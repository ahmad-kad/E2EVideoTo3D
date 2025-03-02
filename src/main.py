#!/usr/bin/env python3
"""
Main entry point for the photogrammetry pipeline.
This module provides a command-line interface to the pipeline functionality.
"""

import os
import sys
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if the environment is properly configured."""
    logger.info("Checking environment setup...")
    
    # Check GPU status
    use_gpu = os.environ.get('USE_GPU', '0') == '1'
    meshroom_binary = os.environ.get('MESHROOM_BINARY', 'meshroom_batch_cpu')
    
    logger.info(f"GPU enabled: {use_gpu}")
    logger.info(f"Using Meshroom binary: {meshroom_binary}")
    
    # Check if Meshroom is available
    try:
        import subprocess
        result = subprocess.run([meshroom_binary, "--help"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        if result.returncode == 0:
            logger.info("Meshroom is available and working correctly")
        else:
            logger.error(f"Meshroom check failed: {result.stderr}")
    except Exception as e:
        logger.error(f"Error checking Meshroom: {e}")
    
    return use_gpu

def test_minio_connection():
    """Test connection to MinIO storage."""
    try:
        import boto3
        from botocore.client import Config
        
        logger.info("Testing connection to MinIO...")
        
        # Connect to MinIO
        s3_client = boto3.client(
            's3',
            endpoint_url='http://minio:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin',
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
        
        # List buckets
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        logger.info(f"Available buckets: {buckets}")
        
        return True
    except Exception as e:
        logger.error(f"Error connecting to MinIO: {e}")
        return False

def main():
    """Main function to run the photogrammetry pipeline."""
    parser = argparse.ArgumentParser(description='Photogrammetry Pipeline')
    parser.add_argument('--check', action='store_true', help='Check environment and connections')
    parser.add_argument('--process', help='Process a video file from MinIO')
    
    args = parser.parse_args()
    
    logger.info("Starting photogrammetry pipeline")
    
    # Check environment setup
    use_gpu = check_environment()
    
    # Test MinIO connection
    minio_ok = test_minio_connection()
    
    if args.check:
        sys.exit(0 if minio_ok else 1)
    
    if args.process:
        logger.info(f"Processing video: {args.process}")
        # Here you would call your processing pipeline
        # For example: from src.ingestion.frame_extractor import extract_frames
        # extract_frames(args.process)
        logger.info("Processing not implemented in this basic version")
    
    logger.info("Photogrammetry pipeline initialized and ready")
    logger.info("To process a video, use --process option with a video file name")
    
    # If no specific action was requested, just display status
    if not (args.check or args.process):
        logger.info("No action specified. System is ready.")
        logger.info("Use --help for available options")

if __name__ == "__main__":
    main() 