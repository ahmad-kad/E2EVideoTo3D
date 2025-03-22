#!/usr/bin/env python3
"""
Upload mesh to MinIO for download

This script uploads the reconstructed mesh to MinIO storage for easy download.
"""

import os
import argparse
import logging
from minio import Minio
from minio.error import S3Error

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('upload_to_minio')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Upload Mesh to MinIO")
    
    parser.add_argument("mesh_file", help="Path to the mesh file to upload")
    parser.add_argument("--bucket", default="models", help="MinIO bucket name")
    parser.add_argument("--endpoint", default="localhost:9000", help="MinIO endpoint")
    parser.add_argument("--access-key", default="minioadmin", help="MinIO access key")
    parser.add_argument("--secret-key", default="minioadmin", help="MinIO secret key")
    parser.add_argument("--secure", action="store_true", help="Use secure (HTTPS) connection")
    
    return parser.parse_args()

def main():
    """Main function to upload mesh to MinIO."""
    args = parse_args()
    
    if not os.path.exists(args.mesh_file):
        logger.error(f"Mesh file not found: {args.mesh_file}")
        return 1
    
    # Create MinIO client
    try:
        client = Minio(
            args.endpoint,
            access_key=args.access_key,
            secret_key=args.secret_key,
            secure=args.secure
        )
        
        # Check if bucket exists, create if not
        if not client.bucket_exists(args.bucket):
            logger.info(f"Creating bucket: {args.bucket}")
            client.make_bucket(args.bucket)
            # Set bucket policy to allow downloads
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{args.bucket}/*"]
                    }
                ]
            }
            client.set_bucket_policy(args.bucket, policy)
        
        # Upload file
        filename = os.path.basename(args.mesh_file)
        logger.info(f"Uploading {args.mesh_file} to bucket '{args.bucket}' as {filename}")
        
        client.fput_object(
            args.bucket, 
            filename, 
            args.mesh_file,
            content_type="application/octet-stream"
        )
        
        # Get download URL
        download_url = f"http://{args.endpoint}/{args.bucket}/{filename}"
        logger.info(f"Upload successful. Download URL: {download_url}")
        
        return 0
        
    except S3Error as err:
        logger.error(f"MinIO error: {err}")
        return 1
    except Exception as err:
        logger.error(f"Error: {err}")
        return 1

if __name__ == "__main__":
    exit(main()) 