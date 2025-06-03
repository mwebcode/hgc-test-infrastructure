import os
import json
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .utils.dynamodb import DynamoDBClient
from .utils.s3 import S3Client
from .utils.github import GitHubClient


def get_env_var(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f'{name} environment variable is required to be set')
    return value


# Custom JSON encoder for Decimal types
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


app = FastAPI(
    title="HGC Frontend Test Infrastructure API",
    description="API for managing frontend test automation",
    version="1.0.0"
)

# CORS middleware - same as reference project
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response
class TriggerTestRequest(BaseModel):
    brand: str
    environment: str
    runId: Optional[str] = None


class TestRunResponse(BaseModel):
    runId: str
    brand: str
    environment: str
    status: str
    timestamp: str
    githubRunId: Optional[str] = None
    commit: Optional[str] = None
    actor: Optional[str] = None
    workflow: Optional[str] = None
    duration: Optional[int] = None
    tests: Optional[Dict[str, Any]] = None


class ListRunsResponse(BaseModel):
    items: List[TestRunResponse]
    count: int
    limit: int
    filters: Dict[str, Optional[str]]
    pagination: Dict[str, Any]


# Initialize clients once
dynamodb_client = None
s3_client = None
github_client = None

def get_dynamodb_client() -> DynamoDBClient:
    global dynamodb_client
    if dynamodb_client is None:
        dynamodb_client = DynamoDBClient()
    return dynamodb_client

def get_s3_client() -> S3Client:
    global s3_client
    if s3_client is None:
        s3_client = S3Client()
    return s3_client

def get_github_client() -> GitHubClient:
    global github_client
    if github_client is None:
        github_client = GitHubClient()
    return github_client


@app.get("/runs", response_model=Dict[str, Any])
async def list_runs(
    brand: Optional[str] = Query(None, description="Filter by brand (mweb, webafrica)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[str] = Query(None, alias="startDate", description="Start date filter"),
    end_date: Optional[str] = Query(None, alias="endDate", description="End date filter"),
    limit: int = Query(25, le=100, description="Maximum number of items to return"),
    last_evaluated_key: Optional[str] = Query(None, alias="lastEvaluatedKey", description="Pagination key")
):
    """List test runs with optional filtering and pagination"""
    
    try:
        # Validate parameters
        valid_brands = ['mweb', 'webafrica']
        if brand and brand not in valid_brands:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid brand. Must be one of: {", ".join(valid_brands)}'
            )
        
        valid_statuses = ['pending', 'triggered', 'running', 'passed', 'failed', 'cancelled', 'completed']
        if status and status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            )
        
        # Handle pagination
        parsed_last_key = None
        if last_evaluated_key:
            try:
                parsed_last_key = json.loads(last_evaluated_key)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail='Invalid lastEvaluatedKey format'
                )
        
        # Query DynamoDB
        dynamodb_client = get_dynamodb_client()
        result = dynamodb_client.list_test_runs(
            brand=brand,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            last_evaluated_key=parsed_last_key
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
        
        return JSONResponse(
            content=json.loads(json.dumps(response_data, default=decimal_default))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in list_runs: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f'Internal server error: {str(e)}'
        )


@app.post("/trigger-tests")
async def trigger_tests(request: TriggerTestRequest):
    """Trigger a new test run"""
    
    try:
        # Validate brand
        valid_brands = ['mweb', 'webafrica']
        if request.brand not in valid_brands:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid brand. Must be one of: {", ".join(valid_brands)}'
            )
        
        # Validate environment
        valid_environments = ['prod', 'staging']
        if request.environment not in valid_environments:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid environment. Must be one of: {", ".join(valid_environments)}'
            )
        
        # Generate run ID if not provided
        run_id = request.runId or f"{request.brand}-{request.environment}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        
        # Prepare run data
        run_data = {
            'runId': run_id,
            'brand': request.brand,
            'environment': request.environment,
            'status': 'triggered'
        }
        
        # Store in DynamoDB
        dynamodb_client = get_dynamodb_client()
        db_result = dynamodb_client.put_test_run(run_data)
        
        if not db_result['success']:
            raise HTTPException(
                status_code=500,
                detail=f'Failed to store test run: {db_result.get("error", "Unknown error")}'
            )
        
        # Trigger GitHub workflow
        github_client = get_github_client()
        
        # Map brand to repository and workflow
        repo_mapping = {
            'mweb': {
                'owner': 'mwebcode',
                'repo': 'hgc-frontend-tests',
                'workflow_id': 'run-tests.yml'
            },
            'webafrica': {
                'owner': 'mwebcode', 
                'repo': 'hgc-frontend-tests',
                'workflow_id': 'run-tests.yml'
            }
        }
        
        repo_config = repo_mapping.get(request.brand)
        if not repo_config:
            raise HTTPException(
                status_code=400,
                detail=f'No GitHub configuration found for brand: {request.brand}'
            )
        
        workflow_inputs = {
            'brand': request.brand,
            'environment': request.environment,
            'run_id': run_id
        }
        
        github_result = github_client.trigger_workflow(
            owner=repo_config['owner'],
            repo=repo_config['repo'],
            workflow_id=repo_config['workflow_id'],
            ref='main',
            inputs=workflow_inputs
        )
        
        if github_result['success']:
            # Update run data with GitHub info
            additional_data = {
                'githubRunId': github_result.get('run_id'),
                'status': 'running'
            }
            
            update_result = dynamodb_client.update_test_run_status(
                request.brand, run_id, 'running', additional_data
            )
            
            if not update_result['success']:
                # Log warning but don't fail the request
                print(f"Warning: Failed to update run status: {update_result.get('error')}")
        
        return {
            'runId': run_id,
            'brand': request.brand,
            'environment': request.environment,
            'status': 'triggered',
            'githubRunId': github_result.get('run_id'),
            'message': 'Test run triggered successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Internal server error: {str(e)}'
        )


