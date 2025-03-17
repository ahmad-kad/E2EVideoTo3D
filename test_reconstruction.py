#!/usr/bin/env python3
"""
Test Reconstruction Script

This script runs a simplified version of the reconstruction pipeline on a specified image set.
It doesn't depend on Airflow and can be run directly to test if mesh generation works.
"""

import os
import glob
import json
import logging
import subprocess
from datetime import datetime
import shutil

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("test_reconstruction")

# Configure paths
PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
IMAGE_SETS_PATH = os.path.join(PROJECT_PATH, 'image_sets')
OUTPUT_PATH = os.path.join(PROJECT_PATH, 'output')
COLMAP_PATH = 'colmap'  # Assuming colmap is in PATH

# Set default meshing options
MESHING_TOOL = 'open3d'  # Using Open3D since we installed it
MESH_OCTREE_DEPTH = '9'
MESH_POINT_WEIGHT = '1'
MESH_TRIM = '7'

# Quality settings (medium preset)
QUALITY_PRESET = 'medium'
FEATURE_EXTRACTOR_ARGS = "--SiftExtraction.max_image_size 2000 --SiftExtraction.estimate_affine_shape 0 --SiftExtraction.domain_size_pooling 0"
MAX_NUM_MATCHES = "25000"
SPARSE_ARGS = "--bundle_adjustment_max_iterations 50"
DENSE_MAX_IMAGE_SIZE = "1500"


def is_gpu_available():
    """Check if GPU is available for computation"""
    try:
        # Try to import CUDA modules
        import torch
        return torch.cuda.is_available()
    except ImportError:
        # If torch is not available, try nvidia-smi
        try:
            subprocess.check_output(['nvidia-smi'], stderr=subprocess.STDOUT)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    logger.warning("GPU not detected. Using CPU for reconstruction (this will be slow).")
    return False


def run_colmap_command(cmd_args, timeout_seconds=7200):
    """
    Run a COLMAP command
    
    Args:
        cmd_args: List of command arguments for COLMAP
        timeout_seconds: Maximum execution time in seconds
    
    Returns:
        Command output
    """
    # Run COLMAP directly
    colmap_cmd = [COLMAP_PATH] + cmd_args
    logger.info(f"Running COLMAP command: {' '.join(colmap_cmd)}")
    result = subprocess.run(colmap_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds)
    
    # Log command output
    if result.stdout:
        logger.info(f"COLMAP command stdout: {result.stdout.decode('utf-8')}")
    if result.stderr:
        logger.warning(f"COLMAP command stderr: {result.stderr.decode('utf-8')}")
    
    return result


