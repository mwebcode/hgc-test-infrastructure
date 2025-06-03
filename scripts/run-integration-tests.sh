#!/bin/bash

# Script to run integration tests against deployed API
# Usage: ./scripts/run-integration-tests.sh [dev|prod] [api-url] [api-key]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
ENVIRONMENT=""
API_URL=""
API_KEY=""

# Parse command line arguments
if [ $# -eq 1 ]; then
    ENVIRONMENT=$1
elif [ $# -eq 3 ]; then
    ENVIRONMENT=$1
    API_URL=$2
    API_KEY=$3
elif [ $# -eq 0 ]; then
    # Interactive mode
    echo "No arguments provided. Running in interactive mode..."
else
    echo "Usage: $0 [environment] [api-url] [api-key]"
    echo "       $0 dev"
    echo "       $0 prod"
    echo "       $0 dev https://api.example.com your-api-key"
    exit 1
fi

# If environment is provided but not URL/key, try to get from environment variables
if [ -n "$ENVIRONMENT" ] && [ -z "$API_URL" ]; then
    if [ "$ENVIRONMENT" = "dev" ]; then
        API_URL="${HGC_API_URL_DEV}"
        API_KEY="${HGC_API_KEY_DEV}"
    elif [ "$ENVIRONMENT" = "prod" ]; then
        API_URL="${HGC_API_URL_PROD}"
        API_KEY="${HGC_API_KEY_PROD}"
    else
        print_error "Invalid environment: $ENVIRONMENT. Must be 'dev' or 'prod'"
        exit 1
    fi
fi

# Interactive mode if still missing values
if [ -z "$API_URL" ]; then
    read -p "Enter API URL: " API_URL
fi

if [ -z "$API_KEY" ]; then
    read -s -p "Enter API Key: " API_KEY
    echo
fi

if [ -z "$API_URL" ] || [ -z "$API_KEY" ]; then
    print_error "API URL and API Key are required"
    exit 1
fi

print_status "Starting integration tests..."
print_status "Environment: ${ENVIRONMENT:-manual}"
print_status "API URL: $API_URL"
print_status "API Key: ${API_KEY:0:8}***"

# Check if we're in the right directory
if [ ! -f "tests/test_integration.py" ]; then
    print_error "Integration test file not found. Please run from the project root directory."
    exit 1
fi

# Check if required dependencies are installed
if ! python -c "import httpx" 2>/dev/null; then
    print_warning "httpx library not found. Installing..."
    pip install httpx
fi

# Run the integration tests
print_status "Running integration tests..."

if python tests/test_integration.py "$API_URL" "$API_KEY"; then
    print_status "✅ All integration tests passed!"
    
    # If this is after a deployment, save the success
    if [ -n "$ENVIRONMENT" ]; then
        echo "$(date): Integration tests passed for $ENVIRONMENT" >> "integration-test-log.txt"
    fi
    
    exit 0
else
    print_error "❌ Integration tests failed!"
    
    # If this is after a deployment, save the failure
    if [ -n "$ENVIRONMENT" ]; then
        echo "$(date): Integration tests FAILED for $ENVIRONMENT" >> "integration-test-log.txt"
    fi
    
    print_error "This indicates the API deployment has issues that need immediate attention."
    print_error "Common issues:"
    print_error "  - DynamoDB parameter errors (like the ScanIndexForward issue)"
    print_error "  - Missing environment variables"
    print_error "  - IAM permission issues"
    print_error "  - API Gateway configuration problems"
    
    exit 1
fi