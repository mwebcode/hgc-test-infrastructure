#!/bin/bash
set -e

STAGE=${1:-prod}
AWS_PROFILE=${2:-mweb}
IAM_USER_NAME="github-actions-hgc-tests-${STAGE}"
POLICY_NAME="hgc-tests-github-actions-policy-${STAGE}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Deleting IAM user: ${IAM_USER_NAME}${NC}"
echo "AWS Profile: ${AWS_PROFILE}"

# Check if user exists
if ! aws iam get-user --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null; then
    echo -e "${YELLOW}IAM user ${IAM_USER_NAME} does not exist${NC}"
    exit 0
fi

# Confirm deletion
echo -e "${RED}⚠️  This will permanently delete the IAM user and all associated access keys!${NC}"
read -p "Are you sure you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

echo -e "${GREEN}Deleting IAM user components...${NC}"

# Delete access keys
echo "Deleting access keys..."
aws iam list-access-keys --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}" --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null | \
while read -r key; do
    if [ ! -z "$key" ] && [ "$key" != "None" ]; then
        echo "  Deleting key: $key"
        aws iam delete-access-key --user-name "${IAM_USER_NAME}" --access-key-id "$key" --profile "${AWS_PROFILE}"
    fi
done

# Delete inline policies
echo "Deleting policies..."
aws iam delete-user-policy --user-name "${IAM_USER_NAME}" --policy-name "${POLICY_NAME}" --profile "${AWS_PROFILE}" 2>/dev/null || true

# Delete user
echo "Deleting user..."
aws iam delete-user --user-name "${IAM_USER_NAME}" --profile "${AWS_PROFILE}"

echo -e "${GREEN}✅ IAM user deleted successfully${NC}"
echo
echo -e "${YELLOW}Remember to:${NC}"
echo "1. Remove AWS credentials from GitHub secrets"
echo "2. Update any documentation that references this user"