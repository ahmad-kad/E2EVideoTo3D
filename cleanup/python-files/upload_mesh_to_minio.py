#!/usr/bin/env python3

import os
import sys
import json
import argparse
from minio import Minio
from minio.error import S3Error

def main():
    parser = argparse.ArgumentParser(description='Upload mesh file to MinIO')
    parser.add_argument('mesh_path', help='Path to the mesh file')
    parser.add_argument('--endpoint', default='minio:9000', help='MinIO endpoint')
    parser.add_argument('--bucket', default='models', help='Bucket name')
    parser.add_argument('--access-key', default='minioadmin', help='MinIO access key')
    parser.add_argument('--secret-key', default='minioadmin', help='MinIO secret key')
    parser.add_argument('--object-name', help='Name of object in MinIO (defaults to file basename)')
    args = parser.parse_args()

    # Check if mesh file exists
    if not os.path.exists(args.mesh_path):
        print(f"Error: Mesh file {args.mesh_path} does not exist")
        return 1

    try:
        # Create MinIO client
        client = Minio(
            args.endpoint,
            access_key=args.access_key,
            secret_key=args.secret_key,
            secure=False
        )

        # Make sure bucket exists
        if not client.bucket_exists(args.bucket):
            print(f"Bucket {args.bucket} does not exist, creating...")
            client.make_bucket(args.bucket)
            print(f"Bucket {args.bucket} created successfully")

        # Set bucket policy to allow public read access
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
        
        client.set_bucket_policy(args.bucket, json.dumps(policy))
        print(f"Public read access policy set for bucket {args.bucket}")

        # Determine object name
        object_name = args.object_name if args.object_name else os.path.basename(args.mesh_path)
        
        # Upload mesh file
        print(f"Uploading {args.mesh_path} to bucket {args.bucket} as {object_name}...")
        
        result = client.fput_object(
            args.bucket, object_name, args.mesh_path,
        )
        
        print(f"Successfully uploaded {object_name} to {result.bucket_name}")
        
        # Create download URL
        host_endpoint = args.endpoint
        if ":" in host_endpoint and not host_endpoint.startswith("http"):
            # Use localhost for the host part when using Docker
            if args.endpoint.startswith("minio:"):
                host_endpoint = args.endpoint.replace("minio:", "localhost:")
                
        download_url = f"http://{host_endpoint}/{args.bucket}/{object_name}"
        print(f"Download URL: {download_url}")
        
        return 0
    
    except S3Error as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 