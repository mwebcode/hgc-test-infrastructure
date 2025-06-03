import os
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal


class DynamoDBClient:
    def __init__(self):
        self.table_name = os.environ.get('DYNAMODB_TABLE')
        if not self.table_name:
            raise ValueError("DynamoDB table name not found in environment variables")
        
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(self.table_name)

    def put_test_run(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a test run in DynamoDB
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Calculate TTL (90 days from now)
        import time
        ttl = int(time.time()) + (90 * 24 * 60 * 60)
        
        item = {
            'pk': f"BRAND#{run_data['brand']}",
            'sk': f"RUN#{timestamp}#{run_data['runId']}",
            'gsi1pk': f"STATUS#{run_data.get('status', 'pending')}",
            'gsi1sk': f"TIMESTAMP#{timestamp}",
            'runId': run_data['runId'],
            'brand': run_data['brand'],
            'environment': run_data['environment'],
            'status': run_data.get('status', 'pending'),
            'timestamp': timestamp,
            'githubRunId': run_data.get('githubRunId'),
            'commit': run_data.get('commit'),
            'actor': run_data.get('actor'),
            'workflow': run_data.get('workflow'),
            'repository': run_data.get('repository'),
            'ttl': ttl
        }
        
        # Add optional fields if they exist
        if 'duration' in run_data:
            item['duration'] = run_data['duration']
        if 'tests' in run_data:
            item['tests'] = run_data['tests']
        if 'reportUrl' in run_data:
            item['reportUrl'] = run_data['reportUrl']
        if 'artifacts' in run_data:
            item['artifacts'] = run_data['artifacts']
        
        try:
            self.table.put_item(Item=item)
            return {'success': True, 'item': item}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_test_run(self, brand: str, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific test run by brand and run ID
        """
        try:
            response = self.table.query(
                KeyConditionExpression='pk = :pk AND begins_with(sk, :sk_prefix)',
                FilterExpression='runId = :run_id',
                ExpressionAttributeValues={
                    ':pk': f'BRAND#{brand}',
                    ':sk_prefix': f'RUN#',
                    ':run_id': run_id
                }
            )
            
            if response['Items']:
                return response['Items'][0]
            return None
        except Exception as e:
            raise Exception(f"Failed to get test run: {str(e)}")

    def list_test_runs(self, brand: Optional[str] = None, status: Optional[str] = None, 
                      start_date: Optional[str] = None, end_date: Optional[str] = None,
                      limit: int = 25, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """
        List test runs with optional filtering
        """
        try:
            # Base query parameters
            query_kwargs = {
                'Limit': limit
            }
            
            if last_evaluated_key:
                query_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            # Determine which query strategy to use
            if status:
                # Use GSI1 to query by status
                query_kwargs.update({
                    'IndexName': 'GSI1',
                    'KeyConditionExpression': 'gsi1pk = :gsi1pk',
                    'ExpressionAttributeValues': {
                        ':gsi1pk': f'STATUS#{status}'
                    }
                })
                
                # Add timestamp range condition if provided
                if start_date or end_date:
                    if start_date and end_date:
                        query_kwargs['KeyConditionExpression'] += ' AND gsi1sk BETWEEN :start_ts AND :end_ts'
                        query_kwargs['ExpressionAttributeValues'].update({
                            ':start_ts': f'TIMESTAMP#{start_date}',
                            ':end_ts': f'TIMESTAMP#{end_date}'
                        })
                    elif start_date:
                        query_kwargs['KeyConditionExpression'] += ' AND gsi1sk >= :start_ts'
                        query_kwargs['ExpressionAttributeValues'][':start_ts'] = f'TIMESTAMP#{start_date}'
                    elif end_date:
                        query_kwargs['KeyConditionExpression'] += ' AND gsi1sk <= :end_ts'
                        query_kwargs['ExpressionAttributeValues'][':end_ts'] = f'TIMESTAMP#{end_date}'
                
            elif brand:
                # Query by brand using primary key
                query_kwargs.update({
                    'KeyConditionExpression': 'pk = :pk',
                    'ExpressionAttributeValues': {
                        ':pk': f'BRAND#{brand}'
                    }
                })
                
            else:
                # Default to querying mweb brand to avoid expensive scans
                query_kwargs.update({
                    'KeyConditionExpression': 'pk = :pk',
                    'ExpressionAttributeValues': {
                        ':pk': 'BRAND#mweb'
                    }
                })
            
            # Execute the query
            response = self.table.query(**query_kwargs)
            
            # Filter by brand if both status and brand were specified
            items = response['Items']
            if status and brand:
                items = [item for item in items if item.get('brand') == brand]
            
            # Sort by timestamp descending (most recent first)
            items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Build result
            result = {
                'items': items,
                'count': len(items)
            }
            
            if 'LastEvaluatedKey' in response:
                result['lastEvaluatedKey'] = response['LastEvaluatedKey']
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to list test runs: {str(e)}")

    def update_test_run_status(self, brand: str, run_id: str, status: str, 
                              additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update test run status and additional data
        """
        try:
            # First get the item to find the correct sort key
            existing_item = self.get_test_run(brand, run_id)
            if not existing_item:
                return {'success': False, 'error': 'Test run not found'}
            
            # Update expression
            update_expression = "SET #status = :status, gsi1pk = :gsi1pk"
            expression_attribute_names = {'#status': 'status'}
            expression_attribute_values = {
                ':status': status,
                ':gsi1pk': f'STATUS#{status}'
            }
            
            # Add additional data to update
            if additional_data:
                for key, value in additional_data.items():
                    if key not in ['pk', 'sk', 'gsi1pk', 'gsi1sk']:  # Don't update key attributes
                        update_expression += f", #{key} = :{key}"
                        expression_attribute_names[f'#{key}'] = key
                        expression_attribute_values[f':{key}'] = value
            
            response = self.table.update_item(
                Key={
                    'pk': existing_item['pk'],
                    'sk': existing_item['sk']
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues='ALL_NEW'
            )
            
            return {'success': True, 'item': response['Attributes']}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}