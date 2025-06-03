import os
import pytest
import httpx
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional


class APIIntegrationTest:
    """Integration tests that use real API endpoints to catch deployment issues"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Content-Type': 'application/json',
            'X-Api-Key': api_key
        }
        self.client = httpx.Client(timeout=30.0)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def test_list_runs_endpoint(self) -> Dict[str, Any]:
        """Test the /runs endpoint with various parameters"""
        
        # Test basic list runs
        response = self.client.get(
            f"{self.base_url}/runs",
            headers=self.headers,
            params={'limit': 10}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'items' in data, "Response should contain 'items' field"
        assert 'count' in data, "Response should contain 'count' field"
        assert 'pagination' in data, "Response should contain 'pagination' field"
        
        # Test with brand filter
        response = self.client.get(
            f"{self.base_url}/runs",
            headers=self.headers,
            params={'brand': 'mweb', 'limit': 5}
        )
        
        assert response.status_code == 200, f"Brand filter failed: {response.text}"
        
        # Test with status filter
        response = self.client.get(
            f"{self.base_url}/runs",
            headers=self.headers,
            params={'status': 'completed', 'limit': 5}
        )
        
        assert response.status_code == 200, f"Status filter failed: {response.text}"
        
        # Test with combined filters
        response = self.client.get(
            f"{self.base_url}/runs",
            headers=self.headers,
            params={
                'brand': 'mweb',
                'status': 'completed',
                'limit': 5
            }
        )
        
        assert response.status_code == 200, f"Combined filters failed: {response.text}"
        
        return data
    
    def test_trigger_tests_endpoint(self) -> Dict[str, Any]:
        """Test the /trigger-tests endpoint"""
        
        test_data = {
            'brand': 'mweb',
            'environment': 'prod'
        }
        
        response = self.client.post(
            f"{self.base_url}/trigger-tests",
            headers=self.headers,
            json=test_data
        )
        
        # Should return 200 or 202 for successful trigger
        assert response.status_code in [200, 202], f"Trigger failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert 'runId' in data, "Response should contain 'runId' field"
        
        return data
    
    def test_get_results_endpoint(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Test the /results/{runId} endpoint"""
        
        response = self.client.get(
            f"{self.base_url}/results/{run_id}",
            headers=self.headers
        )
        
        # 200 if found, 404 if not found (both acceptable)
        assert response.status_code in [200, 404], f"Get results failed: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert 'runId' in data, "Response should contain 'runId' field"
            return data
        
        return None
    
    def test_cors_headers(self):
        """Test CORS headers are properly set"""
        
        # Test OPTIONS request
        response = self.client.options(
            f"{self.base_url}/runs",
            headers={'Origin': 'https://example.com'}
        )
        
        assert response.status_code == 200, f"OPTIONS request failed: {response.text}"
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
    
    def test_error_handling(self):
        """Test API error handling"""
        
        # Test invalid brand
        response = self.client.get(
            f"{self.base_url}/runs",
            headers=self.headers,
            params={'brand': 'invalid_brand'}
        )
        
        assert response.status_code == 400, f"Should reject invalid brand: {response.text}"
        
        # Test invalid status
        response = self.client.get(
            f"{self.base_url}/runs",
            headers=self.headers,
            params={'status': 'invalid_status'}
        )
        
        assert response.status_code == 400, f"Should reject invalid status: {response.text}"
        
        # Test missing API key
        response = self.client.get(f"{self.base_url}/runs")
        assert response.status_code == 403, f"Should require API key: {response.text}"
    
    def run_full_integration_test(self):
        """Run the complete integration test suite"""
        
        print(f"Running integration tests against: {self.base_url}")
        
        # Test 1: List runs endpoint (this was failing with ScanIndexForward error)
        print("Testing /runs endpoint...")
        runs_data = self.test_list_runs_endpoint()
        print(f"✓ /runs endpoint working - found {runs_data['count']} runs")
        
        # Test 2: CORS headers
        print("Testing CORS headers...")
        self.test_cors_headers()
        print("✓ CORS headers properly configured")
        
        # Test 3: Error handling
        print("Testing error handling...")
        self.test_error_handling()
        print("✓ Error handling working correctly")
        
        # Test 4: Trigger tests endpoint
        print("Testing /trigger-tests endpoint...")
        trigger_data = self.test_trigger_tests_endpoint()
        run_id = trigger_data['runId']
        print(f"✓ Test triggered successfully - runId: {run_id}")
        
        # Test 5: Get results endpoint
        print(f"Testing /results/{run_id} endpoint...")
        results_data = self.test_get_results_endpoint(run_id)
        if results_data:
            print(f"✓ Results endpoint working - status: {results_data.get('status', 'unknown')}")
        else:
            print("✓ Results endpoint working (run not found - expected for new runs)")
        
        print("\n🎉 All integration tests passed!")
        return True


def test_dev_environment():
    """Test the dev environment API"""
    
    # Get environment variables
    api_key = os.environ.get('HGC_API_KEY_DEV')
    base_url = os.environ.get('HGC_API_URL_DEV')
    
    if not api_key or not base_url:
        pytest.skip("Dev environment variables not set (HGC_API_KEY_DEV, HGC_API_URL_DEV)")
    
    with APIIntegrationTest(base_url, api_key) as test_runner:
        test_runner.run_full_integration_test()


def test_prod_environment():
    """Test the prod environment API (read-only tests)"""
    
    # Get environment variables
    api_key = os.environ.get('HGC_API_KEY_PROD')
    base_url = os.environ.get('HGC_API_URL_PROD')
    
    if not api_key or not base_url:
        pytest.skip("Prod environment variables not set (HGC_API_KEY_PROD, HGC_API_URL_PROD)")
    
    with APIIntegrationTest(base_url, api_key) as test_runner:
        # Only run read-only tests in production
        print(f"Running read-only integration tests against PROD: {base_url}")
        
        # Test list runs endpoint
        runs_data = test_runner.test_list_runs_endpoint()
        print(f"✓ PROD /runs endpoint working - found {runs_data['count']} runs")
        
        # Test CORS headers
        test_runner.test_cors_headers()
        print("✓ PROD CORS headers properly configured")
        
        # Test error handling
        test_runner.test_error_handling()
        print("✓ PROD Error handling working correctly")
        
        print("\n🎉 All PROD integration tests passed!")


if __name__ == "__main__":
    """Run integration tests directly"""
    
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python test_integration.py <base_url> <api_key>")
        print("Example: python test_integration.py https://api.example.com your-api-key")
        sys.exit(1)
    
    base_url = sys.argv[1]
    api_key = sys.argv[2]
    
    with APIIntegrationTest(base_url, api_key) as test_runner:
        test_runner.run_full_integration_test()