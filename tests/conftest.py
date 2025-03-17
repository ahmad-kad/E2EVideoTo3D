"""
PyTest Configuration File

This file contains shared fixtures and configuration for the test suite.
"""

import os
import sys
import pytest
import tempfile
import shutil

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


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
        with open(os.path.join(image_set_dir, f'image_{i}.jpg'), 'w') as f:
            f.write('dummy image data')
    
    yield image_set_dir 