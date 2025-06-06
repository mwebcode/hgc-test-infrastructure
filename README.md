# HGC Frontend Test Infrastructure

AWS serverless infrastructure for automated frontend testing with GitHub Actions integration.

## Architecture

- **AWS Lambda**: API endpoints for triggering tests and retrieving results
- **API Gateway**: REST API with API key authentication  
- **DynamoDB**: Test run metadata storage with GSI for efficient querying
- **S3**: Test artifacts storage (reports, screenshots, videos, traces)
- **GitHub Actions**: Test execution via workflow dispatch

## API Endpoints

All endpoints require `X-Api-Key` header for authentication.

### Trigger Tests
```bash
POST /trigger-tests
Content-Type: application/json
X-Api-Key: <api-key>

{
  "brand": "mweb",
  "environment": "prod"
}
```

### Get Test Results
```bash
GET /results/{runId}?brand=mweb
X-Api-Key: <api-key>
```

### List Test Runs
```bash
GET /runs?brand=mweb&status=passed&limit=25
X-Api-Key: <api-key>
```

## Deployment

```bash
# Install dependencies
npm install

# Deploy to production
npm run deploy:prod

# Deploy to development
npm run deploy:dev
```

## Testing

### Unit Tests
```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
npm test

# Run specific test file
pytest tests/utils/test_github.py -v

# Run with coverage
npm run test:coverage
```

### Integration Tests

Integration tests verify the deployed API endpoints work correctly and can catch issues like DynamoDB parameter errors.

```bash
# Run integration tests using environment variables
export HGC_API_URL_DEV="https://your-api-gateway-url/dev"
export HGC_API_KEY_DEV="your-dev-api-key"
./scripts/run-integration-tests.sh dev

# Run integration tests with explicit parameters
./scripts/run-integration-tests.sh dev https://api.example.com your-api-key

# Run in interactive mode
./scripts/run-integration-tests.sh

# Run via pytest (requires environment variables)
pytest tests/test_integration.py::test_dev_environment -v
```

#### GitHub Actions Integration Tests

Integration tests run automatically:
- **On every push/PR**: Tests dev environment
- **Every 6 hours**: Scheduled health check  
- **Manual trigger**: Can test dev or prod environment
- **Post-deployment**: Smoke tests after deployment

Required GitHub secrets:
- `HGC_API_URL_DEV` - Dev environment API URL
- `HGC_API_KEY_DEV` - Dev environment API key  
- `HGC_API_URL_PROD` - Prod environment API URL
- `HGC_API_KEY_PROD` - Prod environment API key

#### What Integration Tests Catch

- **DynamoDB parameter errors** (like the ScanIndexForward issue)
- **API Gateway configuration issues**
- **IAM permission problems**  
- **Missing environment variables**
- **CORS header configuration**
- **API key authentication**
- **Response format validation**

## Configuration

The infrastructure uses:
- **API Key**: Stored in SSM Parameter Store
- **GitHub Token**: Stored in SSM Parameter Store
- **Environment Variables**: Stage-specific configuration

## Security

- API key authentication on all endpoints
- GitHub token stored as SecureString in SSM
- IAM roles with least privilege principle
- S3 bucket with public access blocked
- DynamoDB with TTL for automatic cleanup