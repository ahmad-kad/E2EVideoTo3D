#!/usr/bin/env python3
"""
COLMAP Wrapper

This module provides a wrapper for COLMAP operations, making it easier to run
COLMAP commands from Python code.
"""

import os
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path

# Configure logging
logger = logging.getLogger("reconstruction.colmap")

class ColmapWrapper:
    """
    Wrapper class for COLMAP operations.
    """
    
    def __init__(self, colmap_path='colmap', workspace_path=None, image_path=None):
        """
        Initialize the COLMAP wrapper.
        
        Args:
            colmap_path (str): Path to the COLMAP executable
            workspace_path (str): Path to the COLMAP workspace
            image_path (str): Path to the input images
        """
        self.colmap_path = colmap_path
        self.workspace_path = workspace_path
        self.image_path = image_path
        
        # Ensure the binary is available
        self._check_colmap()
        
        # Default configuration
        self.config = {
            'use_gpu': 'auto',  # 'auto', True, or False
            'quality': 'medium',  # 'low', 'medium', 'high'
            'matcher': 'exhaustive',  # 'exhaustive', 'sequential', 'spatial', 'vocab_tree'
            'max_image_size': 2000,
            'max_num_matches': 25000,
            'num_threads': -1,  # -1 means use all available cores
            'timeout': 3600,  # 1 hour timeout for commands
        }
        
        # Quality presets
        self.quality_presets = {
            'low': {
                'max_image_size': 1600,
                'max_num_matches': 10000,
            },
            'medium': {
                'max_image_size': 2000,
                'max_num_matches': 25000,
            },
            'high': {
                'max_image_size': 3200,
                'max_num_matches': 50000,
            }
        }
        
        # Use quality preset if provided
        self._apply_quality_preset(self.config['quality'])
    
    def _check_colmap(self):
        """Check if COLMAP is available and get its version."""
        try:
            result = subprocess.run(
                [self.colmap_path, "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Try to extract version from output
                if "COLMAP" in result.stdout:
                    version_line = [line for line in result.stdout.split('\n') if "COLMAP" in line][0]
                    logger.info(f"COLMAP available: {version_line}")
                else:
                    logger.info("COLMAP is available")
            else:
                logger.warning(f"COLMAP check returned non-zero exit code: {result.returncode}")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"COLMAP not found at {self.colmap_path}: {str(e)}")
            raise RuntimeError(f"COLMAP not found or not executable: {str(e)}")
    
    def _apply_quality_preset(self, quality):
        """Apply quality preset settings."""
        if quality in self.quality_presets:
            preset = self.quality_presets[quality]
            for key, value in preset.items():
                self.config[key] = value
        else:
            logger.warning(f"Unknown quality preset: {quality}, using 'medium' instead")
            self._apply_quality_preset('medium')
    
    def set_config(self, **kwargs):
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if key == 'quality' and value in self.quality_presets:
                self._apply_quality_preset(value)
            else:
                self.config[key] = value
    
    def is_gpu_available(self):
        """Check if GPU is available for COLMAP."""
        if self.config['use_gpu'] == True:
            return True
        elif self.config['use_gpu'] == False:
            return False
        
        # Auto-detect GPU
        try:
            # Try NVIDIA detection
            result = subprocess.run(
                ['nvidia-smi'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("NVIDIA GPU detected")
                return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # Try other detection methods if needed
        try:
            import torch
            if torch.cuda.is_available():
                logger.info("CUDA available via PyTorch")
                return True
        except ImportError:
            pass
        
        logger.info("No GPU detected, using CPU mode")
        return False
    
    def run_feature_extraction(self, image_path=None, database_path=None):
        """
        Run COLMAP feature extraction.
        
        Args:
            image_path (str): Path to the input images
            database_path (str): Path to the database file
        
        Returns:
            bool: True if successful, False otherwise
        """
        image_path = image_path or self.image_path
        if not image_path:
            raise ValueError("Image path must be provided")
        
        if not database_path:
            # Create database path if workspace is specified
            if self.workspace_path:
                os.makedirs(os.path.join(self.workspace_path, 'database'), exist_ok=True)
                database_path = os.path.join(self.workspace_path, 'database', 'database.db')
            else:
                raise ValueError("Database path must be provided if workspace_path is not set")
        
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        
        # Determine GPU usage
        use_gpu = self.is_gpu_available()
        
        # Build command
        cmd = [
            self.colmap_path, 'feature_extractor',
            '--database_path', database_path,
            '--image_path', image_path,
            '--ImageReader.camera_model', 'SIMPLE_RADIAL',
            '--ImageReader.single_camera', '1',
            f'--SiftExtraction.use_gpu', '1' if use_gpu else '0',
            f'--SiftExtraction.max_image_size', str(self.config['max_image_size']),
            f'--SiftExtraction.num_threads', str(self.config['num_threads'])
        ]
        
        logger.info(f"Running COLMAP feature extraction: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode == 0:
                logger.info("Feature extraction completed successfully")
                return True
            else:
                logger.error(f"Feature extraction failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Feature extraction timed out after {self.config['timeout']} seconds")
            return False
        
        except Exception as e:
            logger.error(f"Error during feature extraction: {str(e)}")
            return False
    
    def run_feature_matching(self, database_path=None, matcher=None):
        """
        Run COLMAP feature matching.
        
        Args:
            database_path (str): Path to the database file
            matcher (str): Matching algorithm to use
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not database_path:
            # Use default database path
            if self.workspace_path:
                database_path = os.path.join(self.workspace_path, 'database', 'database.db')
            else:
                raise ValueError("Database path must be provided if workspace_path is not set")
        
        # Ensure database exists
        if not os.path.exists(database_path):
            raise FileNotFoundError(f"Database file not found: {database_path}")
        
        # Determine which matcher to use
        matcher = matcher or self.config['matcher']
        if matcher not in ['exhaustive', 'sequential', 'spatial', 'vocab_tree']:
            logger.warning(f"Unknown matcher: {matcher}, using exhaustive instead")
            matcher = 'exhaustive'
        
        # Determine GPU usage
        use_gpu = self.is_gpu_available()
        
        # Build command
        cmd = [
            self.colmap_path, f'{matcher}_matcher',
            '--database_path', database_path,
            f'--SiftMatching.use_gpu', '1' if use_gpu else '0',
            f'--SiftMatching.max_num_matches', str(self.config['max_num_matches']),
            f'--SiftMatching.num_threads', str(self.config['num_threads'])
        ]
        
        logger.info(f"Running COLMAP {matcher} matcher: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode == 0:
                logger.info("Feature matching completed successfully")
                return True
            else:
                logger.error(f"Feature matching failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Feature matching timed out after {self.config['timeout']} seconds")
            return False
        
        except Exception as e:
            logger.error(f"Error during feature matching: {str(e)}")
            return False
    
    def run_sparse_reconstruction(self, database_path=None, image_path=None, output_path=None):
        """
        Run COLMAP sparse reconstruction (SfM).
        
        Args:
            database_path (str): Path to the database file
            image_path (str): Path to the input images
            output_path (str): Path to the output sparse reconstruction
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Set default paths if not provided
        database_path = database_path or (os.path.join(self.workspace_path, 'database', 'database.db') if self.workspace_path else None)
        image_path = image_path or self.image_path
        output_path = output_path or (os.path.join(self.workspace_path, 'sparse') if self.workspace_path else None)
        
        # Validate paths
        if not database_path or not os.path.exists(database_path):
            raise FileNotFoundError(f"Database file not found: {database_path}")
        
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image directory not found: {image_path}")
        
        if not output_path:
            raise ValueError("Output path must be provided")
        
        # Create output directory
        os.makedirs(output_path, exist_ok=True)
        
        # Build command
        cmd = [
            self.colmap_path, 'mapper',
            '--database_path', database_path,
            '--image_path', image_path,
            '--output_path', output_path,
        ]
        
        logger.info(f"Running COLMAP mapper: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode == 0:
                logger.info("Sparse reconstruction completed successfully")
                return True
            else:
                logger.error(f"Sparse reconstruction failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Sparse reconstruction timed out after {self.config['timeout']} seconds")
            return False
        
        except Exception as e:
            logger.error(f"Error during sparse reconstruction: {str(e)}")
            return False
    
    def run_dense_reconstruction(self, workspace_path=None, sparse_path=None):
        """
        Run COLMAP dense reconstruction (MVS).
        
        Args:
            workspace_path (str): Path to the COLMAP workspace
            sparse_path (str): Path to the sparse reconstruction
        
        Returns:
            bool: True if successful, False otherwise
        """
        workspace_path = workspace_path or self.workspace_path
        if not workspace_path:
            raise ValueError("Workspace path must be provided")
        
        # Set default sparse path if not provided
        sparse_path = sparse_path or os.path.join(workspace_path, 'sparse', '0')
        
        # Validate paths
        if not os.path.exists(sparse_path):
            raise FileNotFoundError(f"Sparse reconstruction not found: {sparse_path}")
        
        # Create output directories
        dense_path = os.path.join(workspace_path, 'dense')
        os.makedirs(dense_path, exist_ok=True)
        
        # Determine GPU usage
        use_gpu = self.is_gpu_available()
        
        # Run image undistorter
        undistorter_cmd = [
            self.colmap_path, 'image_undistorter',
            '--image_path', self.image_path,
            '--input_path', sparse_path,
            '--output_path', dense_path,
            '--output_type', 'COLMAP'
        ]
        
        logger.info(f"Running COLMAP image undistorter: {' '.join(undistorter_cmd)}")
        
        try:
            process = subprocess.run(
                undistorter_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode != 0:
                logger.error(f"Image undistortion failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
            
            # Check if GPU is available for patch match stereo
            if not use_gpu:
                logger.warning("Dense stereo reconstruction requires CUDA. Skipping patch_match_stereo.")
                return False
            
            # Run patch match stereo
            stereo_cmd = [
                self.colmap_path, 'patch_match_stereo',
                '--workspace_path', dense_path
            ]
            
            logger.info(f"Running COLMAP patch match stereo: {' '.join(stereo_cmd)}")
            
            process = subprocess.run(
                stereo_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode != 0:
                logger.error(f"Patch match stereo failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
            
            # Run stereo fusion
            fusion_cmd = [
                self.colmap_path, 'stereo_fusion',
                '--workspace_path', dense_path,
                '--output_path', os.path.join(dense_path, 'fused.ply')
            ]
            
            logger.info(f"Running COLMAP stereo fusion: {' '.join(fusion_cmd)}")
            
            process = subprocess.run(
                fusion_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode != 0:
                logger.error(f"Stereo fusion failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
            
            logger.info("Dense reconstruction completed successfully")
            return True
                
        except subprocess.TimeoutExpired:
            logger.error(f"Dense reconstruction timed out after {self.config['timeout']} seconds")
            return False
        
        except Exception as e:
            logger.error(f"Error during dense reconstruction: {str(e)}")
            return False
    
    def convert_model(self, input_path, output_path, output_type='PLY'):
        """
        Convert COLMAP model to other formats.
        
        Args:
            input_path (str): Path to the input COLMAP model
            output_path (str): Path to the output file
            output_type (str): Output type ('PLY', 'TXT', 'NVM', 'Bundler')
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input path not found: {input_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Build command
        cmd = [
            self.colmap_path, 'model_converter',
            '--input_path', input_path,
            '--output_path', output_path,
            '--output_type', output_type
        ]
        
        logger.info(f"Running COLMAP model converter: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout']
            )
            
            if process.returncode == 0:
                logger.info(f"Model conversion to {output_type} completed successfully")
                return True
            else:
                logger.error(f"Model conversion failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Model conversion timed out after {self.config['timeout']} seconds")
            return False
        
        except Exception as e:
            logger.error(f"Error during model conversion: {str(e)}")
            return False
    
    def run_automatic_reconstruction(self, image_path=None, workspace_path=None, quality=None):
        """
        Run the COLMAP automatic_reconstructor.
        
        This is a convenience function that runs the entire COLMAP pipeline.
        
        Args:
            image_path (str): Path to the input images
            workspace_path (str): Path to the COLMAP workspace
            quality (str): Quality preset to use
        
        Returns:
            bool: True if successful, False otherwise
        """
        image_path = image_path or self.image_path
        workspace_path = workspace_path or self.workspace_path
        
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image directory not found: {image_path}")
        
        if not workspace_path:
            raise ValueError("Workspace path must be provided")
        
        # Create workspace directory
        os.makedirs(workspace_path, exist_ok=True)
        
        # Apply quality preset if provided
        if quality:
            self._apply_quality_preset(quality)
        
        # Determine GPU usage
        use_gpu = self.is_gpu_available()
        
        # Build command
        cmd = [
            self.colmap_path, 'automatic_reconstructor',
            '--workspace_path', workspace_path,
            '--image_path', image_path,
            '--quality', self.config['quality']
        ]
        
        if not use_gpu:
            cmd.extend(['--dense', '0'])
        
        logger.info(f"Running COLMAP automatic reconstructor: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.config['timeout'] * 2  # Double timeout for full pipeline
            )
            
            if process.returncode == 0:
                logger.info("Automatic reconstruction completed successfully")
                return True
            else:
                logger.error(f"Automatic reconstruction failed with return code {process.returncode}")
                logger.error(f"stdout: {process.stdout}")
                logger.error(f"stderr: {process.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Automatic reconstruction timed out")
            return False
        
        except Exception as e:
            logger.error(f"Error during automatic reconstruction: {str(e)}")
            return False

# Convenience function for quick reconstruction
def run_reconstruction(image_path, output_path, quality='medium', use_gpu='auto'):
    """
    Run the full reconstruction pipeline.
    
    Args:
        image_path (str): Path to the input images
        output_path (str): Path for the reconstruction output
        quality (str): Quality preset ('low', 'medium', 'high')
        use_gpu (str/bool): Whether to use GPU ('auto', True, False)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create output directory
        os.makedirs(output_path, exist_ok=True)
        
        # Create workspace paths
        workspace_path = os.path.join(output_path, 'colmap_workspace')
        database_path = os.path.join(workspace_path, 'database', 'database.db')
        sparse_path = os.path.join(workspace_path, 'sparse')
        dense_path = os.path.join(workspace_path, 'dense')
        mesh_path = os.path.join(output_path, 'mesh')
        
        # Create subdirectories
        for path in [workspace_path, os.path.dirname(database_path), sparse_path, dense_path, mesh_path]:
            os.makedirs(path, exist_ok=True)
        
        # Initialize COLMAP wrapper
        colmap = ColmapWrapper(
            workspace_path=workspace_path,
            image_path=image_path
        )
        
        # Set configuration
        colmap.set_config(
            quality=quality,
            use_gpu=use_gpu
        )
        
        # Run feature extraction
        logger.info("Starting feature extraction")
        if not colmap.run_feature_extraction(database_path=database_path):
            logger.error("Feature extraction failed")
            return False
        
        # Run feature matching
        logger.info("Starting feature matching")
        if not colmap.run_feature_matching(database_path=database_path):
            logger.error("Feature matching failed")
            return False
        
        # Run sparse reconstruction
        logger.info("Starting sparse reconstruction")
        if not colmap.run_sparse_reconstruction(
            database_path=database_path,
            image_path=image_path,
            output_path=sparse_path
        ):
            logger.error("Sparse reconstruction failed")
            return False
        
        # Convert sparse model to PLY
        logger.info("Converting sparse model to PLY")
        sparse_ply_path = os.path.join(sparse_path, 'sparse.ply')
        if not colmap.convert_model(
            input_path=os.path.join(sparse_path, '0'),
            output_path=sparse_ply_path,
            output_type='PLY'
        ):
            logger.error("Model conversion failed")
            return False
        
        # Try dense reconstruction if GPU is available
        use_gpu = colmap.is_gpu_available()
        if use_gpu:
            logger.info("Starting dense reconstruction")
            if colmap.run_dense_reconstruction():
                logger.info("Dense reconstruction completed successfully")
                
                # Return success with information about the reconstruction
                return {
                    'success': True,
                    'sparse_reconstruction': os.path.join(sparse_path, '0'),
                    'sparse_pointcloud': sparse_ply_path,
                    'dense_pointcloud': os.path.join(dense_path, 'fused.ply'),
                    'workspace_path': workspace_path
                }
        
        # If dense reconstruction was skipped or failed, return the sparse reconstruction
        return {
            'success': True,
            'sparse_reconstruction': os.path.join(sparse_path, '0'),
            'sparse_pointcloud': sparse_ply_path,
            'workspace_path': workspace_path
        }
        
    except Exception as e:
        logger.error(f"Error during reconstruction: {str(e)}")
        return {'success': False, 'error': str(e)} 