import os
import pytest
import boto3
from moto import mock_dynamodb, mock_s3, mock_ssm


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    test_env = {
        'STAGE': 'test',
        'REGION': 'af-south-1',
        'S3_BUCKET': 'test-bucket',
        'DYNAMODB_TABLE': 'test-table',
        'GITHUB_TOKEN': 'test-token'
    }
    
    # Store original values
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield test_env
    
    # Restore original values
    for key, original_value in original_env.items():
        if original_value is not None:
            os.environ[key] = original_value
        elif key in os.environ:
            del os.environ[key]


@pytest.fixture
def mock_dynamodb_resource(mock_env_vars):
    """Create a mock DynamoDB resource for testing"""
    with mock_dynamodb():
        # Set region in environment for boto3
        os.environ['AWS_DEFAULT_REGION'] = 'af-south-1'
        
        dynamodb = boto3.resource('dynamodb', region_name='af-south-1')
        
        # Create the table
        table = dynamodb.create_table(
            TableName='test-table',
            KeySchema=[
                {
                    'AttributeName': 'pk',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'sk',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'pk',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'sk',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'gsi1pk',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'gsi1sk',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {
                            'AttributeName': 'gsi1pk',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'gsi1sk',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        
        # Wait for table to be active (in mock this is immediate)
        table.meta.client.get_waiter('table_exists').wait(TableName='test-table')
        
        yield dynamodb


@pytest.fixture
def s3_bucket(mock_env_vars):
    """Create a mock S3 bucket for testing"""
    with mock_s3():
        # Set region in environment for boto3
        os.environ['AWS_DEFAULT_REGION'] = 'af-south-1'
        
        s3 = boto3.client('s3', region_name='af-south-1')
        s3.create_bucket(Bucket='test-bucket')
        yield s3


@pytest.fixture
def ssm_client(mock_env_vars):
    """Create a mock SSM client for testing"""
    with mock_ssm():
        ssm = boto3.client('ssm', region_name='af-south-1')
        
        # Add test parameters
        ssm.put_parameter(
            Name='/hgc-frontend-tests/test/github-token',
            Value='test-github-token',
            Type='SecureString'
        )
        
        yield ssm


@pytest.fixture
def sample_lambda_event():
    """Sample Lambda event for testing"""
    return {
        'httpMethod': 'POST',
        'path': '/trigger-tests',
        'headers': {
            'Content-Type': 'application/json',
            'X-Api-Key': 'test-api-key'
        },
        'body': '{"brand": "mweb", "environment": "prod"}',
        'queryStringParameters': None,
        'pathParameters': None,
        'requestContext': {
            'requestId': 'test-request-id',
            'identity': {
                'sourceIp': '127.0.0.1'
            }
        }
    }


@pytest.fixture
def sample_lambda_context():
    """Sample Lambda context for testing"""
    class MockContext:
        def __init__(self):
            self.function_name = 'test-function'
            self.function_version = '1'
            self.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test-function'
            self.memory_limit_in_mb = '128'
            self.remaining_time_in_millis = lambda: 30000
            self.aws_request_id = 'test-request-id'
            self.log_group_name = '/aws/lambda/test-function'
            self.log_stream_name = '2023/01/01/[$LATEST]test-stream'
    
    return MockContext()