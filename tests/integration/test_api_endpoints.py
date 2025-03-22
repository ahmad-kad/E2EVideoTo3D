#!/usr/bin/env python3
import pytest
import json
import os
import time
import threading
import requests
from unittest.mock import patch, MagicMock
import sys
import tempfile
from pathlib import Path

# Add the production directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../production/scripts')))

import api

@pytest.fixture
def client():
    """Create a test client for the Flask application."""
    api.app.config['TESTING'] = True
    with api.app.test_client() as client:
        yield client

@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv('ENABLE_METRICS', 'true')
    yield

@pytest.fixture
def mock_metrics_server(monkeypatch):
    """Mock the metrics server for testing."""
    # Mock the is_port_in_use function to always return True
    monkeypatch.setattr(api, 'is_port_in_use', lambda port: True)
    
    # Mock the start_metrics_server function
    def mock_start():
        return True
    monkeypatch.setattr(api, 'start_metrics_server', mock_start)
    
    # Mock the update_metric function
    def mock_update(name, value=1, labels=None):
        return True
    monkeypatch.setattr(api, 'update_metric', mock_update)
    
    yield

@pytest.fixture
def sample_job_data():
    """Sample job data for testing reconstruction requests."""
    return {
        'image_set_path': '/app/data/input/test_dataset',
        'quality': 'medium',
        'job_id': 'test_job_1'
    }

@pytest.fixture
def sample_job_output_dir(tmpdir):
    """Create a sample job output directory structure for testing."""
    job_id = 'test_job_1'
    timestamp = '20230426_010203'
    job_dir = tmpdir.mkdir(job_id)
    timestamp_dir = job_dir.mkdir(f"{job_id}_{timestamp}")
    
    # Create subdirectories
    mesh_dir = timestamp_dir.mkdir("mesh")
    textures_dir = timestamp_dir.mkdir("textures")
    pointcloud_dir = timestamp_dir.mkdir("pointcloud")
    
    # Create sample files
    mesh_file = mesh_dir.join("reconstructed_mesh.obj")
    mesh_file.write("# Sample mesh file content")
    
    texture_file = textures_dir.join("texture_map.jpg")
    texture_file.write("Sample texture data")
    
    pointcloud_file = pointcloud_dir.join("pointcloud.ply")
    pointcloud_file.write("Sample pointcloud data")
    
    # Create SUCCESS file
    success_file = timestamp_dir.join("SUCCESS")
    success_file.write("Reconstruction completed successfully")
    
    return {
        'tmpdir': tmpdir,
        'job_id': job_id,
        'timestamp_dir': timestamp_dir,
        'mesh_file': mesh_file
    }

def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'healthy'

