"""
PyTest Configuration File

This file contains shared fixtures and configuration for the E2E3D test suite.
"""

import os
import sys
import pytest
import tempfile
import shutil
import json
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Constants
TEST_DATA_DIR = Path(__file__).parent / 'fixtures'


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_image_set(temp_dir):
    """Create a sample image set with mock images for testing."""
    image_set_dir = os.path.join(temp_dir, 'sample_image_set')
    os.makedirs(image_set_dir, exist_ok=True)
    
    # Create dummy image files
    for i in range(5):
        with open(os.path.join(image_set_dir, f'image_{i}.jpg'), 'wb') as f:
            # Create a simple 1x1 black JPEG
            f.write(b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00\x48\x00\x48\x00\x00\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0C\x14\r\x0C\x0B\x0B\x0C\x19\x12\x13\x0F\x14\x1D\x1A\x1F\x1E\x1D\x1A\x1C\x1C $.\' ",#\x1C\x1C(7),01444\x1F\'9=82<.342\xFF\xDB\x00C\x01\t\t\t\x0C\x0B\x0C\x18\r\r\x182!\x1C!22222222222222222222222222222222222222222222222222\xFF\xC0\x00\x11\x08\x00\x01\x00\x01\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xFF\xC4\x00\x1F\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0B\xFF\xC4\x00\xB5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xA1\x08#B\xB1\xC1\x15R\xD1\xF0$3br\x82\t\n\x16\x17\x18\x19\x1A%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8A\x92\x93\x94\x95\x96\x97\x98\x99\x9A\xA2\xA3\xA4\xA5\xA6\xA7\xA8\xA9\xAA\xB2\xB3\xB4\xB5\xB6\xB7\xB8\xB9\xBA\xC2\xC3\xC4\xC5\xC6\xC7\xC8\xC9\xCA\xD2\xD3\xD4\xD5\xD6\xD7\xD8\xD9\xDA\xE1\xE2\xE3\xE4\xE5\xE6\xE7\xE8\xE9\xEA\xF1\xF2\xF3\xF4\xF5\xF6\xF7\xF8\xF9\xFA\xFF\xC4\x00\x1F\x01\x00\x03\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0B\xFF\xC4\x00\xB5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x05!1\x06\x12AQ\x07aq\x13"2\x81\x08\x14B\x91\xA1\xB1\xC1\t#3R\xF0\x15br\xD1\n\x16$4\xE1%\xF1\x17\x18\x19\x1A&\'()*56789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8A\x92\x93\x94\x95\x96\x97\x98\x99\x9A\xA2\xA3\xA4\xA5\xA6\xA7\xA8\xA9\xAA\xB2\xB3\xB4\xB5\xB6\xB7\xB8\xB9\xBA\xC2\xC3\xC4\xC5\xC6\xC7\xC8\xC9\xCA\xD2\xD3\xD4\xD5\xD6\xD7\xD8\xD9\xDA\xE2\xE3\xE4\xE5\xE6\xE7\xE8\xE9\xEA\xF2\xF3\xF4\xF5\xF6\xF7\xF8\xF9\xFA\xFF\xDA\x00\x0C\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xFE\xFE(\xA2\x8A\x00\xFF\xD9')
    
    yield image_set_dir


@pytest.fixture
def sample_obj_file(temp_dir):
    """Create a sample OBJ file for testing."""
    obj_file = os.path.join(temp_dir, 'sample.obj')
    
    with open(obj_file, 'w') as f:
        f.write("""
# Simple triangle mesh
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 0.0 1.0 0.0
f 1 2 3
""")
    
    yield obj_file


@pytest.fixture
def mock_api_client():
    """Create a mock API client for testing the API endpoints."""
    from flask.testing import FlaskClient
    from production.scripts.api import app
    
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_minio_client(temp_dir):
    """Create a mock MinIO client that writes to the local filesystem."""
    from unittest.mock import MagicMock
    
    class MockMinioClient:
        def __init__(self):
            self.storage_dir = os.path.join(temp_dir, 'minio')
            os.makedirs(self.storage_dir, exist_ok=True)
        
        def put_object(self, bucket_name, object_name, data, length, content_type=None):
            bucket_dir = os.path.join(self.storage_dir, bucket_name)
            os.makedirs(bucket_dir, exist_ok=True)
            
            file_path = os.path.join(bucket_dir, object_name)
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write the file data
            with open(file_path, 'wb') as f:
                if hasattr(data, 'read'):
                    # If data is a file-like object
                    content = data.read()
                    data.seek(0)  # Reset file position
                    f.write(content)
                else:
                    # If data is bytes
                    f.write(data)
        
        def get_object(self, bucket_name, object_name):
            file_path = os.path.join(self.storage_dir, bucket_name, object_name)
            
            class MockResponse:
                def __init__(self, file_path):
                    self.file_path = file_path
                
                def read(self):
                    with open(self.file_path, 'rb') as f:
                        return f.read()
                        
            return MockResponse(file_path)
    
    return MockMinioClient() 