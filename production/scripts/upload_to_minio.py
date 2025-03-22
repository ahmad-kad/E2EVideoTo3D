#!/usr/bin/env python3
"""
E2E3D File Upload Service

This script provides functionality for uploading files to MinIO/S3 storage.
It handles retries, error handling, and setting proper access permissions.
"""

import os
import sys
import time
import uuid
import logging
import argparse
import mimetypes
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Union

# S3 client imports with fallbacks
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Configurable settings
MAX_RETRIES = int(os.environ.get('E2E3D_UPLOAD_MAX_RETRIES', '3'))
RETRY_DELAY = float(os.environ.get('E2E3D_UPLOAD_RETRY_DELAY', '1.0'))
MAX_WORKERS = int(os.environ.get('E2E3D_UPLOAD_MAX_WORKERS', '4'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('e2e3d.upload')

class UploadError(Exception):
    """Custom exception for upload errors."""
    pass

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Upload files to MinIO/S3 storage')
    parser.add_argument('files', nargs='+', help='Files to upload (can use glob patterns)')
    parser.add_argument('--endpoint', required=True, help='MinIO/S3 endpoint (host:port)')
    parser.add_argument('--bucket', default='models', help='Bucket name')
    parser.add_argument('--prefix', default='', help='Object name prefix')
    parser.add_argument('--access-key', required=True, help='Access key')
    parser.add_argument('--secret-key', required=True, help='Secret key')
    parser.add_argument('--region', default='us-east-1', help='Region (for S3)')
    parser.add_argument('--secure', action='store_true', help='Use HTTPS')
    parser.add_argument('--public', action='store_true', help='Make objects publicly readable')
    parser.add_argument('--flatten', action='store_true', help='Flatten directory structure')
    parser.add_argument('--content-type', help='Force content type for all files')
    parser.add_argument('--metadata', help='Metadata in key=value format, can be used multiple times', 
                       action='append', default=[])
    parser.add_argument('--batch', action='store_true', help='Batch upload using multiple threads')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    return parser.parse_args()

def get_object_name(file_path: str, prefix: str = '', flatten: bool = False) -> str:
    """
    Determine object name based on file path and prefix.
    
    Args:
        file_path: Path to the file
        prefix: Optional prefix for the object name
        flatten: Whether to flatten directory structure
        
    Returns:
        S3 object name
    """
    if flatten:
        object_name = os.path.basename(file_path)
    else:
        # Use relative path as object name
        object_name = file_path
        # Remove leading ./ or / if present
        if object_name.startswith('./'):
            object_name = object_name[2:]
        elif object_name.startswith('/'):
            object_name = object_name[1:]
    
    # Add prefix if specified
    if prefix:
        # Ensure prefix ends with a slash
        if not prefix.endswith('/'):
            prefix += '/'
        object_name = prefix + object_name
    
    return object_name

def guess_content_type(file_path: str) -> str:
    """
    Guess content type based on file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Content type string
    """
    content_type, _ = mimetypes.guess_type(file_path)
    
    # Default to binary if content type cannot be determined
    if content_type is None:
        # Special handling for some common 3D file formats
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.obj':
            content_type = 'model/obj'
        elif ext == '.ply':
            content_type = 'application/ply'
        elif ext == '.stl':
            content_type = 'model/stl'
        elif ext == '.glb':
            content_type = 'model/gltf-binary'
        elif ext == '.gltf':
            content_type = 'model/gltf+json'
        else:
            content_type = 'application/octet-stream'
    
    return content_type

def parse_metadata(metadata_args: List[str]) -> Dict[str, str]:
    """
    Parse metadata arguments into a dictionary.
    
    Args:
        metadata_args: List of key=value strings
        
    Returns:
        Dictionary of metadata
    """
    metadata = {}
    for item in metadata_args:
        if '=' in item:
            key, value = item.split('=', 1)
            metadata[key.strip()] = value.strip()
    
    return metadata

def upload_with_minio(
    file_path: str,
    object_name: str,
    endpoint: str,
    bucket_name: str,
    access_key: str,
    secret_key: str,
    region: str = 'us-east-1',
    secure: bool = False,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    public: bool = False
) -> str:
    """
    Upload a file using MinIO client.
    
    Args:
        file_path: Path to the file to upload
        object_name: Name of the object in the bucket
        endpoint: MinIO endpoint (host:port)
        bucket_name: Name of the bucket
        access_key: MinIO access key
        secret_key: MinIO secret key
        region: Region (default: us-east-1)
        secure: Whether to use HTTPS
        content_type: Content type of the file
        metadata: Additional metadata
        public: Whether to make the object publicly readable
        
    Returns:
        URL of the uploaded object
        
    Raises:
        UploadError: If upload fails
    """
    if not MINIO_AVAILABLE:
        raise UploadError("MinIO client is not available. Please install the minio package.")
    
    # Determine content type if not provided
    if content_type is None:
        content_type = guess_content_type(file_path)
    
    # Initialize metadata if None
    metadata = metadata or {}
    
    try:
        # Initialize MinIO client
        client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            secure=secure
        )
        logger.debug(f"Connected to MinIO at {endpoint}")
        
        # Check if bucket exists, create if not
        if not client.bucket_exists(bucket_name):
            logger.info(f"Creating bucket: {bucket_name}")
            client.make_bucket(bucket_name)
        
        # Set bucket policy for public read access if requested
        if public:
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
            try:
                client.set_bucket_policy(bucket_name, policy)
                logger.debug(f"Set public read policy for bucket: {bucket_name}")
            except S3Error as e:
                logger.warning(f"Failed to set bucket policy: {e}")
        
        # Upload the file with retries
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Uploading {file_path} to bucket {bucket_name} as {object_name} (attempt {attempt+1})")
                
                # Upload the file
                client.fput_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    file_path=file_path,
                    content_type=content_type,
                    metadata=metadata
                )
                
                # Construct the URL
                protocol = "https" if secure else "http"
                url_endpoint = endpoint
                
                # If running in Docker, endpoint might be 'minio:9000' but needs to be mapped to host
                # Try to handle this common case
                parsed = urlparse(f"{protocol}://{endpoint}")
                if parsed.hostname in ['minio', 'localhost', '127.0.0.1']:
                    url_endpoint = f"localhost:{parsed.port}"
                
                url = f"{protocol}://{url_endpoint}/{bucket_name}/{object_name}"
                
                logger.info(f"Upload successful: {object_name}")
                return url
                
            except S3Error as e:
                logger.warning(f"Upload attempt {attempt+1} failed: {e}")
                
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                else:
                    raise UploadError(f"Failed to upload {file_path} after {MAX_RETRIES} attempts: {e}")
    
    except S3Error as e:
        raise UploadError(f"MinIO error: {e}")
    except Exception as e:
        raise UploadError(f"Unexpected error: {e}")

