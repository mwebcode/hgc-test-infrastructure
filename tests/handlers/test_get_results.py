import json
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from src.handlers.get_results import handler


class TestGetResultsHandler:
    
    def test_get_results_success(self, sample_lambda_context, mock_env_vars):
        """Test successful results retrieval"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'runId': 'test-run-id'},
            'queryStringParameters': {'brand': 'mweb'}
        }
        
        mock_test_run = {
            'runId': 'test-run-id',
            'brand': 'mweb',
            'environment': 'prod',
            'status': 'passed',
            'timestamp': '2023-01-01T00:00:00Z',
            'duration': Decimal('120'),
            'tests': {
                'total': Decimal('10'),
                'passed': Decimal('8'),
                'failed': Decimal('2'),
                'skipped': Decimal('0')
            }
        }
        
        with patch('src.handlers.get_results.DynamoDBClient') as mock_dynamodb_client, \
             patch('src.handlers.get_results.S3Client') as mock_s3_client:
            
            # Mock DynamoDB client
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.get_test_run.return_value = mock_test_run
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            # Mock S3 client
            mock_s3_instance = MagicMock()
            mock_s3_instance.generate_presigned_urls.return_value = {
                'reportUrl': 'https://s3.example.com/report.html',
                'artifacts': ['https://s3.example.com/screenshot.png']
            }
            mock_s3_client.return_value = mock_s3_instance
            
            response = handler(event, sample_lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['runId'] == 'test-run-id'
            assert body['brand'] == 'mweb'
            assert body['status'] == 'passed'
            assert body['duration'] == 120.0  # Decimal converted to float
            assert body['tests']['total'] == 10.0
            assert 'artifacts' in body
    
    def test_get_results_missing_run_id(self, sample_lambda_context, mock_env_vars):
        """Test missing run ID parameter"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': None,
            'queryStringParameters': {'brand': 'mweb'}
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'runId is required' in body['error']
    
    def test_get_results_missing_brand(self, sample_lambda_context, mock_env_vars):
        """Test missing brand parameter"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'runId': 'test-run-id'},
            'queryStringParameters': None
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'brand is required' in body['error']
    
    def test_get_results_invalid_brand(self, sample_lambda_context, mock_env_vars):
        """Test invalid brand parameter"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'runId': 'test-run-id'},
            'queryStringParameters': {'brand': 'invalid'}
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid brand' in body['error']
    
    def test_get_results_not_found(self, sample_lambda_context, mock_env_vars):
        """Test test run not found"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'runId': 'nonexistent-run-id'},
            'queryStringParameters': {'brand': 'mweb'}
        }
        
        with patch('src.handlers.get_results.DynamoDBClient') as mock_dynamodb_client:
            # Mock DynamoDB client to return None
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.get_test_run.return_value = None
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            response = handler(event, sample_lambda_context)
            
            assert response['statusCode'] == 404
            body = json.loads(response['body'])
            assert 'error' in body
            assert 'Test run not found' in body['error']
    
    def test_get_results_dynamodb_error(self, sample_lambda_context, mock_env_vars):
        """Test DynamoDB error handling"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'runId': 'test-run-id'},
            'queryStringParameters': {'brand': 'mweb'}
        }
        
        with patch('src.handlers.get_results.DynamoDBClient') as mock_dynamodb_client:
            # Mock DynamoDB client to raise exception
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.get_test_run.side_effect = Exception("DynamoDB error")
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            response = handler(event, sample_lambda_context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'error' in body
            assert 'Internal server error' in body['error']
    
    def test_get_results_options_request(self, sample_lambda_context, mock_env_vars):
        """Test CORS preflight OPTIONS request"""
        event = {
            'httpMethod': 'OPTIONS',
            'pathParameters': {'runId': 'test-run-id'}
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 200
        assert response['body'] == ''
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
    
    def test_get_results_decimal_serialization(self, sample_lambda_context, mock_env_vars):
        """Test proper Decimal serialization to float"""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'runId': 'test-run-id'},
            'queryStringParameters': {'brand': 'mweb'}
        }
        
        mock_test_run = {
            'runId': 'test-run-id',
            'brand': 'mweb',
            'duration': Decimal('123.45'),
            'tests': {
                'total': Decimal('100'),
                'passed': Decimal('95')
            }
        }
        
        with patch('src.handlers.get_results.DynamoDBClient') as mock_dynamodb_client, \
             patch('src.handlers.get_results.S3Client') as mock_s3_client:
            
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.get_test_run.return_value = mock_test_run
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            mock_s3_instance = MagicMock()
            mock_s3_instance.generate_presigned_urls.return_value = {}
            mock_s3_client.return_value = mock_s3_instance
            
            response = handler(event, sample_lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            
            # Verify Decimal values are converted to float
            assert isinstance(body['duration'], float)
            assert body['duration'] == 123.45
            assert isinstance(body['tests']['total'], float)
            assert body['tests']['total'] == 100.0