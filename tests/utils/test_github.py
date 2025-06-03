import pytest
from unittest.mock import patch, MagicMock
import httpx
from src.utils.github import GitHubClient


class TestGitHubClient:
    
    def test_github_client_initialization(self, mock_env_vars):
        """Test GitHub client initialization"""
        client = GitHubClient()
        
        assert client.token == 'test-token'
        assert 'Authorization' in client.headers
        assert client.headers['Authorization'] == 'token test-token'
        assert client.headers['Accept'] == 'application/vnd.github.v3+json'
        assert client.headers['X-GitHub-Api-Version'] == '2022-11-28'
    
    def test_trigger_workflow_success(self, mock_env_vars):
        """Test successful workflow trigger"""
        with patch('httpx.post') as mock_post:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            client = GitHubClient()
            result = client.trigger_workflow(
                owner='test-owner',
                repo='test-repo',
                workflow_id='test-workflow',
                ref='main',
                inputs={'brand': 'mweb', 'environment': 'prod'}
            )
            
            assert result['success'] is True
            assert result['message'] == 'Workflow triggered successfully'
            
            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert 'repos/test-owner/test-repo/actions/workflows/test-workflow/dispatches' in call_args[0][0]
            assert call_args[1]['json']['ref'] == 'main'
            assert call_args[1]['json']['inputs']['brand'] == 'mweb'
    
    def test_trigger_workflow_failure(self, mock_env_vars):
        """Test workflow trigger failure"""
        with patch('httpx.post') as mock_post:
            # Mock failure response
            mock_response = MagicMock()
            mock_response.status_code = 422
            mock_response.text = 'Unprocessable Entity'
            mock_post.return_value = mock_response
            
            client = GitHubClient()
            result = client.trigger_workflow(
                owner='test-owner',
                repo='test-repo',
                workflow_id='test-workflow',
                ref='main'
            )
            
            assert result['success'] is False
            assert 'Failed to trigger workflow' in result['message']
            assert result['status_code'] == 422
    
    def test_trigger_workflow_with_inputs(self, mock_env_vars):
        """Test workflow trigger with custom inputs"""
        with patch('httpx.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            client = GitHubClient()
            inputs = {
                'brand': 'webafrica',
                'environment': 'staging',
                'runId': 'custom-run-id',
                'triggeredBy': 'api'
            }
            
            result = client.trigger_workflow(
                owner='test-owner',
                repo='test-repo',
                workflow_id='test-workflow',
                ref='develop',
                inputs=inputs
            )
            
            assert result['success'] is True
            
            # Verify inputs were passed correctly
            call_args = mock_post.call_args
            request_json = call_args[1]['json']
            assert request_json['ref'] == 'develop'
            assert request_json['inputs'] == inputs
    
    def test_trigger_workflow_without_inputs(self, mock_env_vars):
        """Test workflow trigger without inputs"""
        with patch('httpx.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            client = GitHubClient()
            result = client.trigger_workflow(
                owner='test-owner',
                repo='test-repo',
                workflow_id='test-workflow',
                ref='main'
            )
            
            assert result['success'] is True
            
            # Verify request structure
            call_args = mock_post.call_args
            request_json = call_args[1]['json']
            assert request_json['ref'] == 'main'
            assert request_json['inputs'] == {}
    
    def test_github_client_missing_token(self):
        """Test GitHub client initialization without token"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="GitHub token not found"):
                GitHubClient()
    
    def test_get_workflow_runs_success(self, mock_env_vars):
        """Test successful workflow runs retrieval"""
        with patch('httpx.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'workflow_runs': [
                    {'id': 123, 'status': 'completed'},
                    {'id': 124, 'status': 'in_progress'}
                ]
            }
            mock_get.return_value = mock_response
            
            client = GitHubClient()
            result = client.get_workflow_runs(
                owner='test-owner',
                repo='test-repo',
                workflow_id='test-workflow'
            )
            
            assert 'workflow_runs' in result
            assert len(result['workflow_runs']) == 2
    
    def test_get_run_status_success(self, mock_env_vars):
        """Test successful run status retrieval"""
        with patch('httpx.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'id': 123,
                'status': 'completed',
                'conclusion': 'success'
            }
            mock_get.return_value = mock_response
            
            client = GitHubClient()
            result = client.get_run_status(
                owner='test-owner',
                repo='test-repo',
                run_id='123'
            )
            
            assert result['id'] == 123
            assert result['status'] == 'completed'
            assert result['conclusion'] == 'success'
    
    def test_verify_webhook_signature(self, mock_env_vars):
        """Test webhook signature verification"""
        client = GitHubClient()
        
        # Test valid signature
        payload = b'{"test": "data"}'
        secret = 'test-secret'
        
        import hmac
        import hashlib
        expected_signature = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        assert client.verify_webhook_signature(payload, expected_signature, secret) is True
        
        # Test invalid signature
        assert client.verify_webhook_signature(payload, 'invalid-signature', secret) is False