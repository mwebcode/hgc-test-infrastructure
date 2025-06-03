# Cost Analysis: HGC Frontend Test Infrastructure

## Overview

This document provides a comprehensive cost analysis for running the HGC frontend test infrastructure, including GitHub Actions workflow execution and AWS serverless components.

## GitHub Actions Costs

### Free Tier Limits
- **2,000 minutes/month** for private repositories
- **Unlimited minutes** for public repositories
- **500MB storage** for artifacts and logs

### Paid Pricing (Private Repositories)
- **$0.008/minute** for Linux runners
- **$0.016/minute** for Windows runners
- **$0.064/minute** for macOS runners
- **$0.25/GB/month** for artifact storage beyond free tier

### Typical Test Run Duration
- **Frontend tests**: 5-15 minutes per run
- **Multiple environments**: 2-3x longer for parallel execution
- **Artifact upload**: Additional 1-2 minutes

## AWS Infrastructure Costs

### API Gateway
- **$3.50 per million requests** (first 333 million)
- **$2.76 per million requests** (next 667 million)
- **$1.60 per million requests** (next 19 billion)
- **$0.09/GB** for data transfer out

### AWS Lambda
- **$0.20 per 1 million requests**
- **$0.0000166667 per GB-second** of compute time
- **First 1 million requests free** per month
- **First 400,000 GB-seconds free** per month

### Amazon DynamoDB
- **On-Demand Pricing:**
  - **$1.25 per million write requests**
  - **$0.25 per million read requests**
  - **$0.25/GB/month** for storage
- **Free Tier:** 25 GB storage, 2.5M read requests, 1M write requests

### Amazon S3
- **Standard Storage:**
  - **$0.023/GB/month** for first 50TB
  - **$0.022/GB/month** for next 450TB
- **Requests:**
  - **$0.0004 per 1,000 PUT requests**
  - **$0.0004 per 1,000 GET requests**
- **Data Transfer:**
  - **$0.09/GB** for first 10TB out to internet

### SSM Parameter Store
- **Standard parameters**: Free
- **Advanced parameters**: $0.05 per 10,000 requests

## Cost Estimation Scenarios

### Low Usage (25 test runs/month)
| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| GitHub Actions | 25 runs × 10 min | $2.00 |
| API Gateway | 250 requests | $0.00 |
| Lambda | 250 invocations | $0.00 |
| DynamoDB | 250 writes, 500 reads | $0.00 |
| S3 | 5GB storage, 250 uploads | $0.23 |
| **Total** | | **~$2.23** |

### Medium Usage (100 test runs/month)
| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| GitHub Actions | 100 runs × 10 min | $8.00 |
| API Gateway | 1,000 requests | $0.00 |
| Lambda | 1,000 invocations | $0.00 |
| DynamoDB | 1,000 writes, 2,000 reads | $0.00 |
| S3 | 20GB storage, 1,000 uploads | $0.86 |
| **Total** | | **~$8.86** |

### High Usage (500 test runs/month)
| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| GitHub Actions | 500 runs × 10 min | $40.00 |
| API Gateway | 5,000 requests | $0.02 |
| Lambda | 5,000 invocations | $0.00 |
| DynamoDB | 5,000 writes, 10,000 reads | $8.75 |
| S3 | 100GB storage, 5,000 uploads | $4.30 |
| **Total** | | **~$53.07** |

### Enterprise Usage (2,000 test runs/month)
| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| GitHub Actions | 2,000 runs × 12 min | $192.00 |
| API Gateway | 20,000 requests | $0.07 |
| Lambda | 20,000 invocations | $0.00 |
| DynamoDB | 20,000 writes, 40,000 reads | $35.00 |
| S3 | 400GB storage, 20,000 uploads | $17.20 |
| **Total** | | **~$244.27** |

## Cost Optimization Strategies

### GitHub Actions Optimization
1. **Use public repositories** for unlimited free minutes
2. **Optimize test parallelization** to reduce total runtime
3. **Set artifact retention** to 7-30 days maximum
4. **Use self-hosted runners** for high-volume usage
5. **Cache dependencies** to reduce setup time

### AWS Cost Optimization
1. **DynamoDB TTL**: Auto-delete old records after 90 days
2. **S3 Lifecycle Policies**: 
   - Move to IA after 30 days
   - Move to Glacier after 90 days
   - Delete after 1 year
3. **Lambda optimization**: Right-size memory allocation
4. **API Gateway caching**: Reduce backend calls
5. **Reserved capacity**: For predictable high usage

### Monitoring and Alerting
1. **AWS Cost Explorer**: Track spending trends
2. **Billing alerts**: Set up notifications at $10, $50, $100
3. **GitHub usage reports**: Monitor Action minutes
4. **Resource tagging**: Track costs by environment/team

## Sample S3 Lifecycle Policy

```json
{
    "Rules": [
        {
            "Id": "TestArtifactLifecycle",
            "Status": "Enabled",
            "Filter": {"Prefix": "artifacts/"},
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "Expiration": {
                "Days": 365
            }
        }
    ]
}
```

## Cost Monitoring Commands

```bash
# Check AWS costs
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost

# GitHub Actions usage (via API)
gh api /repos/mwebcode/hgc-frontend-tests/actions/billing/usage

# DynamoDB table size
aws dynamodb describe-table \
  --table-name hgc-test-runs-prod \
  --query 'Table.TableSizeBytes'
```

## Recommendations

### For Development Teams
- Start with **public repositories** to minimize GitHub Actions costs
- Use **25-50 test runs/month** budget for initial setup
- Monitor costs weekly during ramp-up phase

### For Production Usage
- Budget **$50-100/month** for moderate usage (200-500 runs)
- Implement **automated cost alerting** at multiple thresholds
- Review and optimize **quarterly** based on usage patterns

### For Enterprise Scale
- Consider **GitHub Enterprise** for volume discounts
- Use **AWS Reserved Instances** for predictable workloads
- Implement **comprehensive cost allocation** by team/project

---

*Last updated: December 2024*
*For current AWS pricing, visit: https://aws.amazon.com/pricing/*
*For current GitHub pricing, visit: https://github.com/pricing*