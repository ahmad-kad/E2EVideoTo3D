#!/usr/bin/env python3

import os
import sys
import json
import argparse
from minio import Minio
from minio.error import S3Error

def main():
    parser = argparse.ArgumentParser(description='Upload a file to MinIO')
    parser.add_argument('file_path', help='Path to the file to upload')
    parser.add_argument('--endpoint', default='localhost:9000', help='MinIO endpoint')
    parser.add_argument('--bucket', default='models', help='Bucket name')
    parser.add_argument('--access-key', default='minioadmin', help='Access key')
    parser.add_argument('--secret-key', default='minioadmin', help='Secret key')
    args = parser.parse_args()

    # Check if file exists
    if not os.path.exists(args.file_path):
        print(f"Error: File {args.file_path} does not exist")
        return 1

    try:
        # Create MinIO client
        client = Minio(
            args.endpoint,
            access_key=args.access_key,
            secret_key=args.secret_key,
            secure=False
        )

        # Check if bucket exists, create if not
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

        # Get file name from path
        file_name = os.path.basename(args.file_path)
        
        # Upload file
        print(f"Uploading {args.file_path} to bucket {args.bucket} as {file_name}...")
        
        result = client.fput_object(
            args.bucket, file_name, args.file_path,
        )
        
        print(f"Successfully uploaded {file_name} to {result.bucket_name}")
        print(f"Download URL: http://{args.endpoint}/{result.bucket_name}/{file_name}")
        
        return 0
    
    except S3Error as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 