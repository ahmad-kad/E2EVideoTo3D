#!/usr/bin/env python3
"""
Mesh Generation Module

This module provides functions for generating meshes from point clouds using
different algorithms and approaches.
"""

import os
import sys
import json
import logging
import numpy as np
import subprocess
from datetime import datetime
from pathlib import Path

# Configure logging
logger = logging.getLogger("reconstruction.mesh")

class MeshGenerator:
    """
    Class for generating meshes from point clouds using different methods.
    """
    
    def __init__(self, method='open3d', config=None):
        """
        Initialize the mesh generator.
        
        Args:
            method (str): The meshing method to use ('open3d', 'poisson', or 'delaunay')
            config (dict): Optional configuration parameters
        """
        self.method = method.lower()
        self.config = config or {}
        
        # Set default parameters
        self.defaults = {
            'octree_depth': 9,
            'point_weight': 1.0,
            'trim_threshold': 7.0,
            'voxel_size': 0.01,
            'colmap_path': 'colmap',
            'timeout': 300  # 5 minutes
        }
        
        # Merge defaults with provided config
        for key, value in self.defaults.items():
            if key not in self.config:
                self.config[key] = value
    
    def generate(self, input_path, output_path, **kwargs):
        """
        Generate a mesh from a point cloud.
        
        Args:
            input_path (str): Path to the input point cloud file
            output_path (str): Path to save the output mesh file
            **kwargs: Additional method-specific parameters
        
        Returns:
            dict: Information about the generated mesh
        """
        # Update config with any provided kwargs
        for key, value in kwargs.items():
            self.config[key] = value
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Choose the appropriate method
        if self.method == 'open3d':
            return self.generate_with_open3d(input_path, output_path)
        elif self.method == 'poisson':
            return self.generate_with_colmap_poisson(input_path, output_path)
        elif self.method == 'delaunay':
            return self.generate_with_colmap_delaunay(input_path, output_path)
        else:
            raise ValueError(f"Unsupported meshing method: {self.method}")
    
    def generate_with_open3d(self, input_path, output_path):
        """
        Generate a mesh using Open3D's Poisson reconstruction.
        
        Args:
            input_path (str): Path to the input point cloud (PLY file)
            output_path (str): Path to save the output mesh (typically OBJ or PLY)
        
        Returns:
            dict: Information about the generated mesh
        """
        try:
            import open3d as o3d
            
            logger.info(f"Loading point cloud from {input_path}")
            pcd = o3d.io.read_point_cloud(input_path)
            
            # Report point cloud statistics
            num_points = len(pcd.points)
            logger.info(f"Point cloud has {num_points} points")
            
            # Downsample if requested
            voxel_size = self.config.get('voxel_size', None)
            if voxel_size is not None and voxel_size > 0:
                logger.info(f"Downsampling with voxel size {voxel_size}")
                pcd = pcd.voxel_down_sample(voxel_size)
                logger.info(f"After downsampling: {len(pcd.points)} points")
            
            # Estimate normals if not present
            if not pcd.has_normals():
                logger.info("Estimating normals")
                pcd.estimate_normals(
                    search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
                )
                pcd.orient_normals_consistent_tangent_plane(20)
            
            # Perform Poisson surface reconstruction
            depth = int(self.config.get('octree_depth', 9))
            logger.info(f"Performing Poisson reconstruction with depth {depth}")
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=depth, width=0, scale=1.1, linear_fit=False
            )
            
            # Remove low-density vertices
            threshold = float(self.config.get('trim_threshold', 7))
            logger.info(f"Filtering mesh with density threshold: {threshold}")
            density_threshold = np.percentile(densities, threshold)
            vertices_to_remove = densities < density_threshold
            mesh.remove_vertices_by_mask(vertices_to_remove)
            
            # Clean mesh
            logger.info("Cleaning mesh (removing unreferenced vertices)")
            mesh.remove_unreferenced_vertices()
            
            # Save mesh
            logger.info(f"Saving mesh to {output_path}")
            o3d.io.write_triangle_mesh(output_path, mesh)
            
            # Return mesh information
            mesh_info = {
                'file_path': output_path,
                'original_points': num_points,
                'final_vertices': len(mesh.vertices),
                'triangles': len(mesh.triangles),
                'method': 'open3d_poisson',
                'config': {
                    'depth': depth,
                    'voxel_size': voxel_size,
                    'trim_threshold': threshold
                }
            }
            
            logger.info(f"Mesh generation completed: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
            return mesh_info
            
        except ImportError as e:
            logger.error(f"Open3D not available: {str(e)}")
            raise ImportError("Open3D is required for this meshing method. Install with 'pip install open3d'")
        
        except Exception as e:
            logger.error(f"Error during Open3D mesh generation: {str(e)}")
            raise
    
    def generate_with_colmap_poisson(self, input_path, output_path):
        """
        Generate a mesh using COLMAP's Poisson mesher.
        
        Args:
            input_path (str): Path to the input point cloud
            output_path (str): Path to save the output mesh
        
        Returns:
            dict: Information about the generated mesh
        """
        colmap_path = self.config.get('colmap_path', 'colmap')
        depth = self.config.get('octree_depth', 9)
        point_weight = self.config.get('point_weight', 1)
        
        cmd = [
            colmap_path, 'poisson_mesher',
            '--input_path', input_path,
            '--output_path', output_path,
            '--PoissonMeshing.depth', str(depth),
            '--PoissonMeshing.point_weight', str(point_weight)
        ]
        
        logger.info(f"Running COLMAP poisson mesher: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=self.config.get('timeout', 300)
            )
            
            logger.info(f"COLMAP poisson_mesher stdout: {process.stdout}")
            if process.stderr:
                logger.warning(f"COLMAP poisson_mesher stderr: {process.stderr}")
            
            # We can't get exact mesh statistics from COLMAP output
            mesh_info = {
                'file_path': output_path,
                'method': 'colmap_poisson',
                'config': {
                    'depth': depth,
                    'point_weight': point_weight
                }
            }
            
            logger.info(f"Mesh generation completed successfully: {output_path}")
            return mesh_info
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"COLMAP mesher timed out after {self.config.get('timeout')} seconds")
            raise TimeoutError(f"Mesh generation timed out: {str(e)}")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"COLMAP mesher failed with return code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise RuntimeError(f"Mesh generation failed: {str(e)}")
    
    def generate_with_colmap_delaunay(self, input_path, output_path):
        """
        Generate a mesh using COLMAP's Delaunay mesher.
        
        Args:
            input_path (str): Path to the sparse reconstruction directory
            output_path (str): Path to save the output mesh
        
        Returns:
            dict: Information about the generated mesh
        """
        colmap_path = self.config.get('colmap_path', 'colmap')
        
        cmd = [
            colmap_path, 'delaunay_mesher',
            '--input_path', input_path,
            '--output_path', output_path
        ]
        
        logger.info(f"Running COLMAP delaunay_mesher: {' '.join(cmd)}")
        
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=self.config.get('timeout', 300)
            )
            
            logger.info(f"COLMAP delaunay_mesher stdout: {process.stdout}")
            if process.stderr:
                logger.warning(f"COLMAP delaunay_mesher stderr: {process.stderr}")
            
            mesh_info = {
                'file_path': output_path,
                'method': 'colmap_delaunay',
            }
            
            logger.info(f"Mesh generation completed successfully: {output_path}")
            return mesh_info
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"COLMAP mesher timed out after {self.config.get('timeout')} seconds")
            raise TimeoutError(f"Mesh generation timed out: {str(e)}")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"COLMAP mesher failed with return code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise RuntimeError(f"Mesh generation failed: {str(e)}")

def generate_mesh(input_path, output_path, method='open3d', **kwargs):
    """
    Convenience function to generate a mesh without explicitly creating a MeshGenerator instance.
    
    Args:
        input_path (str): Path to the input point cloud
        output_path (str): Path to save the output mesh
        method (str): The meshing method to use
        **kwargs: Additional method-specific parameters
    
    Returns:
        dict: Information about the generated mesh
    """
    generator = MeshGenerator(method=method, config=kwargs)
    return generator.generate(input_path, output_path) 