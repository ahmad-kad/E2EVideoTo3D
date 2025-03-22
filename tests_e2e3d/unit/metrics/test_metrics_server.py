"""
Unit tests for the metrics server functionality
"""

import pytest
import socket
import time
from unittest.mock import patch, MagicMock

# Import metrics functions
from production.scripts.api import start_metrics_server, cleanup_metrics_server, is_port_in_use

def test_is_port_in_use_with_closed_port():
    """Test the is_port_in_use function with a port that's not in use."""
    # Find an unused port for testing
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        unused_port = s.getsockname()[1]
    
    # Test the function
    result = is_port_in_use(unused_port)
    assert result is False

def test_is_port_in_use_with_open_port():
    """Test the is_port_in_use function with a port that is in use."""
    # Open a port for testing
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', 0))
    server_socket.listen(1)
    used_port = server_socket.getsockname()[1]
    
    try:
        # Test the function
        result = is_port_in_use(used_port)
        assert result is True
    finally:
        server_socket.close()

def test_start_metrics_server():
    """Test the start_metrics_server function."""
    with patch('production.scripts.api.subprocess.Popen') as mock_popen:
        # Configure the mock
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Call the function
        start_metrics_server()
        
        # Check that Popen was called
        mock_popen.assert_called_once()
        
        # Check that global variables were set
        from production.scripts.api import metrics_process
        assert metrics_process is not None

def test_cleanup_metrics_server():
    """Test the cleanup_metrics_server function."""
    with patch('production.scripts.api.metrics_process') as mock_process:
        # Configure the mock
        mock_process.poll.return_value = None  # Process is still running
        
        # Call the function
        cleanup_metrics_server()
        
        # Check that the process was terminated
        mock_process.terminate.assert_called_once()

def test_metrics_startup_shutdown_integration():
    """Test the full lifecycle of the metrics server."""
    # We need to patch both functions to avoid actual process creation
    with patch('production.scripts.api.subprocess.Popen') as mock_popen:
        # Configure the mocks
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        mock_process.poll.return_value = None  # Process is running
        
        # Start the metrics server
        start_metrics_server()
        
        # Verify it was started
        mock_popen.assert_called_once()
        
        # Clean up
        cleanup_metrics_server()
        
        # Verify cleanup was called
        mock_process.terminate.assert_called_once() 