import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from ..utils.github import GitHubClient
from ..utils.dynamodb import DynamoDBClient


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler to trigger GitHub Actions workflow
    """
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent',
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
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        # Validate required parameters
        brand = body.get('brand')
        environment = body.get('environment')
        
        if not brand or not environment:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Missing required parameters: brand and environment'
                })
            }
        
        # Validate brand values
        valid_brands = ['mweb', 'webafrica']  # Add more as needed
        if brand not in valid_brands:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Invalid brand. Must be one of: {", ".join(valid_brands)}'
                })
            }
        
        # Validate environment values
        valid_environments = ['prod', 'staging', 'dev']  # Add more as needed
        if environment not in valid_environments:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Invalid environment. Must be one of: {", ".join(valid_environments)}'
                })
            }
        
        # Generate unique run ID
        run_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Initialize clients
        github_client = GitHubClient()
        dynamodb_client = DynamoDBClient()
        
        # Prepare workflow inputs
        workflow_inputs = {
            'brand': brand,
            'environment': environment,
            'runId': run_id,
            'triggeredBy': 'api'
        }
        
        # Trigger GitHub Actions workflow
        workflow_result = github_client.trigger_workflow(
            owner='mwebcode',
            repo='hgc-frontend-tests',
            workflow_id='165936262',  # Use the workflow ID from GitHub
            ref='main',
            inputs=workflow_inputs
        )
        
        if not workflow_result['success']:
            return {
                'statusCode': 500,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Failed to trigger GitHub workflow',
                    'details': workflow_result['message']
                })
            }
        
        # Store initial run metadata in DynamoDB
        run_data = {
            'runId': run_id,
            'brand': brand,
            'environment': environment,
            'status': 'triggered',
            'timestamp': timestamp,
            'actor': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'api'),
            'workflow': 'scheduled-tests.yml',
            'repository': 'mwebcode/hgc-frontend-tests'
        }
        
        db_result = dynamodb_client.put_test_run(run_data)
        
        if not db_result['success']:
            # Log error but don't fail the request since workflow was triggered
            print(f"Failed to store run metadata: {db_result['error']}")
        
        # Return success response
        response_body = {
            'success': True,
            'runId': run_id,
            'brand': brand,
            'environment': environment,
            'status': 'triggered',
            'timestamp': timestamp,
            'message': 'Test workflow triggered successfully'
        }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({
                'error': 'Invalid JSON in request body'
            })
        }
    
    except Exception as e:
        print(f"Error in trigger_tests handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }