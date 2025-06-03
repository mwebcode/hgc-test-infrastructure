import os
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import mimetypes


class S3Client:
    def __init__(self):
        self.bucket_name = os.environ.get('S3_BUCKET')
        if not self.bucket_name:
            raise ValueError("S3 bucket name not found in environment variables")
        
        self.s3 = boto3.client('s3')

    def generate_presigned_url(self, object_key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for S3 object access
        """
        try:
            response = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {str(e)}")

    def list_objects(self, prefix: str, max_keys: int = 1000) -> List[Dict[str, Any]]:
        """
        List objects in S3 bucket with given prefix
        """
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'lastModified': obj['LastModified'].isoformat(),
                        'etag': obj['ETag'].strip('"')
                    })
            
            return objects
        except ClientError as e:
            raise Exception(f"Failed to list objects: {str(e)}")

    def get_object_info(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata about an S3 object
        """
        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=object_key)
            return {
                'size': response['ContentLength'],
                'lastModified': response['LastModified'].isoformat(),
                'contentType': response.get('ContentType', 'unknown'),
                'etag': response['ETag'].strip('"')
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise Exception(f"Failed to get object info: {str(e)}")

    def build_test_results_structure(self, brand: str, environment: str, timestamp: str) -> Dict[str, str]:
        """
        Build the expected S3 path structure for test results
        """
        prefix = f"{brand}/{environment}/{timestamp}"
        
        return {
            'reports_prefix': f"reports/{prefix}/",
            'artifacts_prefix': f"artifacts/{prefix}/",
            'metadata_prefix': f"metadata/{prefix}/",
            'html_report': f"reports/{prefix}/index.html",
            'metadata_file': f"metadata/{prefix}/metadata.json"
        }

    def get_test_artifacts(self, brand: str, environment: str, timestamp: str) -> Dict[str, Any]:
        """
        Get all artifacts for a specific test run
        """
        paths = self.build_test_results_structure(brand, environment, timestamp)
        
        artifacts = {
            'reports': [],
            'screenshots': [],
            'videos': [],
            'traces': [],
            'metadata': None,
            'html_report_url': None
        }
        
        try:
            # Get HTML report URL if it exists
            if self.get_object_info(paths['html_report']):
                artifacts['html_report_url'] = self.generate_presigned_url(paths['html_report'])
            
            # Get metadata
            metadata_file = paths['metadata_file']
            if self.get_object_info(metadata_file):
                artifacts['metadata'] = self.generate_presigned_url(metadata_file)
            
            # Get report files
            report_objects = self.list_objects(paths['reports_prefix'])
            for obj in report_objects:
                artifacts['reports'].append({
                    'key': obj['key'],
                    'url': self.generate_presigned_url(obj['key']),
                    'size': obj['size'],
                    'lastModified': obj['lastModified']
                })
            
            # Get artifact files
            artifact_objects = self.list_objects(paths['artifacts_prefix'])
            for obj in artifact_objects:
                key = obj['key']
                file_info = {
                    'key': key,
                    'url': self.generate_presigned_url(key),
                    'size': obj['size'],
                    'lastModified': obj['lastModified']
                }
                
                # Categorize by file type
                if key.endswith(('.png', '.jpg', '.jpeg')):
                    artifacts['screenshots'].append(file_info)
                elif key.endswith(('.webm', '.mp4')):
                    artifacts['videos'].append(file_info)
                elif key.endswith('.zip'):
                    artifacts['traces'].append(file_info)
                else:
                    artifacts['reports'].append(file_info)
            
            return artifacts
            
        except Exception as e:
            raise Exception(f"Failed to get test artifacts: {str(e)}")

    def check_bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible
        """
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise Exception(f"Failed to check bucket: {str(e)}")

    def get_bucket_size(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        Get bucket size and object count for monitoring
        """
        try:
            kwargs = {'Bucket': self.bucket_name}
            if prefix:
                kwargs['Prefix'] = prefix
                
            paginator = self.s3.get_paginator('list_objects_v2')
            
            total_size = 0
            total_count = 0
            
            for page in paginator.paginate(**kwargs):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size += obj['Size']
                        total_count += 1
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'total_objects': total_count
            }
            
        except ClientError as e:
            raise Exception(f"Failed to get bucket size: {str(e)}")