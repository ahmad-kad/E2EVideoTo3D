"""
Unit tests for the core reconstruction functionality
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Import the reconstruction script
# Note: We need to patch actual execution of COLMAP and other tools
from production.scripts.reconstruct import run_reconstruction, create_output_structure

def test_run_reconstruction():
    """Test the run_reconstruction function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock image set
        image_set_dir = os.path.join(temp_dir, 'test_images')
        os.makedirs(image_set_dir, exist_ok=True)
        
        # Create dummy images
        for i in range(5):
            with open(os.path.join(image_set_dir, f'image_{i}.jpg'), 'wb') as f:
                # Simple JPG header
                f.write(b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0C\x14\r\x0C\x0B\x0B\x0C\x19\x12\x13\x0F\x14\x1D\x1A\x1F\x1E\x1D\x1A\x1C\x1C $.\' ",#\x1C\x1C(7),01444\x1F\'9=82<.342')
        
        # Create job ID and output structure
        job_id = "test_job_123"
        output_paths = create_output_structure(temp_dir, job_id)
        
        # Mock list_input_files to prevent actual file reading
        with patch('production.scripts.reconstruct.list_input_files') as mock_list_files:
            # Configure mock to return list of image files
            image_files = [os.path.join(image_set_dir, f'image_{i}.jpg') for i in range(5)]
            mock_list_files.return_value = image_files
            
            # Call run_reconstruction
            output_files = run_reconstruction(
                image_set_dir,
                output_paths,
                quality='low',  # Use lowest quality for speed
                use_gpu='false'
            )
            
            # Verify output files were created
            assert 'mesh' in output_files
            assert 'pointcloud' in output_files
            assert 'texture' in output_files
            assert os.path.exists(output_files['mesh'])
            assert os.path.exists(output_files['pointcloud'])

def test_create_output_structure():
    """Test the create_output_structure function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        job_id = "test_job_456"
        
        # Call the function
        output_paths = create_output_structure(temp_dir, job_id)
        
        # Verify directories were created
        assert os.path.exists(output_paths['root'])
        assert os.path.exists(output_paths['mesh'])
        assert os.path.exists(output_paths['pointcloud'])
        assert os.path.exists(output_paths['textures'])
        assert os.path.exists(output_paths['logs'])
        assert os.path.exists(output_paths['temp'])
        
        # Verify metadata file was created
        metadata_file = os.path.join(output_paths['root'], 'metadata.json')
        assert os.path.exists(metadata_file)
        
        # Check metadata contents
        import json
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
            assert metadata['job_id'] == job_id 