def test_metrics_check(client, mock_env, mock_metrics_server):
    """Test the metrics check endpoint."""
    response = client.get('/api/metrics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'available'
    assert data['port'] == 9101

def test_reconstruct_endpoint(client, mock_env, mock_metrics_server, sample_job_data):
    """Test the reconstruct endpoint with valid data."""
    # Mock os.path.isdir to return True for our test path
    with patch('os.path.isdir', return_value=True):
        # Mock subprocess.Popen
        mock_process = MagicMock()
        mock_process.pid = 12345
        
        with patch('subprocess.Popen', return_value=mock_process) as mock_popen:
            # Mock threading.Thread
            with patch('threading.Thread') as mock_thread:
                response = client.post(
                    '/api/reconstruct',
                    json=sample_job_data,
                    content_type='application/json'
                )
                
                # Check response
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['status'] == 'submitted'
                assert data['job_id'] == sample_job_data['job_id']
                
                # Check if the process was started correctly
                mock_popen.assert_called_once()
                # Check that thread was started
                mock_thread.assert_called_once()

def test_reconstruct_endpoint_invalid_input(client, sample_job_data):
    """Test the reconstruct endpoint with invalid input data."""
    # Test with missing image_set_path
    invalid_data = sample_job_data.copy()
    del invalid_data['image_set_path']
    
    response = client.post(
        '/api/reconstruct',
        json=invalid_data,
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'image_set_path is required' in data['error']
    
    # Test with non-existent directory
    with patch('os.path.isdir', return_value=False):
        response = client.post(
            '/api/reconstruct',
            json=sample_job_data,
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Input directory does not exist' in data['error']

def test_list_jobs_empty(client):
    """Test listing jobs when there are none."""
    response = client.get('/api/jobs')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'jobs' in data
    assert len(data['jobs']) == 0

def test_list_jobs_with_active_job(client, mock_env, mock_metrics_server):
    """Test listing jobs with an active job in progress."""
    # Add a mock job to the active_jobs dictionary
    job_id = 'test_active_job'
    api.active_jobs[job_id] = {
        'process': MagicMock(),
        'start_time': time.time(),
        'status': 'running',
        'output_dir': '/app/data/output/test_active_job'
    }
    
    try:
        response = client.get('/api/jobs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'jobs' in data
        assert len(data['jobs']) == 1
        assert job_id in data['jobs']
        assert data['jobs'][job_id]['status'] == 'running'
    finally:
        # Clean up
        if job_id in api.active_jobs:
            del api.active_jobs[job_id]

def test_get_job_status_active(client):
    """Test getting status of an active job."""
    # Add a mock job to the active_jobs dictionary
    job_id = 'test_status_job'
    start_time = time.time()
    api.active_jobs[job_id] = {
        'process': MagicMock(),
        'start_time': start_time,
        'status': 'running',
        'output_dir': '/app/data/output/test_status_job'
    }
    
    try:
        response = client.get(f'/api/job/{job_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['job_id'] == job_id
        assert data['status'] == 'running'
        assert data['start_time'] == start_time
        assert 'elapsed' in data
    finally:
        # Clean up
        if job_id in api.active_jobs:
            del api.active_jobs[job_id]

def test_get_job_status_completed(client):
    """Test getting status of a completed job."""
    # Add a mock job to the job_history dictionary
    job_id = 'test_completed_job'
    start_time = time.time() - 60  # Started 60 seconds ago
    end_time = time.time() - 10    # Ended 10 seconds ago
    api.job_history[job_id] = {
        'status': 'completed',
        'start_time': start_time,
        'end_time': end_time,
        'duration': 50,
        'output_dir': '/app/data/output/test_completed_job'
    }
    
    try:
        response = client.get(f'/api/job/{job_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['job_id'] == job_id
        assert data['status'] == 'completed'
        assert data['start_time'] == start_time
        assert data['end_time'] == end_time
        assert data['duration'] == 50
    finally:
        # Clean up
        if job_id in api.job_history:
            del api.job_history[job_id]

def test_get_job_status_from_filesystem(client, sample_job_output_dir):
    """Test getting job status from the filesystem when not in memory."""
    job_id = sample_job_output_dir['job_id']
    
    # Mock the base output directory path
    with patch('os.path.join', lambda *args: str(sample_job_output_dir['tmpdir'].join(args[1:]))):
        with patch('os.path.isdir', return_value=True):
            with patch('glob.glob', return_value=[str(sample_job_output_dir['timestamp_dir'])]):
                response = client.get(f'/api/job/{job_id}')
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['job_id'] == job_id
                assert data['status'] == 'completed'
                assert 'details' in data
                assert data['details'] == 'Reconstruction completed successfully'

def test_get_job_results(client, sample_job_output_dir):
    """Test getting job results for a completed job."""
    job_id = sample_job_output_dir['job_id']
    
    # Mock the base output directory path and filesystem functions
    with patch('os.path.join', lambda *args: str(sample_job_output_dir['tmpdir'].join(args[1:]))):
        with patch('os.path.isdir', return_value=True):
            with patch('glob.glob') as mock_glob:
                # Set up mock glob behavior
                def mock_glob_side_effect(pattern):
                    if pattern.endswith('*'):
                        if 'test_job_1_*' in pattern:
                            return [str(sample_job_output_dir['timestamp_dir'])]
                        elif 'mesh/*' in pattern:
                            return [str(sample_job_output_dir['mesh_file'])]
                        else:
                            return []
                    return []
                
                mock_glob.side_effect = mock_glob_side_effect
                
                with patch('os.path.exists', return_value=True):
                    with patch('os.path.isfile', return_value=True):
                        with patch('os.path.getsize', return_value=1024):
                            with patch('os.path.relpath', return_value=f"test_job_1/mesh/reconstructed_mesh.obj"):
                                response = client.get(f'/api/job/{job_id}/results')
                                assert response.status_code == 200
                                data = json.loads(response.data)
                                assert data['job_id'] == job_id
                                assert 'files' in data
                                assert len(data['files']) > 0
                                assert data['files'][0]['type'] == 'obj'

def test_cancel_job(client, mock_env, mock_metrics_server):
    """Test cancelling a running job."""
    # Add a mock job to the active_jobs dictionary
    job_id = 'test_cancel_job'
    mock_process = MagicMock()
    api.active_jobs[job_id] = {
        'process': mock_process,
        'start_time': time.time(),
        'status': 'running',
        'output_dir': '/app/data/output/test_cancel_job'
    }
    
    try:
        response = client.post(f'/api/job/{job_id}/cancel')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'cancelled'
        assert data['job_id'] == job_id
        
        # Check that the process was terminated
        mock_process.terminate.assert_called_once()
        
        # Job should be moved from active_jobs to job_history
        assert job_id not in api.active_jobs
        assert job_id in api.job_history
        assert api.job_history[job_id]['status'] == 'cancelled'
    finally:
        # Clean up
        if job_id in api.active_jobs:
            del api.active_jobs[job_id]
        if job_id in api.job_history:
            del api.job_history[job_id]

def test_get_file(client, sample_job_output_dir):
    """Test getting a file from the output directory."""
    filepath = f"test_job_1/mesh/reconstructed_mesh.obj"
    
    # Mock the base output directory path and file functions
    with patch('os.path.join', return_value=str(sample_job_output_dir['mesh_file'])):
        with patch('os.path.isfile', return_value=True):
            with patch('flask.send_file', return_value='Mocked file content'):
                response = client.get(f'/api/file/{filepath}')
                assert response.status_code == 200 