def run_reconstruction(image_set_name):
    """
    Run the full reconstruction pipeline for a specific image set
    
    Args:
        image_set_name: Name of the image set to process
        
    Returns:
        Dictionary with mesh information
    """
    # Create paths
    image_set_dir = os.path.join(IMAGE_SETS_PATH, image_set_name)
    output_base_dir = os.path.join(OUTPUT_PATH, image_set_name)
    workspace_dir = os.path.join(output_base_dir, 'colmap_workspace')
    
    # Create workspace directories
    os.makedirs(workspace_dir, exist_ok=True)
    sparse_dir = os.path.join(workspace_dir, 'sparse')
    os.makedirs(sparse_dir, exist_ok=True)
    dense_dir = os.path.join(workspace_dir, 'dense')
    os.makedirs(dense_dir, exist_ok=True)
    
    # Create a database directory
    database_dir = os.path.join(workspace_dir, 'database')
    os.makedirs(database_dir, exist_ok=True)
    database_path = os.path.join(database_dir, 'database.db')
    
    # Log the workspace creation
    logger.info(f"Created COLMAP workspace for {image_set_name}:")
    logger.info(f" - Workspace: {workspace_dir}")
    logger.info(f" - Database: {database_path}")
    logger.info(f" - Sparse: {sparse_dir}")
    logger.info(f" - Dense: {dense_dir}")
    
    # 1. Feature extraction
    try:
        # Build the COLMAP command for feature extraction
        extraction_args = [
            'feature_extractor',
            '--database_path', database_path,
            '--image_path', image_set_dir
        ]
        
        # Add quality-specific arguments
        extraction_args.extend(FEATURE_EXTRACTOR_ARGS.split())
        
        # Add GPU options if available
        if is_gpu_available():
            extraction_args.extend(['--SiftExtraction.use_gpu', '1'])
        else:
            extraction_args.extend(['--SiftExtraction.use_gpu', '0'])
        
        logger.info(f"Running COLMAP feature extraction for {image_set_name}")
        
        # Run feature extraction
        extraction_result = run_colmap_command(extraction_args)
        
        logger.info(f"COLMAP feature extraction completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Feature extraction failed for {image_set_name}: {str(e)}")
        raise Exception(f"Feature extraction failed: {str(e)}")
    
    # 2. Feature matching
    try:
        # Build the COLMAP command for feature matching
        matching_args = [
            'exhaustive_matcher',
            '--database_path', database_path,
            '--SiftMatching.max_num_matches', MAX_NUM_MATCHES
        ]
        
        # Add GPU options if available
        if is_gpu_available():
            matching_args.extend(['--SiftMatching.use_gpu', '1'])
        else:
            matching_args.extend(['--SiftMatching.use_gpu', '0'])
        
        logger.info(f"Running COLMAP feature matching for {image_set_name}")
        
        # Run feature matching
        matching_result = run_colmap_command(matching_args)
        
        logger.info(f"COLMAP feature matching completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Feature matching failed for {image_set_name}: {str(e)}")
        raise Exception(f"Feature matching failed: {str(e)}")
    
    # 3. Sparse reconstruction
    try:
        # Create sparse model directory
        sparse_model_dir = os.path.join(sparse_dir, '0')
        os.makedirs(sparse_model_dir, exist_ok=True)
        
        # Build the COLMAP command for mapper
        mapper_args = [
            'mapper',
            '--database_path', database_path,
            '--image_path', image_set_dir,
            '--output_path', sparse_model_dir
        ]
        
        # Add quality-specific arguments
        mapper_args.extend(SPARSE_ARGS.split())
        
        logger.info(f"Running COLMAP sparse reconstruction for {image_set_name}")
        
        # Run mapper
        mapper_result = run_colmap_command(mapper_args)
        
        logger.info(f"COLMAP sparse reconstruction completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Sparse reconstruction failed for {image_set_name}: {str(e)}")
        raise Exception(f"Sparse reconstruction failed: {str(e)}")
    
    # 4. Image undistortion for dense reconstruction
    try:
        # Build the COLMAP command for image undistortion
        undistort_args = [
            'image_undistorter',
            '--image_path', image_set_dir,
            '--input_path', sparse_model_dir,
            '--output_path', dense_dir,
            '--max_image_size', DENSE_MAX_IMAGE_SIZE
        ]
        
        logger.info(f"Running COLMAP image undistortion for {image_set_name}")
        
        # Run image undistortion
        undistort_result = run_colmap_command(undistort_args)
        
        logger.info(f"COLMAP image undistortion completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Image undistortion failed for {image_set_name}: {str(e)}")
        raise Exception(f"Image undistortion failed: {str(e)}")
    
    # 5. Stereo matching
    try:
        # Build the COLMAP command for stereo matching
        stereo_args = [
            'patch_match_stereo',
            '--workspace_path', dense_dir
        ]
        
        # Add GPU options if available
        if is_gpu_available():
            stereo_args.extend(['--PatchMatchStereo.gpu_index', '0'])
        
        logger.info(f"Running COLMAP stereo matching for {image_set_name}")
        
        # Run stereo matching
        stereo_result = run_colmap_command(stereo_args)
        
        logger.info(f"COLMAP stereo matching completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Stereo matching failed for {image_set_name}: {str(e)}")
        raise Exception(f"Stereo matching failed: {str(e)}")
    
    # 6. Stereo fusion
    try:
        # Output path for the fused point cloud
        fused_ply_path = os.path.join(dense_dir, 'fused.ply')
        
        # Build the COLMAP command for stereo fusion
        fusion_args = [
            'stereo_fusion',
            '--workspace_path', dense_dir,
            '--output_path', fused_ply_path
        ]
        
        logger.info(f"Running COLMAP stereo fusion for {image_set_name}")
        
        # Run stereo fusion
        fusion_result = run_colmap_command(fusion_args)
        
        logger.info(f"COLMAP stereo fusion completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Stereo fusion failed for {image_set_name}: {str(e)}")
        raise Exception(f"Stereo fusion failed: {str(e)}")
    
    # 7. Generate mesh from point cloud
    try:
        # Set up mesh output path
        mesh_output_path = os.path.join(output_base_dir, 'mesh.ply')
        
        logger.info(f"Generating mesh for {image_set_name} using {MESHING_TOOL} method")
        
        if MESHING_TOOL.lower() == 'open3d':
            # Simple mesh generation using Open3D
            import open3d as o3d
            
            logger.info(f"Reading point cloud from {fused_ply_path}")
            pcd = o3d.io.read_point_cloud(fused_ply_path)
            
            logger.info(f"Estimating normals")
            pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
            
            logger.info(f"Creating mesh using Poisson reconstruction")
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=int(MESH_OCTREE_DEPTH), linear_fit=False)
            
            logger.info(f"Removing low density vertices")
            vertices_to_remove = densities < float(MESH_TRIM)
            mesh.remove_vertices_by_mask(vertices_to_remove)
            
            logger.info(f"Saving mesh to {mesh_output_path}")
            o3d.io.write_triangle_mesh(mesh_output_path, mesh)
        
        elif MESHING_TOOL.lower() == 'delaunay':
            # Use COLMAP's delaunay mesher
            cmd = [
                COLMAP_PATH,
                'delaunay_mesher',
                '--input_path', os.path.dirname(fused_ply_path),
                '--output_path', mesh_output_path
            ]
            
            logger.info(f"Running COLMAP delaunay_mesher command: {' '.join(cmd)}")
            
            # Run delaunay_mesher
            process = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.stdout:
                logger.info(f"COLMAP delaunay_mesher stdout: {process.stdout.decode('utf-8')}")
            if process.stderr:
                logger.warning(f"COLMAP delaunay_mesher stderr: {process.stderr.decode('utf-8')}")
        
        # Copy the point cloud to the output directory for easier access
        point_cloud_output_path = os.path.join(output_base_dir, 'point_cloud.ply')
        subprocess.run(['cp', fused_ply_path, point_cloud_output_path], check=True)
        
        # Create a metadata file
        metadata_path = os.path.join(output_base_dir, 'metadata.json')
        metadata = {
            'processed_date': datetime.utcnow().isoformat(),
            'image_set': image_set_name,
            'quality_preset': QUALITY_PRESET,
            'frame_count': len(glob.glob(os.path.join(image_set_dir, "*.jpg")) + 
                            glob.glob(os.path.join(image_set_dir, "*.png"))),
            'meshing_tool': MESHING_TOOL
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Create a completion marker
        with open(os.path.join(output_base_dir, 'COMPLETED'), 'w') as f:
            f.write(datetime.utcnow().isoformat())
        
        logger.info(f"Processing for image set {image_set_name} completed")
        logger.info(f"Outputs available at:")
        logger.info(f" - Point cloud: {point_cloud_output_path}")
        logger.info(f" - Mesh: {mesh_output_path}")
        logger.info(f" - Metadata: {metadata_path}")
        
        return {
            'mesh_path': mesh_output_path,
            'point_cloud_path': point_cloud_output_path,
            'metadata_path': metadata_path,
            'image_set_name': image_set_name
        }
    except Exception as e:
        logger.error(f"Mesh generation failed for {image_set_name}: {str(e)}")
        raise Exception(f"Mesh generation failed: {str(e)}")


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: python test_reconstruction.py <image_set_name>")
        sys.exit(1)
        
    image_set_name = sys.argv[1]
    image_path = os.path.join(os.getcwd(), 'image_sets', image_set_name)
    
    if not os.path.exists(image_path):
        logger.error(f"Image set path does not exist: {image_path}")
        sys.exit(1)
        
    output_path = os.path.join(os.getcwd(), 'output', image_set_name)
    
    # Create necessary directories
    paths = create_directories(output_path)
    
    # Generate a symbolic link to the images for easier access
    images_symlink = os.path.join(paths['colmap_workspace'], 'images')
    if os.path.exists(images_symlink):
        if os.path.islink(images_symlink):
            os.unlink(images_symlink)
        else:
            shutil.rmtree(images_symlink)
    os.symlink(image_path, images_symlink)
    
    # Database path
    database_path = os.path.join(paths['database'], 'database.db')
    
    # Perform feature extraction
    if not feature_extraction(image_path, database_path):
        logger.error("Feature extraction failed. Exiting...")
        sys.exit(1)
        
    # Perform feature matching
    if not feature_matching(database_path):
        logger.error("Feature matching failed. Exiting...")
        sys.exit(1)
    
    # Try triangulation approach instead of sparse reconstruction
    if not triangulation(database_path, image_path, paths['sparse'], paths['colmap_workspace']):
        logger.error("Triangulation failed. Exiting...")
        sys.exit(1)
    
    # Perform dense reconstruction
    if not dense_reconstruction(paths['colmap_workspace'], paths['sparse']):
        logger.error("Dense reconstruction failed. Exiting...")
        sys.exit(1)
        
    # Generate mesh
    ply_path = os.path.join(paths['colmap_workspace'], 'dense/fused.ply')
    if not os.path.exists(ply_path):
        logger.error(f"Point cloud file does not exist: {ply_path}")
        sys.exit(1)
        
    if not generate_mesh(ply_path, paths['mesh']):
        logger.error("Mesh generation failed. Exiting...")
        sys.exit(1)
        
    logger.info("Reconstruction pipeline completed successfully!")
    logger.info(f"Mesh saved to: {os.path.join(paths['mesh'], 'reconstructed_mesh.obj')}")


if __name__ == "__main__":
    main() 