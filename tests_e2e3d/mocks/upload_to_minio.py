"""
Mock implementation of upload_to_minio for testing.
"""

import os
from typing import Optional, Any

def upload_file_to_minio(
    client: Any, 
    bucket_name: str, 
    object_name: str, 
    file_path: str, 
    content_type: Optional[str] = None
) -> bool:
    """
    Mock implementation of upload_file_to_minio function for testing.
    
    Args:
        client: The MinIO client
        bucket_name: Name of the bucket
        object_name: Name of the object in the bucket
        file_path: Path to the file to upload
        content_type: Content type of the file
        
    Returns:
        True if the upload was successful, False otherwise
        
    Raises:
        FileNotFoundError: If the file does not exist
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Read the file
    with open(file_path, 'rb') as f:
        file_data = f.read()
        file_size = len(file_data)
    
    # Upload to the mock client
    client.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=open(file_path, 'rb'),
        length=file_size,
        content_type=content_type
    )
    
    return True

def upload_to_minio(
    file_path: str,
    endpoint: str,
    bucket_name: str,
    access_key: str,
    secret_key: str,
    secure: bool = False
) -> str:
    """
    Mock implementation of upload_to_minio function for testing.
    
    Args:
        file_path: Path to the file to upload
        endpoint: MinIO endpoint (host:port)
        bucket_name: Name of the bucket
        access_key: MinIO access key
        secret_key: MinIO secret key
        secure: Whether to use HTTPS
        
    Returns:
        URL of the uploaded file
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Generate a mock URL
    protocol = "https" if secure else "http"
    object_name = os.path.basename(file_path)
    url = f"{protocol}://{endpoint}/{bucket_name}/{object_name}"
    
    return url 