#!/usr/bin/env python3

import os
import sys
import open3d as o3d
import numpy as np

def visualize_mesh(mesh_path):
    """
    Visualize a mesh using Open3D.
    
    Args:
        mesh_path: Path to the mesh file (OBJ, PLY, etc.)
    """
    print(f"Loading mesh from {mesh_path}")
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # Print mesh information
    print(f"Mesh has {len(mesh.vertices)} vertices and {len(mesh.triangles)} triangles")
    
    # Compute normals if not present
    if not mesh.has_vertex_normals():
        print("Computing vertex normals")
        mesh.compute_vertex_normals()
    
    # Add color if not present
    if not mesh.has_vertex_colors():
        print("Adding default vertex colors")
        mesh.vertex_colors = o3d.utility.Vector3dVector(
            np.ones((len(mesh.vertices), 3)) * np.array([0.7, 0.7, 0.7])
        )
    
    # Create a coordinate frame for reference
    coordinate_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
        size=0.5, origin=[0, 0, 0]
    )
    
    # Visualize the mesh
    print("Visualizing mesh (press 'q' to exit)")
    o3d.visualization.draw_geometries([mesh, coordinate_frame])

def main():
    if len(sys.argv) < 2:
        print("Usage: python visualize_mesh.py <mesh_file>")
        sys.exit(1)
    
    mesh_path = sys.argv[1]
    
    if not os.path.exists(mesh_path):
        print(f"Error: Mesh file does not exist: {mesh_path}")
        sys.exit(1)
    
    visualize_mesh(mesh_path)

if __name__ == "__main__":
    main() 