import os
import httpx
from typing import Dict, Any, Optional


class GitHubClient:
    def __init__(self):
        self.token = os.environ.get('GITHUB_TOKEN')
        if not self.token:
            raise ValueError("GitHub token not found in environment variables")
        
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }

    def trigger_workflow(self, owner: str, repo: str, workflow_id: str, ref: str = 'main', inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Trigger a GitHub Actions workflow
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
        
        payload = {
            'ref': ref,
            'inputs': inputs or {}
        }
        
        response = httpx.post(url, json=payload, headers=self.headers)
        
        if response.status_code == 204:
            return {
                'success': True,
                'message': 'Workflow triggered successfully'
            }
        else:
            return {
                'success': False,
                'message': f'Failed to trigger workflow: {response.text}',
                'status_code': response.status_code
            }

    def get_workflow_runs(self, owner: str, repo: str, workflow_id: str, per_page: int = 10) -> Dict[str, Any]:
        """
        Get recent workflow runs
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        params = {'per_page': per_page}
        
        response = httpx.get(url, params=params, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get workflow runs: {response.text}")

    def get_run_status(self, owner: str, repo: str, run_id: str) -> Dict[str, Any]:
        """
        Get status of a specific workflow run
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
        
        response = httpx.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get run status: {response.text}")

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify GitHub webhook signature
        """
        import hmac
        import hashlib
        
        expected_signature = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)