def upload_with_boto3(
    file_path: str,
    object_name: str,
    endpoint: str,
    bucket_name: str,
    access_key: str,
    secret_key: str,
    region: str = 'us-east-1',
    secure: bool = False,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    public: bool = False
) -> str:
    """
    Upload a file using boto3 client.
    
    Args:
        Same as upload_with_minio
        
    Returns:
        URL of the uploaded object
        
    Raises:
        UploadError: If upload fails
    """
    if not BOTO3_AVAILABLE:
        raise UploadError("boto3 is not available. Please install the boto3 package.")
    
    # Determine content type if not provided
    if content_type is None:
        content_type = guess_content_type(file_path)
    
    # Initialize metadata if None
    metadata = metadata or {}
    
    # Prepare S3 client parameters
    protocol = "https" if secure else "http"
    endpoint_url = f"{protocol}://{endpoint}"
    
    # Extra kwargs for upload_file
    extra_args = {
        'ContentType': content_type,
        'Metadata': metadata,
    }
    
    # Add public-read ACL if requested
    if public:
        extra_args['ACL'] = 'public-read'
    
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            # Use path style addressing for MinIO compatibility
            config=boto3.session.Config(signature_version='s3v4', s3={'addressing_style': 'path'})
        )
        
        # Create bucket if it doesn't exist
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"Creating bucket: {bucket_name}")
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                raise
        
        # Upload the file with retries
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Uploading {file_path} to bucket {bucket_name} as {object_name} (attempt {attempt+1})")
                
                # Upload the file
                s3_client.upload_file(
                    Filename=file_path,
                    Bucket=bucket_name,
                    Key=object_name,
                    ExtraArgs=extra_args
                )
                
                # Construct the URL
                # If running in Docker, endpoint might be 'minio:9000' but needs to be mapped to host
                parsed = urlparse(endpoint_url)
                if parsed.hostname in ['minio', 'localhost', '127.0.0.1']:
                    url_endpoint = f"localhost:{parsed.port}"
                else:
                    url_endpoint = endpoint
                
                url = f"{protocol}://{url_endpoint}/{bucket_name}/{object_name}"
                
                logger.info(f"Upload successful: {object_name}")
                return url
                
            except ClientError as e:
                logger.warning(f"Upload attempt {attempt+1} failed: {e}")
                
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                else:
                    raise UploadError(f"Failed to upload {file_path} after {MAX_RETRIES} attempts: {e}")
    
    except ClientError as e:
        raise UploadError(f"S3 error: {e}")
    except Exception as e:
        raise UploadError(f"Unexpected error: {e}")

