#!/bin/bash
set -e

# Configuration
STAGE=${1:-prod}
REGION=${2:-af-south-1}
AWS_PROFILE=${3:-mweb}
IAM_USER_NAME="github-actions-hgc-tests-${STAGE}"
POLICY_NAME="hgc-tests-github-actions-policy-${STAGE}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up IAM user for GitHub Actions...${NC}"
echo "Stage: ${STAGE}"
echo "Region: ${REGION}"
echo "AWS Profile: ${AWS_PROFILE}"
echo "IAM User: ${IAM_USER_NAME}"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --profile "${AWS_PROFILE}" --query Account --output text)
echo "AWS Account ID: ${ACCOUNT_ID}"

# Get bucket and table names from serverless outputs (if deployed)
BUCKET_NAME="hgc-test-results-${STAGE}"
TABLE_NAME="hgc-test-runs-${STAGE}"

# Check if user already exists
if aws iam get-user --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null; then
    echo -e "${YELLOW}IAM user ${IAM_USER_NAME} already exists${NC}"
    read -p "Do you want to recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing user..."
        # Delete access keys first
        aws iam list-access-keys --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}" --query 'AccessKeyMetadata[].AccessKeyId' --output text | \
        while read -r key; do
            if [ ! -z "$key" ]; then
                echo "  Deleting access key: $key"
                aws iam delete-access-key --user-name "${IAM_USER_NAME}" --access-key-id "$key" --profile "${AWS_PROFILE}"
            fi
        done
        # Delete inline policies
        aws iam delete-user-policy --user-name "${IAM_USER_NAME}" --policy-name "${POLICY_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null || true
        # Delete user
        aws iam delete-user --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}"
    else
        exit 1
    fi
fi

# Create IAM user
echo -e "${GREEN}Creating IAM user...${NC}"
aws iam create-user --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}" \
    --tags Key=Purpose,Value=GitHubActions Key=Project,Value=HGCFrontendTests Key=Stage,Value="${STAGE}"

# Create IAM policy
echo -e "${GREEN}Creating IAM policy...${NC}"
cat > /tmp/github-actions-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3UploadAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}/reports/*",
        "arn:aws:s3:::${BUCKET_NAME}/artifacts/*",
        "arn:aws:s3:::${BUCKET_NAME}/metadata/*"
      ]
    },
    {
      "Sid": "DynamoDBWriteAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}"
    },
    {
      "Sid": "DynamoDBWriteIndexAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}/index/*"
    }
  ]
}
EOF

# Attach inline policy to user
aws iam put-user-policy \
    --user-name "${IAM_USER_NAME}" \
    --policy-name "${POLICY_NAME}" \
    --policy-document file:///tmp/github-actions-policy.json \
    --profile "${AWS_PROFILE}"

# Create access keys
echo -e "${GREEN}Creating access keys...${NC}"
CREDENTIALS=$(aws iam create-access-key --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}" --output json)

ACCESS_KEY_ID=$(echo "$CREDENTIALS" | jq -r '.AccessKey.AccessKeyId')
SECRET_ACCESS_KEY=$(echo "$CREDENTIALS" | jq -r '.AccessKey.SecretAccessKey')

# Clean up temp file
rm /tmp/github-actions-policy.json

# Output credentials
echo -e "${GREEN}✅ IAM user created successfully!${NC}"
echo
echo -e "${YELLOW}=== GitHub Secrets Configuration ===${NC}"
echo "Add these secrets to your GitHub repository:"
echo "Repository URL: https://github.com/mwebcode/hgc-frontend-tests/settings/secrets/actions"
echo
echo "FRONTEND_TESTS_AWS_ACCESS_KEY_ID=${ACCESS_KEY_ID}"
echo "FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY=${SECRET_ACCESS_KEY}"
echo "FRONTEND_TESTS_AWS_DEFAULT_REGION=${REGION}"
echo "FRONTEND_TESTS_AWS_S3_BUCKET=${BUCKET_NAME}"
echo "FRONTEND_TESTS_AWS_DYNAMODB_TABLE=${TABLE_NAME}"
echo
echo -e "${YELLOW}=== Security Note ===${NC}"
echo "These credentials will only be shown once. Store them securely!"
echo

# Optional: Save to file
read -p "Save credentials to file? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CREDS_FILE="github-actions-creds-${STAGE}-$(date +%Y%m%d%H%M%S).txt"
    cat > "$CREDS_FILE" <<EOF
# GitHub Actions AWS Credentials
# Created: $(date)
# Stage: ${STAGE}
# Region: ${REGION}
# User: ${IAM_USER_NAME}

FRONTEND_TESTS_AWS_ACCESS_KEY_ID=${ACCESS_KEY_ID}
FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY=${SECRET_ACCESS_KEY}
FRONTEND_TESTS_AWS_DEFAULT_REGION=${REGION}
FRONTEND_TESTS_AWS_S3_BUCKET=${BUCKET_NAME}
FRONTEND_TESTS_AWS_DYNAMODB_TABLE=${TABLE_NAME}
EOF
    chmod 600 "$CREDS_FILE"
    echo -e "${GREEN}Credentials saved to: ${CREDS_FILE}${NC}"
    echo -e "${RED}⚠️  Delete this file after adding to GitHub secrets!${NC}"
fi

# Optional: Configure GitHub CLI
if command -v gh &> /dev/null; then
    echo
    read -p "Configure GitHub secrets using GitHub CLI? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Configuring GitHub secrets...${NC}"
        
        # Check if we're in the right directory
        if [ ! -d "../hgc-frontend-tests" ]; then
            echo -e "${YELLOW}hgc-frontend-tests directory not found at ../hgc-frontend-tests${NC}"
            echo "Please navigate to the directory containing both repositories and run this script again,"
            echo "or manually add the secrets to GitHub."
            echo
        else
            cd ../hgc-frontend-tests || { echo "Failed to navigate to hgc-frontend-tests directory"; exit 1; }
            
            gh secret set FRONTEND_TESTS_AWS_ACCESS_KEY_ID --body "${ACCESS_KEY_ID}"
            gh secret set FRONTEND_TESTS_AWS_SECRET_ACCESS_KEY --body "${SECRET_ACCESS_KEY}"
            gh secret set FRONTEND_TESTS_AWS_DEFAULT_REGION --body "${REGION}"
            gh secret set FRONTEND_TESTS_AWS_S3_BUCKET --body "${BUCKET_NAME}"
            gh secret set FRONTEND_TESTS_AWS_DYNAMODB_TABLE --body "${TABLE_NAME}"
            
            echo -e "${GREEN}✅ GitHub secrets configured successfully!${NC}"
            cd - > /dev/null
        fi
    fi
fi

echo
echo -e "${GREEN}Setup complete!${NC}"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Add the credentials to GitHub secrets (if not done automatically)"
echo "2. Deploy the infrastructure: npm run deploy:${STAGE}"
echo "3. Update the GitHub Actions workflow in hgc-frontend-tests"
echo "4. Test the setup by triggering a workflow"