@app.get("/results/{run_id}")
async def get_results(
    run_id: str,
    brand: Optional[str] = Query(None, description="Brand to search in (optional for efficiency)")
):
    """Get test results for a specific run"""
    
    try:
        # Initialize clients
        dynamodb_client = get_dynamodb_client()
        s3_client = get_s3_client()
        
        # Get test run metadata from DynamoDB
        if brand:
            # Efficient query by brand
            test_run = dynamodb_client.get_test_run(brand, run_id)
        else:
            # Less efficient - search across all brands
            all_brands = ['mweb', 'webafrica']
            test_run = None
            
            for b in all_brands:
                test_run = dynamodb_client.get_test_run(b, run_id)
                if test_run:
                    break
        
        if not test_run:
            raise HTTPException(
                status_code=404,
                detail=f'Test run not found: {run_id}'
            )
        
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
        
        return JSONResponse(
            content=json.loads(json.dumps(response_data, default=decimal_default))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Internal server error: {str(e)}'
        )


@app.post("/webhook")
async def webhook(request: Request):
    """Handle GitHub webhook events"""
    
    try:
        body = await request.body()
        headers = dict(request.headers)
        
        # Get GitHub event type
        github_event = headers.get('x-github-event', '')
        
        if github_event == 'workflow_run':
            # Parse webhook payload
            payload = json.loads(body.decode('utf-8'))
            
            # Extract run information
            workflow_run = payload.get('workflow_run', {})
            run_id = workflow_run.get('id')
            status = workflow_run.get('status')
            conclusion = workflow_run.get('conclusion')
            
            # Look for our run ID in the workflow name or inputs
            # This is a simplified implementation - you may need to adjust based on your workflow structure
            
            return {
                'message': 'Webhook received',
                'event': github_event,
                'status': status,
                'conclusion': conclusion
            }
        
        return {'message': 'Webhook received but not processed'}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Webhook processing error: {str(e)}'
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'service': 'hgc-frontend-tests-api'
    }