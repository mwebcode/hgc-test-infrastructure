#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}GitHub CLI (gh) is not installed. Please install it first:${NC}"
    echo "https://cli.github.com/"
    exit 1
fi

# Check if credentials file exists
CREDS_FILE=$1
if [ -z "$CREDS_FILE" ]; then
    echo "Usage: ./setup-github-secrets.sh <credentials-file>"
    echo
    echo "Example:"
    echo "  ./setup-github-secrets.sh github-actions-creds-prod-20250603140000.txt"
    exit 1
fi

if [ ! -f "$CREDS_FILE" ]; then
    echo -e "${RED}Credentials file not found: $CREDS_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Setting up GitHub secrets from: $CREDS_FILE${NC}"

# Source the credentials
source "$CREDS_FILE"

# Verify required variables are set
if [ -z "$FRONTEND_TESTS_AWS_ACCESS_KEY_ID" ] || [ -z "$FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY" ] || [ -z "$FRONTEND_TESTS_AWS_DEFAULT_REGION" ] || [ -z "$FRONTEND_TESTS_AWS_S3_BUCKET" ] || [ -z "$FRONTEND_TESTS_AWS_DYNAMODB_TABLE" ]; then
    echo -e "${RED}Error: Missing required environment variables in credentials file${NC}"
    echo "Required variables: FRONTEND_TESTS_AWS_ACCESS_KEY_ID, FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY, FRONTEND_TESTS_AWS_DEFAULT_REGION, FRONTEND_TESTS_AWS_S3_BUCKET, FRONTEND_TESTS_AWS_DYNAMODB_TABLE"
    exit 1
fi

# Check if we're in the right directory or navigate to it
if [ ! -d ".git" ] || ! git remote get-url origin | grep -q "hgc-frontend-tests"; then
    if [ -d "../hgc-frontend-tests" ]; then
        echo -e "${YELLOW}Navigating to hgc-frontend-tests directory...${NC}"
        cd ../hgc-frontend-tests
    else
        echo -e "${RED}Error: Not in hgc-frontend-tests repository and can't find it at ../hgc-frontend-tests${NC}"
        echo "Please run this script from within the hgc-frontend-tests repository"
        exit 1
    fi
fi

# Verify we're in the right repo
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "unknown")
if [ "$REPO" != "mwebcode/hgc-frontend-tests" ]; then
    echo -e "${RED}Wrong repository. Expected: mwebcode/hgc-frontend-tests, Got: $REPO${NC}"
    echo "Please navigate to the correct repository"
    exit 1
fi

# Set GitHub secrets
echo -e "${GREEN}Setting GitHub secrets for $REPO...${NC}"

echo "  Setting FRONTEND_TESTS_AWS_ACCESS_KEY_ID..."
gh secret set FRONTEND_TESTS_AWS_ACCESS_KEY_ID --body "${FRONTEND_TESTS_AWS_ACCESS_KEY_ID}"

echo "  Setting FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY..."
gh secret set FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY --body "${FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY}"

echo "  Setting FRONTEND_TESTS_AWS_DEFAULT_REGION..."
gh secret set FRONTEND_TESTS_AWS_DEFAULT_REGION --body "${FRONTEND_TESTS_AWS_DEFAULT_REGION}"

echo "  Setting FRONTEND_TESTS_AWS_S3_BUCKET..."
gh secret set FRONTEND_TESTS_AWS_S3_BUCKET --body "${FRONTEND_TESTS_AWS_S3_BUCKET}"

echo "  Setting FRONTEND_TESTS_AWS_DYNAMODB_TABLE..."
gh secret set FRONTEND_TESTS_AWS_DYNAMODB_TABLE --body "${FRONTEND_TESTS_AWS_DYNAMODB_TABLE}"

echo
echo -e "${GREEN}✅ GitHub secrets configured successfully!${NC}"
echo
echo -e "${YELLOW}Configured secrets:${NC}"
echo "  FRONTEND_TESTS_AWS_ACCESS_KEY_ID"
echo "  FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY"
echo "  FRONTEND_TESTS_AWS_DEFAULT_REGION: ${FRONTEND_TESTS_AWS_DEFAULT_REGION}"
echo "  FRONTEND_TESTS_AWS_S3_BUCKET: ${FRONTEND_TESTS_AWS_S3_BUCKET}"
echo "  FRONTEND_TESTS_AWS_DYNAMODB_TABLE: ${FRONTEND_TESTS_AWS_DYNAMODB_TABLE}"
echo
echo -e "${RED}⚠️  Security reminder:${NC}"
echo "Remember to delete the credentials file: rm $CREDS_FILE"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Update GitHub Actions workflow to use these secrets"
echo "2. Test the workflow by triggering a test run"
echo "3. Verify results are uploaded to S3 and stored in DynamoDB"