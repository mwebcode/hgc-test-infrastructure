import json
from typing import Dict, Any
from decimal import Decimal

from ..utils.dynamodb import DynamoDBClient


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler to list test runs with filtering and pagination
    """
    
    # CORS headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }
    
    try:
        # Handle preflight requests
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': ''
            }
        
        # Parse query parameters
        query_parameters = event.get('queryStringParameters') or {}
        
        brand = query_parameters.get('brand')
        status = query_parameters.get('status')
        start_date = query_parameters.get('startDate')
        end_date = query_parameters.get('endDate')
        limit = int(query_parameters.get('limit', '25'))
        
        # Handle pagination
        last_evaluated_key = None
        if query_parameters.get('lastEvaluatedKey'):
            try:
                last_evaluated_key = json.loads(query_parameters['lastEvaluatedKey'])
            except json.JSONDecodeError:
                return {
                    'statusCode': 400,
                    'headers': headers,
                    'body': json.dumps({
                        'error': 'Invalid lastEvaluatedKey format'
                    })
                }
        
        # Validate parameters
        if limit > 100:
            limit = 100  # Cap at 100 items per request
        
        valid_brands = ['mweb', 'webafrica']
        if brand and brand not in valid_brands:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Invalid brand. Must be one of: {", ".join(valid_brands)}'
                })
            }
        
        valid_statuses = ['pending', 'triggered', 'running', 'passed', 'failed', 'cancelled', 'completed']
        if status and status not in valid_statuses:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                })
            }
        
        # Initialize DynamoDB client
        dynamodb_client = DynamoDBClient()
        
        # Query test runs
        result = dynamodb_client.list_test_runs(
            brand=brand,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            last_evaluated_key=last_evaluated_key
        )
        
        # Transform items for response
        items = []
        for item in result['items']:
            transformed_item = {
                'runId': item['runId'],
                'brand': item['brand'],
                'environment': item['environment'],
                'status': item['status'],
                'timestamp': item['timestamp'],
                'githubRunId': item.get('githubRunId'),
                'commit': item.get('commit'),
                'actor': item.get('actor'),
                'workflow': item.get('workflow'),
                'duration': item.get('duration'),
                'tests': item.get('tests')
            }
            items.append(transformed_item)
        
        # Build response
        response_data = {
            'items': items,
            'count': len(items),
            'limit': limit,
            'filters': {
                'brand': brand,
                'status': status,
                'startDate': start_date,
                'endDate': end_date
            }
        }
        
        # Add pagination info
        if 'lastEvaluatedKey' in result:
            response_data['pagination'] = {
                'hasMore': True,
                'lastEvaluatedKey': json.dumps(result['lastEvaluatedKey'])
            }
        else:
            response_data['pagination'] = {
                'hasMore': False
            }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_data, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error in list_runs handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }