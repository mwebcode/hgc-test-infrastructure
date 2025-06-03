import json
import pytest
from unittest.mock import patch, MagicMock
from src.handlers.trigger_tests import handler


class TestTriggerTestsHandler:
    
    def test_trigger_tests_success(self, sample_lambda_event, sample_lambda_context, mock_env_vars):
        """Test successful test trigger"""
        with patch('src.handlers.trigger_tests.GitHubClient') as mock_github_client, \
             patch('src.handlers.trigger_tests.DynamoDBClient') as mock_dynamodb_client:
            
            # Mock GitHub client
            mock_github_instance = MagicMock()
            mock_github_instance.trigger_workflow.return_value = {
                'success': True,
                'workflow_run_id': 12345
            }
            mock_github_client.return_value = mock_github_instance
            
            # Mock DynamoDB client
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.put_test_run.return_value = {'success': True}
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            # Call handler
            response = handler(sample_lambda_event, sample_lambda_context)
            
            # Assertions
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
            assert body['brand'] == 'mweb'
            assert body['environment'] == 'prod'
            assert 'runId' in body
            assert body['status'] == 'triggered'
            
            # Verify GitHub workflow was triggered
            mock_github_instance.trigger_workflow.assert_called_once()
            
            # Verify DynamoDB record was created
            mock_dynamodb_instance.put_test_run.assert_called_once()
    
    def test_trigger_tests_invalid_brand(self, sample_lambda_context, mock_env_vars):
        """Test trigger with invalid brand"""
        event = {
            'httpMethod': 'POST',
            'body': '{"brand": "invalid", "environment": "prod"}'
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid brand' in body['error']
    
    def test_trigger_tests_invalid_environment(self, sample_lambda_context, mock_env_vars):
        """Test trigger with invalid environment"""
        event = {
            'httpMethod': 'POST',
            'body': '{"brand": "mweb", "environment": "invalid"}'
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid environment' in body['error']
    
    def test_trigger_tests_missing_body(self, sample_lambda_context, mock_env_vars):
        """Test trigger with missing request body"""
        event = {
            'httpMethod': 'POST',
            'body': '{}'
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Missing required parameters' in body['error']
    
    def test_trigger_tests_invalid_json(self, sample_lambda_context, mock_env_vars):
        """Test trigger with invalid JSON body"""
        event = {
            'httpMethod': 'POST',
            'body': 'invalid json'
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body
        assert 'Invalid JSON' in body['error']
    
    def test_trigger_tests_github_error(self, sample_lambda_event, sample_lambda_context, mock_env_vars):
        """Test GitHub API error handling"""
        with patch('src.handlers.trigger_tests.GitHubClient') as mock_github_client, \
             patch('src.handlers.trigger_tests.DynamoDBClient'):
            
            # Mock GitHub client to raise exception
            mock_github_instance = MagicMock()
            mock_github_instance.trigger_workflow.side_effect = Exception("GitHub API error")
            mock_github_client.return_value = mock_github_instance
            
            response = handler(sample_lambda_event, sample_lambda_context)
            
            assert response['statusCode'] == 500
            body = json.loads(response['body'])
            assert 'error' in body
            assert 'Internal server error' in body['error']
    
    def test_trigger_tests_dynamodb_error(self, sample_lambda_event, sample_lambda_context, mock_env_vars):
        """Test DynamoDB error handling"""
        with patch('src.handlers.trigger_tests.GitHubClient') as mock_github_client, \
             patch('src.handlers.trigger_tests.DynamoDBClient') as mock_dynamodb_client:
            
            # Mock successful GitHub response
            mock_github_instance = MagicMock()
            mock_github_instance.trigger_workflow.return_value = {
                'success': True,
                'workflow_run_id': 12345
            }
            mock_github_client.return_value = mock_github_instance
            
            # Mock DynamoDB client to return error
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.put_test_run.return_value = {
                'success': False,
                'error': 'DynamoDB error'
            }
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            response = handler(sample_lambda_event, sample_lambda_context)
            
            # Should still succeed as GitHub trigger worked
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['success'] is True
    
    def test_trigger_tests_options_request(self, sample_lambda_context, mock_env_vars):
        """Test CORS preflight OPTIONS request"""
        event = {
            'httpMethod': 'OPTIONS',
            'headers': {}
        }
        
        response = handler(event, sample_lambda_context)
        
        assert response['statusCode'] == 200
        assert response['body'] == ''
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
    
    def test_trigger_tests_with_custom_run_id(self, sample_lambda_context, mock_env_vars):
        """Test trigger with custom run ID"""
        event = {
            'httpMethod': 'POST',
            'body': '{"brand": "mweb", "environment": "prod", "runId": "custom-run-id"}'
        }
        
        with patch('src.handlers.trigger_tests.GitHubClient') as mock_github_client, \
             patch('src.handlers.trigger_tests.DynamoDBClient') as mock_dynamodb_client:
            
            # Mock successful responses
            mock_github_instance = MagicMock()
            mock_github_instance.trigger_workflow.return_value = {
                'success': True,
                'workflow_run_id': 12345
            }
            mock_github_client.return_value = mock_github_instance
            
            mock_dynamodb_instance = MagicMock()
            mock_dynamodb_instance.put_test_run.return_value = {'success': True}
            mock_dynamodb_client.return_value = mock_dynamodb_instance
            
            response = handler(event, sample_lambda_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['runId'] == 'custom-run-id'