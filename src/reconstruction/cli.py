#!/usr/bin/env python3
"""
Reconstruction CLI

This module provides a command-line interface for running the 3D reconstruction pipeline.
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("reconstruction")

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.reconstruction.colmap import ColmapWrapper
from src.reconstruction.mesh import MeshGenerator


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="3D Reconstruction Pipeline")
    
    # Input/output options
    parser.add_argument("image_set", help="Path to the image set directory")
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: ./output/<image_set_name>)")
    
    # Pipeline options
    parser.add_argument("--quality", choices=["low", "medium", "high"], default="medium", 
                        help="Quality preset for reconstruction")
    parser.add_argument("--use-gpu", choices=["auto", "true", "false"], default="auto",
                        help="Whether to use GPU for reconstruction")
    
    # Mesh generation options
    parser.add_argument("--mesh-method", choices=["open3d", "poisson", "delaunay"], default="open3d",
                        help="Method for generating mesh")
    parser.add_argument("--depth", type=int, default=9, 
                        help="Octree depth for Poisson reconstruction")
    parser.add_argument("--trim", type=float, default=7.0,
                        help="Density percentile to trim from mesh")
    parser.add_argument("--voxel-size", type=float, default=0.01,
                        help="Voxel size for downsampling point cloud")
    
    # Skip steps
    parser.add_argument("--skip-colmap", action="store_true", 
                        help="Skip COLMAP reconstruction (assumes it's already done)")
    parser.add_argument("--skip-mesh", action="store_true",
                        help="Skip mesh generation")
    
    # COLMAP options
    parser.add_argument("--colmap-path", default="colmap",
                        help="Path to COLMAP executable")
    
    # Verbose output
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")
    
    return parser.parse_args()


def main():
    """Main CLI entry point."""
    args = parse_args()
    
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input path
    image_path = os.path.abspath(args.image_set)
    if not os.path.exists(image_path):
        logger.error(f"Image set path does not exist: {image_path}")
        return 1
    
    # Determine image set name and output path
    image_set_name = os.path.basename(image_path.rstrip('/'))
    output_path = args.output or os.path.join(os.path.dirname(os.path.dirname(image_path)), 'output', image_set_name)
    
    # Create output directory
    os.makedirs(output_path, exist_ok=True)
    
    # Set up paths
    workspace_path = os.path.join(output_path, 'colmap_workspace')
    dense_path = os.path.join(workspace_path, 'dense')
    sparse_path = os.path.join(workspace_path, 'sparse')
    database_path = os.path.join(workspace_path, 'database', 'database.db')
    mesh_path = os.path.join(output_path, 'mesh')
    mesh_output_path = os.path.join(mesh_path, 'reconstructed_mesh.obj')
    
    # Create directories
    for path in [workspace_path, os.path.dirname(database_path), sparse_path, dense_path, mesh_path]:
        os.makedirs(path, exist_ok=True)
    
    # Set up log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(output_path, f"reconstruction_run_{timestamp}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    
    logger.info(f"Starting reconstruction for image set: {image_set_name}")
    logger.info(f"Output directory: {output_path}")
    
    # Convert use_gpu string to boolean or None
    use_gpu = None
    if args.use_gpu.lower() == "true":
        use_gpu = True
    elif args.use_gpu.lower() == "false":
        use_gpu = False
    
    # Run COLMAP reconstruction
    sparse_ply_path = os.path.join(sparse_path, 'sparse.ply')
    dense_ply_path = os.path.join(dense_path, 'fused.ply')
    
    # Initialize result information
    result = {
        'image_set': image_set_name,
        'output_path': output_path,
        'timestamp': timestamp,
        'colmap': {
            'completed': False,
            'sparse_reconstruction': None,
            'dense_reconstruction': None
        },
        'mesh': {
            'completed': False,
            'path': None
        }
    }
    
    if not args.skip_colmap:
        try:
            logger.info("Initializing COLMAP wrapper")
            colmap = ColmapWrapper(
                colmap_path=args.colmap_path,
                workspace_path=workspace_path,
                image_path=image_path
            )
            
            # Set configuration
            colmap.set_config(
                quality=args.quality,
                use_gpu=use_gpu
            )
            
            # Run feature extraction
            logger.info("Starting feature extraction")
            if not colmap.run_feature_extraction(database_path=database_path):
                logger.error("Feature extraction failed. Exiting...")
                return 1
            
            # Run feature matching
            logger.info("Starting feature matching")
            if not colmap.run_feature_matching(database_path=database_path):
                logger.error("Feature matching failed. Exiting...")
                return 1
            
            # Run sparse reconstruction
            logger.info("Starting sparse reconstruction")
            if not colmap.run_sparse_reconstruction(
                database_path=database_path,
                image_path=image_path,
                output_path=sparse_path
            ):
                logger.error("Sparse reconstruction failed. Exiting...")
                return 1
            
            # Convert sparse model to PLY
            logger.info("Converting sparse model to PLY")
            if not colmap.convert_model(
                input_path=os.path.join(sparse_path, '0'),
                output_path=sparse_ply_path,
                output_type='PLY'
            ):
                logger.error("Model conversion failed. Exiting...")
                return 1
            
            # Set result information
            result['colmap']['completed'] = True
            result['colmap']['sparse_reconstruction'] = os.path.join(sparse_path, '0')
            result['colmap']['sparse_pointcloud'] = sparse_ply_path
            
            # Try dense reconstruction if GPU is available
            actual_use_gpu = colmap.is_gpu_available()
            if actual_use_gpu:
                logger.info("Starting dense reconstruction")
                if colmap.run_dense_reconstruction():
                    logger.info("Dense reconstruction completed successfully")
                    result['colmap']['dense_reconstruction'] = os.path.join(dense_path, 'fused.ply')
                else:
                    logger.warning("Dense reconstruction failed, will use sparse reconstruction for meshing")
            else:
                logger.warning("No GPU available for dense reconstruction, will use sparse reconstruction for meshing")
            
        except Exception as e:
            logger.error(f"Error during COLMAP reconstruction: {str(e)}")
            return 1
    else:
        logger.info("Skipping COLMAP reconstruction (--skip-colmap specified)")
        
        # Check if necessary files exist
        if not os.path.exists(sparse_ply_path):
            logger.error(f"Sparse point cloud not found: {sparse_ply_path}")
            return 1
        
        result['colmap']['completed'] = True
        result['colmap']['sparse_reconstruction'] = os.path.join(sparse_path, '0')
        result['colmap']['sparse_pointcloud'] = sparse_ply_path
        
        if os.path.exists(dense_ply_path):
            result['colmap']['dense_reconstruction'] = dense_ply_path
    
    # Generate mesh if not skipped
    if not args.skip_mesh:
        try:
            logger.info(f"Generating mesh using {args.mesh_method} method")
            
            # Determine input point cloud
            input_ply = result['colmap']['dense_reconstruction'] or result['colmap']['sparse_pointcloud']
            
            if not input_ply or not os.path.exists(input_ply):
                logger.error(f"Point cloud not found: {input_ply}")
                return 1
            
            # Initialize mesh generator
            mesh_generator = MeshGenerator(
                method=args.mesh_method,
                config={
                    'octree_depth': args.depth,
                    'trim_threshold': args.trim,
                    'voxel_size': args.voxel_size,
                    'colmap_path': args.colmap_path
                }
            )
            
            # Generate mesh
            mesh_info = mesh_generator.generate(input_ply, mesh_output_path)
            
            logger.info(f"Mesh generation completed successfully: {mesh_info}")
            result['mesh']['completed'] = True
            result['mesh']['path'] = mesh_output_path
            result['mesh']['info'] = mesh_info
            
        except Exception as e:
            logger.error(f"Error during mesh generation: {str(e)}")
            return 1
    else:
        logger.info("Skipping mesh generation (--skip-mesh specified)")
    
    # Write result information to file
    result_file = os.path.join(output_path, f"reconstruction_result_{timestamp}.json")
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Reconstruction completed successfully!")
    logger.info(f"Output saved to: {output_path}")
    
    if result['mesh']['completed']:
        logger.info(f"Mesh saved to: {result['mesh']['path']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 