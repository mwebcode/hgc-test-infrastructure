import json
import os
from typing import Dict, Any

from ..utils.dynamodb import DynamoDBClient
from ..utils.github import GitHubClient


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for GitHub webhook to update test run status
    """
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent,X-GitHub-Event,X-GitHub-Delivery,X-Hub-Signature-256',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }
    
    try:
        # Handle preflight requests
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': ''
            }
        
        # Get webhook headers
        webhook_headers = event.get('headers', {})
        github_event = webhook_headers.get('X-GitHub-Event') or webhook_headers.get('x-github-event')
        github_delivery = webhook_headers.get('X-GitHub-Delivery') or webhook_headers.get('x-github-delivery')
        signature = webhook_headers.get('X-Hub-Signature-256') or webhook_headers.get('x-hub-signature-256')
        
        # Only process workflow_run events
        if github_event != 'workflow_run':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'message': f'Ignored event type: {github_event}',
                    'delivery': github_delivery
                })
            }
        
        # Parse webhook payload
        body = event.get('body', '{}')
        
        # Verify webhook signature if secret is configured
        webhook_secret = os.environ.get('GITHUB_WEBHOOK_SECRET')
        if webhook_secret and signature:
            github_client = GitHubClient()
            if not github_client.verify_webhook_signature(body.encode(), signature, webhook_secret):
                return {
                    'statusCode': 401,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'Invalid webhook signature'
                    })
                }
        
        payload = json.loads(body)
        
        # Extract workflow run information
        workflow_run = payload.get('workflow_run', {})
        action = payload.get('action')
        
        # Only process completed workflows
        if action != 'completed':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({
                    'message': f'Ignored action: {action}',
                    'delivery': github_delivery
                })
            }
        
        # Extract run information
        github_run_id = str(workflow_run.get('id'))
        conclusion = workflow_run.get('conclusion')  # success, failure, cancelled, etc.
        status = workflow_run.get('status')  # completed
        workflow_name = workflow_run.get('name')
        run_number = workflow_run.get('run_number')
        created_at = workflow_run.get('created_at')
        updated_at = workflow_run.get('updated_at')
        
        # Map GitHub conclusion to our status
        status_mapping = {
            'success': 'passed',
            'failure': 'failed',
            'cancelled': 'cancelled',
            'skipped': 'cancelled',
            'timed_out': 'failed',
            'action_required': 'failed'
        }
        
        final_status = status_mapping.get(conclusion, 'failed')
        
        # Calculate duration if possible
        duration = None
        if created_at and updated_at:
            from datetime import datetime
            try:
                start = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                end = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                duration = int((end - start).total_seconds())
            except Exception as e:
                print(f"Failed to calculate duration: {e}")
        
        # Try to extract custom run ID from workflow inputs or run name
        # This would be set when triggering via API
        custom_run_id = None
        inputs = workflow_run.get('inputs') or {}
        custom_run_id = inputs.get('runId')
        
        if not custom_run_id:
            # Try to extract from head commit message or other sources
            head_commit = workflow_run.get('head_commit', {})
            commit_message = head_commit.get('message', '')
            
            # Look for runId in commit message format: [runId: xxx-xxx-xxx]
            import re
            match = re.search(r'\[runId:\s*([^\]]+)\]', commit_message)
            if match:
                custom_run_id = match.group(1).strip()
        
        # Initialize DynamoDB client
        dynamodb_client = DynamoDBClient()
        
        # Extract brand from inputs or repository
        brand = inputs.get('brand')
        environment = inputs.get('environment')
        
        if not brand:
            # Try to determine from repository or workflow name
            repo_name = payload.get('repository', {}).get('name', '')
            if 'mweb' in repo_name.lower():
                brand = 'mweb'
            elif 'webafrica' in repo_name.lower():
                brand = 'webafrica'
        
        # Prepare update data
        update_data = {
            'status': final_status,
            'githubRunId': github_run_id,
            'conclusion': conclusion,
            'workflowName': workflow_name,
            'runNumber': run_number,
            'updatedAt': updated_at
        }
        
        if duration:
            update_data['duration'] = duration
        
        # Try to parse test results from workflow output (if available)
        # This would require additional API calls to get job outputs
        # For now, we'll skip this and rely on the GitHub Actions to upload this data
        
        update_result = None
        
        if custom_run_id and brand:
            # Update specific run by custom run ID
            update_result = dynamodb_client.update_test_run_status(
                brand=brand,
                run_id=custom_run_id,
                status=final_status,
                additional_data=update_data
            )
        elif github_run_id:
            # Try to find run by GitHub run ID (less efficient)
            # This requires scanning or using a GSI
            print(f"Attempting to find run by GitHub run ID: {github_run_id}")
            # For now, we'll create a new entry if we can't find the existing one
            
            if brand and environment:
                from datetime import datetime, timezone
                import uuid
                
                run_data = {
                    'runId': custom_run_id or str(uuid.uuid4()),
                    'brand': brand,
                    'environment': environment,
                    'status': final_status,
                    'githubRunId': github_run_id,
                    'conclusion': conclusion,
                    'workflowName': workflow_name,
                    'runNumber': run_number,
                    'actor': workflow_run.get('actor', {}).get('login', 'unknown'),
                    'workflow': workflow_run.get('workflow_id'),
                    'repository': payload.get('repository', {}).get('full_name'),
                    'commit': workflow_run.get('head_sha'),
                    'duration': duration
                }
                
                update_result = dynamodb_client.put_test_run(run_data)
        
        response_data = {
            'message': 'Webhook processed successfully',
            'delivery': github_delivery,
            'action': action,
            'status': final_status,
            'githubRunId': github_run_id,
            'customRunId': custom_run_id,
            'brand': brand,
            'environment': environment,
            'duration': duration
        }
        
        if update_result:
            response_data['database_update'] = update_result.get('success', False)
            if not update_result.get('success'):
                response_data['database_error'] = update_result.get('error')
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_data)
        }
        
    except json.JSONDecodeError as e:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({
                'error': 'Invalid JSON in webhook payload',
                'details': str(e)
            })
        }
    
    except Exception as e:
        print(f"Error in webhook handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }