"""
Unit tests for the API health endpoint
"""

import pytest
import json

def test_api_health_endpoint(mock_api_client):
    """Test that the health endpoint returns a healthy status."""
    response = mock_api_client.get('/api/health')
    assert response.status_code == 200
    
    data = json.loads(response.data.decode('utf-8'))
    assert 'status' in data
    assert data['status'] == 'healthy'

def test_api_metrics_endpoint(mock_api_client):
    """Test that the metrics endpoint returns the expected response."""
    response = mock_api_client.get('/api/metrics')
    assert response.status_code == 200
    
    data = json.loads(response.data.decode('utf-8'))
    assert 'status' in data
    
    # Check if metrics are available or not
    if data.get('status') == 'available':
        assert 'port' in data
        assert data['port'] == 9101
    else:
        assert data.get('status') == 'unavailable'
        assert 'reason' in data 