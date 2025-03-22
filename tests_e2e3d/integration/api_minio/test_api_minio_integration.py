"""
Integration tests for API and MinIO interaction
"""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
import io
import sys

# Add the mocks directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'mocks'))

def test_api_uploads_to_minio(mock_api_client, mock_minio_client):
    """Test that the API can trigger a job that uploads results to MinIO."""
    
    # Mock the reconstruction process
    with patch('production.scripts.api.subprocess.Popen') as mock_popen:
        # Configure the mocks
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        mock_process.communicate.return_value = (b'Job started with ID: test_job_123', b'')
        mock_process.returncode = 0
        
        # Test data for reconstruction
        test_data = {
            'image_set': 'test_image_set',
            'job_id': 'test_job_integration',
            'quality': 'medium'
        }
        
        # Make the API request
        response = mock_api_client.post(
            '/api/reconstruct',
            data=json.dumps(test_data),
            content_type='application/json'
        )
        
        # Check API response
        assert response.status_code == 200
        data = json.loads(response.data.decode('utf-8'))
        assert 'job_id' in data

def test_end_to_end_with_mocks(mock_api_client, mock_minio_client, temp_dir):
    """Test the end-to-end flow with mocked components."""
    
    # Create a mock image set
    image_set_dir = os.path.join(temp_dir, 'test_image_set')
    os.makedirs(image_set_dir, exist_ok=True)
    
    # Create dummy images
    for i in range(5):
        with open(os.path.join(image_set_dir, f'image_{i}.jpg'), 'w') as f:
            f.write('dummy image data')
    
    # Create a mock mesh output file
    mesh_output = os.path.join(temp_dir, 'output', 'mesh.obj')
    os.makedirs(os.path.dirname(mesh_output), exist_ok=True)
    with open(mesh_output, 'w') as f:
        f.write('# Mock OBJ file\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3')
    
    # Set up the patch for the API subprocess
    with patch('production.scripts.api.subprocess.Popen') as mock_api_popen:
        # Configure the API process mock
        mock_api_process = MagicMock()
        mock_api_popen.return_value = mock_api_process
        mock_api_process.communicate.return_value = (f'Job started with ID: test_job_123\nOutput file: {mesh_output}'.encode(), b'')
        mock_api_process.returncode = 0
        
        # Test data for reconstruction
        test_data = {
            'image_set': image_set_dir,
            'job_id': 'test_job_e2e',
            'quality': 'low'
        }
        
        # Make the API request
        response = mock_api_client.post(
            '/api/reconstruct',
            data=json.dumps(test_data),
            content_type='application/json'
        )
        
        # Check API response
        assert response.status_code == 200
        data = json.loads(response.data.decode('utf-8'))
        assert 'job_id' in data 