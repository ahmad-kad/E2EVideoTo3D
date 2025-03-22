#!/usr/bin/env python3
import pytest
import json
import os
import time
import requests
import subprocess
import signal
import sys
from unittest.mock import patch, MagicMock

# Add the production directory to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../production/scripts')))

import api

@pytest.fixture
def mock_metrics_process():
    """Create a mock metrics process for testing."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.terminate = MagicMock()
    mock_process.wait = MagicMock()
    mock_process.kill = MagicMock()
    
    original_process = api.metrics_process
    api.metrics_process = mock_process
    api.metrics_pid = mock_process.pid
    
    yield mock_process
    
    api.metrics_process = original_process

def test_metrics_initialization():
    """Test that metrics initialization works properly."""
    with patch.dict(os.environ, {'ENABLE_METRICS': 'true'}):
        with patch('api.is_port_in_use', return_value=False):
            with patch('api.start_metrics_server', return_value=True) as mock_start:
                api.metrics_enabled = False
                
                if os.environ.get('ENABLE_METRICS', 'false').lower() == 'true':
                    api.metrics_enabled = True
                    if not api.is_port_in_use(9101):
                        api.start_metrics_server()
                
                mock_start.assert_called_once()
                assert api.metrics_enabled is True

def test_metrics_cleanup(mock_metrics_process):
    """Test metrics cleanup on exit."""
    api.cleanup_metrics_server()
    mock_metrics_process.terminate.assert_called_once()

def test_update_metric_active_jobs():
    """Test updating the active_jobs metric."""
    with patch.dict(os.environ, {'ENABLE_METRICS': 'true'}):
        with patch('api.is_port_in_use', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                
                result = api.update_metric('active_jobs', 5)
                assert result is True
                
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                assert 'ACTIVE_JOBS.set(5)' in args[0][2]

def test_update_metric_reconstruction_total():
    """Test updating the reconstruction_total metric."""
    with patch.dict(os.environ, {'ENABLE_METRICS': 'true'}):
        with patch('api.is_port_in_use', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                
                result = api.update_metric('reconstruction_total')
                assert result is True
                
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                assert 'RECONSTRUCTION_TOTAL' in args[0][2]
                assert '.inc(1)' in args[0][2]

def test_update_metric_job_duration():
    """Test updating the job_duration metric with custom values and labels."""
    with patch.dict(os.environ, {'ENABLE_METRICS': 'true'}):
        with patch('api.is_port_in_use', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                
                result = api.update_metric('job_duration', 42.5, {'job_id': 'test_job', 'status': 'completed'})
                assert result is True
                
                mock_run.assert_called_once()
                args, kwargs = mock_run.call_args
                assert 'JOB_DURATION' in args[0][2]
                assert 'job_id="test_job"' in args[0][2]
                assert 'status="completed"' in args[0][2]
                assert '.inc(42.5)' in args[0][2]

def test_update_metric_invalid():
    """Test updating an invalid/nonexistent metric."""
    with patch.dict(os.environ, {'ENABLE_METRICS': 'true'}):
        with patch('api.is_port_in_use', return_value=True):
            result = api.update_metric('nonexistent_metric')
            assert result is False

def test_update_metric_disabled():
    """Test updating a metric when metrics are disabled."""
    with patch.dict(os.environ, {'ENABLE_METRICS': 'false'}):
        api.metrics_enabled = False
        result = api.update_metric('reconstruction_total')
        assert result is False

def test_job_monitor_thread_success():
    """Test the job monitor thread with a successful job completion."""
    job_id = 'test_monitor_job'
    output_dir = '/app/data/output/test_monitor_job'
    mock_process = MagicMock()
    mock_process.wait.return_value = 0
    
    with patch('api.update_metric') as mock_update:
        with patch('os.path.exists', lambda path: 'SUCCESS' in path):
            api.job_history = {}
            api.active_jobs = {}
            
            api.job_monitor_thread(job_id, mock_process, output_dir)
            
            assert job_id not in api.active_jobs
            assert job_id in api.job_history
            assert api.job_history[job_id]['status'] == 'completed'
            
            assert mock_update.call_count >= 5
            
            initial_active_call = False
            final_active_call = False
            
            for call in mock_update.call_args_list:
                args, kwargs = call
                if args[0] == 'active_jobs':
                    if args[1] == 1:
                        initial_active_call = True
                    elif args[1] == 0:
                        final_active_call = True
            
            assert initial_active_call
            assert final_active_call

def test_job_monitor_thread_failure():
    """Test the job monitor thread with a job failure."""
    job_id = 'test_monitor_fail_job'
    output_dir = '/app/data/output/test_monitor_fail_job'
    mock_process = MagicMock()
    mock_process.wait.return_value = 1  # Non-zero return code indicates failure
    
    with patch('api.update_metric') as mock_update:
        with patch('os.path.exists', lambda path: False):
            api.job_history = {}
            api.active_jobs = {}
            
            api.job_monitor_thread(job_id, mock_process, output_dir)
            
            assert job_id not in api.active_jobs
            assert job_id in api.job_history
            assert api.job_history[job_id]['status'] == 'failed'
            
            reconstruction_failure_called = False
            
            for call in mock_update.call_args_list:
                args, kwargs = call
                if args[0] == 'reconstruction_failure':
                    reconstruction_failure_called = True
                    break
            
            assert reconstruction_failure_called

def test_job_monitor_thread_exception():
    """Test the job monitor thread when an unexpected exception occurs."""
    job_id = 'test_monitor_exception_job'
    output_dir = '/app/data/output/test_monitor_exception_job'
    mock_process = MagicMock()
    mock_process.wait.side_effect = Exception("Test exception")
    
    with patch('api.update_metric') as mock_update:
        api.job_history = {}
        api.active_jobs = {job_id: {'start_time': time.time()}}
        
        api.job_monitor_thread(job_id, mock_process, output_dir)
        
        assert job_id not in api.active_jobs
        assert job_id in api.job_history
        assert api.job_history[job_id]['status'] == 'error'
        assert 'Test exception' in api.job_history[job_id]['error']
        
        reconstruction_failure_called = False
        
        for call in mock_update.call_args_list:
            args, kwargs = call
            if args[0] == 'reconstruction_failure':
                reconstruction_failure_called = True
                break
        
        assert reconstruction_failure_called 