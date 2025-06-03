import json
from typing import Dict, Any
from decimal import Decimal

from ..utils.dynamodb import DynamoDBClient
from ..utils.s3 import S3Client


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler to get test results for a specific run
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
        
        # Get run ID from path parameters
        path_parameters = event.get('pathParameters', {})
        run_id = path_parameters.get('runId')
        
        if not run_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Missing runId parameter'
                })
            }
        
        # Get brand from query parameters (required to query DynamoDB efficiently)
        query_parameters = event.get('queryStringParameters') or {}
        brand = query_parameters.get('brand')
        
        # Initialize clients
        dynamodb_client = DynamoDBClient()
        s3_client = S3Client()
        
        # Get test run metadata from DynamoDB
        if brand:
            # Efficient query by brand
            test_run = dynamodb_client.get_test_run(brand, run_id)
        else:
            # Less efficient - search across all brands
            # You might want to add a GSI for runId if this becomes common
            all_brands = ['mweb', 'webafrica']  # Update as needed
            test_run = None
            
            for b in all_brands:
                test_run = dynamodb_client.get_test_run(b, run_id)
                if test_run:
                    break
        
        if not test_run:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'error': 'Test run not found',
                    'runId': run_id
                })
            }
        
        # Build response with basic metadata
        response_data = {
            'runId': test_run['runId'],
            'brand': test_run['brand'],
            'environment': test_run['environment'],
            'status': test_run['status'],
            'timestamp': test_run['timestamp'],
            'githubRunId': test_run.get('githubRunId'),
            'commit': test_run.get('commit'),
            'actor': test_run.get('actor'),
            'workflow': test_run.get('workflow'),
            'repository': test_run.get('repository'),
            'duration': test_run.get('duration'),
            'tests': test_run.get('tests'),
            'artifacts': None,
            'reportUrl': None
        }
        
        # If test run is completed, get S3 artifacts
        if test_run['status'] in ['passed', 'failed', 'completed']:
            try:
                # Extract timestamp for S3 path construction
                # Timestamp format: 2025-06-03T14:00:00Z -> 20250603_140000
                iso_timestamp = test_run['timestamp']
                timestamp_for_s3 = iso_timestamp.replace('-', '').replace(':', '').replace('T', '_').replace('Z', '')[:15]
                
                artifacts = s3_client.get_test_artifacts(
                    test_run['brand'],
                    test_run['environment'],
                    timestamp_for_s3
                )
                
                response_data['artifacts'] = artifacts
                response_data['reportUrl'] = artifacts.get('html_report_url')
                
            except Exception as e:
                # Don't fail the request if S3 artifacts can't be retrieved
                print(f"Failed to get S3 artifacts for run {run_id}: {str(e)}")
                response_data['artifacts'] = {
                    'error': 'Failed to retrieve artifacts from S3',
                    'details': str(e)
                }
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_data, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Error in get_results handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }