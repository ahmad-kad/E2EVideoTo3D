#!/usr/bin/env python3

import os
import sys
import numpy as np
import open3d as o3d
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MeshGeneration')

def generate_mesh_from_point_cloud(input_ply, output_obj, depth=9, voxel_size=None):
    """
    Generate a mesh from a point cloud using Poisson surface reconstruction.
    
    Args:
        input_ply: Path to the input PLY point cloud file
        output_obj: Path to save the output OBJ mesh file
        depth: Depth parameter for Poisson reconstruction (higher = more detail)
        voxel_size: If not None, downsample the point cloud with this voxel size
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load the point cloud
        logger.info(f"Loading point cloud from {input_ply}")
        pcd = o3d.io.read_point_cloud(input_ply)
        
        # Print point cloud information
        logger.info(f"Point cloud has {len(pcd.points)} points")
        
        # Downsample if requested
        if voxel_size is not None:
            logger.info(f"Downsampling with voxel size {voxel_size}")
            pcd = pcd.voxel_down_sample(voxel_size)
            logger.info(f"After downsampling: {len(pcd.points)} points")
        
        # Estimate normals if not present
        if not pcd.has_normals():
            logger.info("Estimating normals")
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
            pcd.orient_normals_consistent_tangent_plane(20)
        
        # Perform Poisson surface reconstruction
        logger.info(f"Performing Poisson reconstruction with depth {depth}")
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=depth)
        
        # Remove low-density vertices (optional)
        logger.info("Removing low-density vertices")
        vertices_to_remove = densities < np.quantile(densities, 0.1)
        mesh.remove_vertices_by_mask(vertices_to_remove)
        
        # Clean mesh
        logger.info("Cleaning mesh (removing unreferenced vertices)")
        mesh.remove_unreferenced_vertices()
        
        # Save mesh
        logger.info(f"Saving mesh to {output_obj}")
        o3d.io.write_triangle_mesh(output_obj, mesh)
        
        logger.info("Mesh generation completed successfully!")
        return True
    
    except Exception as e:
        logger.error(f"Error generating mesh: {e}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_mesh.py <input_ply> <output_obj> [depth] [voxel_size]")
        sys.exit(1)
    
    input_ply = sys.argv[1]
    output_obj = sys.argv[2]
    
    # Optional parameters
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 9
    voxel_size = float(sys.argv[4]) if len(sys.argv) > 4 else None
    
    if not os.path.exists(input_ply):
        logger.error(f"Input PLY file does not exist: {input_ply}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_obj)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    success = generate_mesh_from_point_cloud(input_ply, output_obj, depth, voxel_size)
    if not success:
        logger.error("Mesh generation failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 