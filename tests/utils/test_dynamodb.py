import pytest
from unittest.mock import patch, MagicMock
import time
from decimal import Decimal
from src.utils.dynamodb import DynamoDBClient


class TestDynamoDBClient:
    
    def test_put_test_run_success(self, mock_dynamodb_resource, mock_env_vars):
        """Test successful test run insertion"""
        client = DynamoDBClient()
        
        run_data = {
            'runId': 'test-run-id',
            'brand': 'mweb',
            'environment': 'prod',
            'status': 'running',
            'githubRunId': '12345',
            'commit': 'abc123',
            'actor': 'test-user'
        }
        
        result = client.put_test_run(run_data)
        
        if not result['success']:
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        assert result['success'] is True
        assert 'item' in result
        
        # Verify item structure
        item = result['item']
        assert item['pk'] == 'BRAND#mweb'
        assert item['sk'].startswith('RUN#')
        assert item['gsi1pk'] == 'STATUS#running'
        assert item['runId'] == 'test-run-id'
        assert item['brand'] == 'mweb'
        assert item['environment'] == 'prod'
        assert 'ttl' in item
    
    def test_put_test_run_with_optional_fields(self, mock_dynamodb_resource, mock_env_vars):
        """Test test run insertion with optional fields"""
        client = DynamoDBClient()
        
        run_data = {
            'runId': 'test-run-id',
            'brand': 'mweb',
            'environment': 'prod',
            'duration': 120,
            'tests': {'total': 10, 'passed': 8},
            'reportUrl': 'https://example.com/report.html',
            'artifacts': ['screenshot.png']
        }
        
        result = client.put_test_run(run_data)
        
        assert result['success'] is True
        item = result['item']
        assert item['duration'] == 120
        assert item['tests'] == {'total': 10, 'passed': 8}
        assert item['reportUrl'] == 'https://example.com/report.html'
        assert item['artifacts'] == ['screenshot.png']
    
    def test_get_test_run_success(self, mock_dynamodb_resource, mock_env_vars):
        """Test successful test run retrieval"""
        client = DynamoDBClient()
        
        # First insert a test run
        run_data = {
            'runId': 'test-run-id',
            'brand': 'mweb',
            'environment': 'prod'
        }
        client.put_test_run(run_data)
        
        # Then retrieve it
        result = client.get_test_run('mweb', 'test-run-id')
        
        assert result is not None
        assert result['runId'] == 'test-run-id'
        assert result['brand'] == 'mweb'
        assert result['environment'] == 'prod'
    
    def test_get_test_run_not_found(self, mock_dynamodb_resource, mock_env_vars):
        """Test test run retrieval when not found"""
        client = DynamoDBClient()
        
        result = client.get_test_run('mweb', 'nonexistent-run-id')
        
        assert result is None
    
    def test_list_test_runs_by_brand(self, mock_dynamodb_resource, mock_env_vars):
        """Test listing test runs by brand"""
        client = DynamoDBClient()
        
        # Insert multiple test runs
        for i in range(3):
            run_data = {
                'runId': f'test-run-{i}',
                'brand': 'mweb',
                'environment': 'prod'
            }
            client.put_test_run(run_data)
        
        # List runs for mweb brand
        result = client.list_test_runs(brand='mweb', limit=10)
        
        assert 'items' in result
        assert len(result['items']) == 3
        assert result['count'] == 3
        
        # Verify all items are for mweb brand
        for item in result['items']:
            assert item['brand'] == 'mweb'
    
    def test_list_test_runs_by_status(self, mock_dynamodb_resource, mock_env_vars):
        """Test listing test runs by status"""
        client = DynamoDBClient()
        
        # Insert test runs with different statuses
        statuses = ['running', 'passed', 'failed']
        for i, status in enumerate(statuses):
            run_data = {
                'runId': f'test-run-{i}',
                'brand': 'mweb',
                'environment': 'prod',
                'status': status
            }
            client.put_test_run(run_data)
        
        # List runs with 'passed' status
        result = client.list_test_runs(status='passed', limit=10)
        
        assert 'items' in result
        assert len(result['items']) == 1
        assert result['items'][0]['status'] == 'passed'
    
    def test_list_test_runs_default_mweb(self, mock_dynamodb_resource, mock_env_vars):
        """Test listing test runs defaults to mweb brand"""
        client = DynamoDBClient()
        
        # Insert runs for different brands
        brands = ['mweb', 'webafrica']
        for brand in brands:
            run_data = {
                'runId': f'test-run-{brand}',
                'brand': brand,
                'environment': 'prod'
            }
            client.put_test_run(run_data)
        
        # List runs without specifying brand (should default to mweb)
        result = client.list_test_runs(limit=10)
        
        assert 'items' in result
        # Should only return mweb items due to default behavior
        for item in result['items']:
            assert item['brand'] == 'mweb'
    
    def test_list_test_runs_with_limit(self, mock_dynamodb_resource, mock_env_vars):
        """Test listing test runs with limit"""
        client = DynamoDBClient()
        
        # Insert 5 test runs
        for i in range(5):
            run_data = {
                'runId': f'test-run-{i}',
                'brand': 'mweb',
                'environment': 'prod'
            }
            client.put_test_run(run_data)
        
        # List with limit of 3
        result = client.list_test_runs(brand='mweb', limit=3)
        
        assert len(result['items']) == 3
        assert result['count'] == 3
    
    def test_update_test_run_status_success(self, mock_dynamodb_resource, mock_env_vars):
        """Test successful test run status update"""
        client = DynamoDBClient()
        
        # First insert a test run
        run_data = {
            'runId': 'test-run-id',
            'brand': 'mweb',
            'environment': 'prod',
            'status': 'running'
        }
        client.put_test_run(run_data)
        
        # Update status with additional data
        additional_data = {
            'duration': 120,
            'tests': {'total': 10, 'passed': 8}
        }
        
        result = client.update_test_run_status(
            'mweb', 
            'test-run-id', 
            'passed', 
            additional_data
        )
        
        assert result['success'] is True
        assert 'item' in result
        
        # Verify updates
        updated_item = result['item']
        assert updated_item['status'] == 'passed'
        assert updated_item['gsi1pk'] == 'STATUS#passed'
        assert updated_item['duration'] == 120
        assert updated_item['tests'] == {'total': 10, 'passed': 8}
    
    def test_update_test_run_status_not_found(self, mock_dynamodb_resource, mock_env_vars):
        """Test updating non-existent test run"""
        client = DynamoDBClient()
        
        result = client.update_test_run_status(
            'mweb', 
            'nonexistent-run-id', 
            'passed'
        )
        
        assert result['success'] is False
        assert 'error' in result
        assert 'Test run not found' in result['error']
    
    def test_dynamodb_client_initialization_error(self):
        """Test DynamoDB client initialization without environment variable"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="DynamoDB table name not found"):
                DynamoDBClient()
    
    def test_put_test_run_exception_handling(self, mock_env_vars):
        """Test exception handling in put_test_run"""
        with patch('boto3.resource') as mock_boto3:
            # Mock table that raises exception
            mock_table = MagicMock()
            mock_table.put_item.side_effect = Exception("DynamoDB error")
            mock_boto3.return_value.Table.return_value = mock_table
            
            client = DynamoDBClient()
            run_data = {
                'runId': 'test-run-id',
                'brand': 'mweb',
                'environment': 'prod'
            }
            
            result = client.put_test_run(run_data)
            
            assert result['success'] is False
            assert 'error' in result
            assert 'DynamoDB error' in result['error']