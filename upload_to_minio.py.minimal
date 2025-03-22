#!/usr/bin/env python3
"""
Upload Mesh File to MinIO

This script uploads a mesh file to MinIO and sets public read permissions for it.
"""

import os
import sys
import argparse
import logging
from minio import Minio
from minio.error import S3Error

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('upload_to_minio')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Upload mesh file to MinIO')
    parser.add_argument('mesh_file', help='Path to the mesh file to upload')
    parser.add_argument('--endpoint', required=True, help='MinIO endpoint (host:port)')
    parser.add_argument('--bucket', default='models', help='Bucket name')
    parser.add_argument('--access-key', required=True, help='MinIO access key')
    parser.add_argument('--secret-key', required=True, help='MinIO secret key')
    parser.add_argument('--secure', action='store_true', help='Use HTTPS')
    return parser.parse_args()

def upload_to_minio(mesh_file, endpoint, bucket_name, access_key, secret_key, secure=False):
    """Upload the mesh file to MinIO and return download URL."""
    try:
        # Initialize MinIO client
        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        logger.info(f"Connected to MinIO at {endpoint}")

        # Check if bucket exists, create if not
        if not client.bucket_exists(bucket_name):
            logger.info(f"Creating bucket: {bucket_name}")
            client.make_bucket(bucket_name)
            # Set bucket policy for public read access
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }
                ]
            }
            client.set_bucket_policy(bucket_name, policy)
            logger.info(f"Set public read policy for bucket: {bucket_name}")

        # Upload file
        object_name = os.path.basename(mesh_file)
        logger.info(f"Uploading {mesh_file} to bucket {bucket_name} as {object_name}")
        client.fput_object(bucket_name, object_name, mesh_file)
        
        # Construct the URL
        protocol = "https" if secure else "http"
        host_parts = endpoint.split(':')
        # If running in Docker, endpoint might be 'minio:9000' but needs to be mapped to host
        if host_parts[0] == 'minio':
            host_parts[0] = 'localhost'
        url = f"{protocol}://{':'.join(host_parts)}/{bucket_name}/{object_name}"
        
        logger.info(f"Upload successful. File accessible at: {url}")
        return url
    
    except S3Error as e:
        logger.error(f"Error uploading to MinIO: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

def main():
    """Main entry point."""
    args = parse_args()
    
    # Validate mesh file exists
    if not os.path.isfile(args.mesh_file):
        logger.error(f"Mesh file does not exist: {args.mesh_file}")
        return 1
    
    try:
        url = upload_to_minio(
            args.mesh_file,
            args.endpoint,
            args.bucket,
            args.access_key,
            args.secret_key,
            args.secure
        )
        logger.info(f"Mesh file uploaded and available at: {url}")
        return 0
    except Exception as e:
        logger.error(f"Failed to upload mesh file: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 