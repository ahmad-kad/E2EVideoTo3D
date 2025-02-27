import boto3
from botocore.client import Config
from typing import List, Dict, Any, Optional
import os
import json
import logging

logger = logging.getLogger(__name__)

class MinioClient:
    """Client for interacting with MinIO/S3 storage."""
    
    def __init__(
        self,
        endpoint_url: str = "http://localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        region: str = "us-east-1"
    ):
        """
        Initialize MinIO client.
        
        Args:
            endpoint_url: MinIO endpoint URL
            access_key: MinIO access key
            secret_key: MinIO secret key
            region: MinIO region
        """
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        
        # Initialize S3 client
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version='s3v4')
        )
        
        logger.info(f"Initialized MinIO client with endpoint {endpoint_url}")
    
    def create_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """
        Create a bucket if it doesn't exist.
        
        Args:
            bucket_name: Name of the bucket
            
        Returns:
            Response from S3 API
        """
        try:
            # Check if bucket already exists
            self.s3.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
            return {"status": "exists", "bucket": bucket_name}
        except:
            # Create the bucket
            response = self.s3.create_bucket(Bucket=bucket_name)
            logger.info(f"Created bucket {bucket_name}")
            return response
    
    def upload_file(self, file_path: str, bucket_name: str, object_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a file to a bucket.
        
        Args:
            file_path: Path to the file
            bucket_name: Name of the bucket
            object_name: Name of the object (defaults to file name)
            
        Returns:
            Response from S3 API
        """
        if object_name is None:
            object_name = os.path.basename(file_path)
            
        # Upload the file
        response = self.s3.upload_file(file_path, bucket_name, object_name)
        logger.info(f"Uploaded {file_path} to {bucket_name}/{object_name}")
        
        return {"status": "uploaded", "bucket": bucket_name, "object": object_name}
    
    def download_file(self, bucket_name: str, object_name: str, file_path: str) -> Dict[str, Any]:
        """
        Download a file from a bucket.
        
        Args:
            bucket_name: Name of the bucket
            object_name: Name of the object
            file_path: Path to save the file
            
        Returns:
            Response from S3 API
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Download the file
        self.s3.download_file(bucket_name, object_name, file_path)
        logger.info(f"Downloaded {bucket_name}/{object_name} to {file_path}")
        
        return {"status": "downloaded", "bucket": bucket_name, "object": object_name, "path": file_path}
    
    def list_objects(self, bucket_name: str, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List objects in a bucket.
        
        Args:
            bucket_name: Name of the bucket
            prefix: Prefix to filter objects
            
        Returns:
            List of object metadata
        """
        response = self.s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        
        objects = []
        if 'Contents' in response:
            for obj in response['Contents']:
                objects.append({
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat()
                })
        
        logger.info(f"Listed {len(objects)} objects in {bucket_name}/{prefix}")
        
        return objects
    
    def set_lifecycle_policy(self, bucket_name: str, prefix: str, days: int) -> Dict[str, Any]:
        """
        Set lifecycle policy for objects in a bucket.
        
        Args:
            bucket_name: Name of the bucket
            prefix: Prefix for objects to apply policy
            days: Number of days after which objects should be deleted
            
        Returns:
            Response from S3 API
        """
        lifecycle_config = {
            'Rules': [
                {
                    'ID': f'auto-delete-rule-{prefix}',
                    'Status': 'Enabled',
                    'Prefix': prefix,
                    'Expiration': {
                        'Days': days
                    }
                }
            ]
        }
        
        response = self.s3.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_config
        )
        
        logger.info(f"Set lifecycle policy for {bucket_name}/{prefix} to delete after {days} days")
        
        return response 