def upload_to_minio(
    file_path: str,
    endpoint: str,
    bucket_name: str,
    access_key: str,
    secret_key: str,
    object_name: Optional[str] = None,
    region: str = 'us-east-1',
    secure: bool = False,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    public: bool = True
) -> str:
    """
    Upload a file to MinIO/S3 storage.
    
    This function acts as a facade over the specific upload implementations,
    trying each one in order until one succeeds.
    
    Args:
        file_path: Path to the file to upload
        endpoint: MinIO endpoint (host:port)
        bucket_name: Name of the bucket
        access_key: Access key
        secret_key: Secret key
        object_name: Name of the object in the bucket (default: basename of file_path)
        region: Region (default: us-east-1)
        secure: Whether to use HTTPS
        content_type: Content type of the file
        metadata: Additional metadata
        public: Whether to make the object publicly readable
        
    Returns:
        URL of the uploaded object
        
    Raises:
        UploadError: If upload fails with all available implementations
    """
    # Verify that file exists
    if not os.path.isfile(file_path):
        raise UploadError(f"File does not exist: {file_path}")
    
    # Use basename if object_name is not provided
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    # Try MinIO client first, then boto3
    if MINIO_AVAILABLE:
        try:
            return upload_with_minio(
                file_path=file_path,
                object_name=object_name,
                endpoint=endpoint,
                bucket_name=bucket_name,
                access_key=access_key,
                secret_key=secret_key,
                region=region,
                secure=secure,
                content_type=content_type,
                metadata=metadata,
                public=public
            )
        except UploadError as e:
            logger.warning(f"MinIO upload failed: {e}")
            if not BOTO3_AVAILABLE:
                raise
    
    if BOTO3_AVAILABLE:
        return upload_with_boto3(
            file_path=file_path,
            object_name=object_name,
            endpoint=endpoint,
            bucket_name=bucket_name,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            secure=secure,
            content_type=content_type,
            metadata=metadata,
            public=public
        )
    
    raise UploadError("No available S3 client implementation. Please install either minio or boto3.")

