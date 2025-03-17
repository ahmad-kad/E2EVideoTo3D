# Multiple Image Sets Reconstruction Pipeline

This guide explains how to use the multi-reconstruction pipeline to process multiple image sets for different scenes or objects.

## Overview

The multi-reconstruction pipeline allows you to process multiple sets of images (from different scenes or objects) in a single batch run. Each image set is processed independently, resulting in separate 3D reconstructions for each set.

The pipeline implements a complete ETL (Extract, Transform, Load) workflow:
- **Extract**: Read images from each image set
- **Transform**: Process through reconstruction stages (feature extraction, matching, sparse/dense reconstruction, meshing)
- **Load**: Output 3D models (point clouds and meshes) for each image set

## Directory Structure

- `/image_sets/` - The main directory to store your image sets
  - `/image_sets/scene1/` - Directory for the first image set
  - `/image_sets/scene2/` - Directory for the second image set
  - `/image_sets/scene3/` - Directory for the third image set
  - etc.

## How to Use

### 1. Prepare Your Image Sets

1. Place each image set in a separate directory under the `image_sets` folder
2. Each directory should contain the images for a specific scene or object
3. Supported image formats: JPG and PNG

You can use the provided helper script to manage your image sets:

```bash
# List existing image sets
./setup_image_sets.sh list

# Create a new image set directory
./setup_image_sets.sh create-set my_new_scene

# Move images from input/ to an image set
./setup_image_sets.sh move-input my_scene
```

Example structure:
```
image_sets/
├── house_exterior/
│   ├── image001.jpg
│   ├── image002.jpg
│   └── ...
├── statue/
│   ├── image001.jpg
│   ├── image002.jpg
│   └── ...
└── toy_car/
    ├── image001.jpg
    ├── image002.jpg
    └── ...
```

### 2. Run the Pipeline

You can run the multi-reconstruction pipeline using the Airflow UI or command line:

#### Using Airflow UI
1. Navigate to the Airflow UI (typically at http://localhost:8080)
2. Find the DAG named `multi_reconstruction_pipeline`
3. Trigger the DAG manually

#### Using Command Line
```bash
airflow dags trigger multi_reconstruction_pipeline
```

### 3. Monitor Progress

You can monitor the progress of each image set reconstruction in the Airflow UI. The pipeline creates separate tasks for each image set, making it easy to track their individual progress.

For each image set, the pipeline will:
1. Run feature extraction and matching
2. Perform sparse reconstruction
3. Perform dense reconstruction
4. Generate a 3D mesh
5. Output the final results

### 4. Outputs

The reconstruction outputs for each image set will be stored in:
```
output/
├── scene1/
│   ├── point_cloud.ply       # The dense point cloud
│   ├── mesh.ply              # The generated 3D mesh
│   ├── colmap_workspace/     # Workspace with intermediate files
│   └── metadata.json         # Processing information and statistics
├── scene2/
│   ├── point_cloud.ply
│   ├── mesh.ply
│   ├── colmap_workspace/
│   └── metadata.json
└── ...
```

## Configuration Options

### Quality Presets

The pipeline uses quality presets for the reconstruction process:

- **Low quality**: Faster processing, lower quality results
- **Medium quality**: Balanced processing time and quality (default)
- **High quality**: Best results, but slower processing

You can set the quality preset using the `QUALITY_PRESET` environment variable.

### Meshing Options

You can configure mesh generation with these environment variables:

- `MESHING_TOOL`: Choose between 'poisson' (default), 'delaunay', or 'open3d'
- `MESH_OCTREE_DEPTH`: Controls mesh detail (default: 9)
- `MESH_POINT_WEIGHT`: Weight for input points (default: 1)
- `MESH_TRIM`: Threshold for removing low-density vertices (default: 7)

## Troubleshooting

- **No image sets found**: Make sure you have created subdirectories in the `image_sets` folder and that they contain images.
- **GPU not detected**: If available, enable GPU acceleration by setting `USE_COLMAP_DOCKER=true` in your environment variables.
- **Mesh generation fails**: Ensure you have the right meshing tools installed. By default, the pipeline attempts to use PoissonRecon or falls back to Open3D.
- **Pipeline fails**: Check the Airflow logs for details. The most common issues are related to insufficient memory for larger image sets.

## Technical Details

The multi-reconstruction pipeline uses a COLMAP-based reconstruction process and runs it on each image set independently. The complete ETL process for each image set:

1. **Extraction**: Read images from the image set directory
2. **Transformation**:
   - Feature extraction: Extract SIFT features from images
   - Feature matching: Match features between image pairs
   - Sparse reconstruction: Camera pose estimation and sparse point cloud generation
   - Dense reconstruction: Dense point cloud generation (undistortion, stereo matching, fusion)
   - Mesh generation: Convert the point cloud to a 3D mesh using Poisson reconstruction
3. **Loading**:
   - Save the point cloud, mesh, and metadata to the output directory
   - Generate a completion marker for tracking 