def upload_batch(
    file_paths: List[str],
    endpoint: str,
    bucket_name: str,
    access_key: str,
    secret_key: str,
    prefix: str = '',
    region: str = 'us-east-1',
    secure: bool = False,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    public: bool = True,
    flatten: bool = False
) -> Dict[str, str]:
    """
    Upload multiple files in parallel.
    
    Args:
        file_paths: List of file paths to upload
        endpoint: MinIO endpoint (host:port)
        bucket_name: Name of the bucket
        access_key: Access key
        secret_key: Secret key
        prefix: Prefix for object names
        region: Region (default: us-east-1)
        secure: Whether to use HTTPS
        content_type: Content type for all files (if specified)
        metadata: Additional metadata
        public: Whether to make objects publicly readable
        flatten: Whether to flatten directory structure
        
    Returns:
        Dictionary mapping file paths to URLs
    """
    results = {}
    errors = []
    
    # Function to be executed in parallel
    def upload_file(file_path):
        try:
            object_name = get_object_name(file_path, prefix, flatten)
            url = upload_to_minio(
                file_path=file_path,
                endpoint=endpoint,
                bucket_name=bucket_name,
                access_key=access_key,
                secret_key=secret_key,
                object_name=object_name,
                region=region,
                secure=secure,
                content_type=content_type,
                metadata=metadata,
                public=public
            )
            return file_path, url, None
        except Exception as e:
            return file_path, None, str(e)
    
    # Use ThreadPoolExecutor for parallel uploads
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(upload_file, file_path) for file_path in file_paths]
        
        for future in futures:
            file_path, url, error = future.result()
            
            if error:
                logger.error(f"Failed to upload {file_path}: {error}")
                errors.append((file_path, error))
            else:
                results[file_path] = url
    
    # Report overall status
    total = len(file_paths)
    succeeded = len(results)
    failed = len(errors)
    
    if failed > 0:
        logger.warning(f"Batch upload completed with {succeeded} successes and {failed} failures out of {total} files")
    else:
        logger.info(f"Batch upload completed successfully: {succeeded} files uploaded")
    
    # Raise exception if all uploads failed
    if failed == total:
        raise UploadError(f"All {total} uploads failed")
    
    return results

def expand_file_patterns(patterns: List[str]) -> List[str]:
    """
    Expand glob patterns and validate file paths.
    
    Args:
        patterns: List of file paths or glob patterns
        
    Returns:
        List of valid file paths
    """
    import glob
    
    files = []
    for pattern in patterns:
        # Check if it's a glob pattern
        if any(c in pattern for c in '*?[]'):
            matching_files = glob.glob(pattern)
            if not matching_files:
                logger.warning(f"No files match pattern: {pattern}")
            files.extend(matching_files)
        else:
            # Add as is if it exists
            if os.path.isfile(pattern):
                files.append(pattern)
            else:
                logger.warning(f"File not found: {pattern}")
    
    # Filter to only include files (not directories)
    files = [f for f in files if os.path.isfile(f)]
    
    if not files:
        raise UploadError("No valid files to upload")
    
    return files

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set verbosity level
    if args.verbose:
        logging.getLogger('e2e3d').setLevel(logging.DEBUG)
    
    try:
        # Prepare metadata
        metadata = parse_metadata(args.metadata)
        
        # Expand file patterns
        file_paths = expand_file_patterns(args.files)
        logger.info(f"Found {len(file_paths)} files to upload")
        
        # Batch upload or single file upload
        if args.batch or len(file_paths) > 1:
            results = upload_batch(
                file_paths=file_paths,
                endpoint=args.endpoint,
                bucket_name=args.bucket,
                access_key=args.access_key,
                secret_key=args.secret_key,
                prefix=args.prefix,
                region=args.region,
                secure=args.secure,
                content_type=args.content_type,
                metadata=metadata,
                public=args.public,
                flatten=args.flatten
            )
            
            # Show summary of uploads
            for file_path, url in results.items():
                logger.info(f"{file_path} -> {url}")
            
            return 0
        
        else:
            # Single file upload
            file_path = file_paths[0]
            object_name = get_object_name(file_path, args.prefix, args.flatten)
            
            url = upload_to_minio(
                file_path=file_path,
                endpoint=args.endpoint,
                bucket_name=args.bucket,
                access_key=args.access_key,
                secret_key=args.secret_key,
                object_name=object_name,
                region=args.region,
                secure=args.secure,
                content_type=args.content_type,
                metadata=metadata,
                public=args.public
            )
            
            logger.info(f"File uploaded and available at: {url}")
            return 0
    
    except UploadError as e:
        logger.error(f"{e}")
        return 1
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 