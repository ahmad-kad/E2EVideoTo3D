# E2E3D Reconstruction Pipeline

## Overview

The E2E3D reconstruction pipeline is a complete end-to-end solution for generating 3D meshes from image sequences. It uses photogrammetry techniques to reconstruct 3D models and stores them in MinIO object storage for easy download and further use.

## Requirements

- Docker and Docker Compose
- Image dataset (a sequence of images capturing an object from different angles)
- At least 8GB RAM recommended for reconstruction
- Approximately 10GB free disk space

## Quick Start

For the fastest way to generate a 3D mesh from your images:

```bash
# Start with the workaround solution
# 1. Start MinIO
docker-compose -f docker-compose-minimal-test.yml up -d

# 2. Run the simplified pipeline
USE_DOCKER=false ./simple_run_pipeline.sh /path/to/your/images
```

After completion, you can download your 3D mesh from: http://localhost:9000/models/reconstructed_mesh.obj

## Workaround Solution (Recommended)

Due to issues with building Docker images on some systems, we've created a simplified approach:

### Step 1: Start MinIO Service

```bash
docker-compose -f docker-compose-minimal-test.yml up -d
```

### Step 2: Run the Simplified Pipeline

```bash
# Run with local Python
USE_DOCKER=false ./simple_run_pipeline.sh /path/to/your/images

# OR use existing Docker image if available
USE_DOCKER=true ./simple_run_pipeline.sh /path/to/your/images
```

For more details on the workaround solution, see [WORKAROUND.md](WORKAROUND.md).

## Full Setup Instructions (If Docker Build Works)

### Step 1: Build the Docker Images

We've created a script to build all necessary Docker images with fixed configurations:

```bash
# Make the script executable if needed
chmod +x build_fixed_images.sh

# Build the Docker images
./build_fixed_images.sh
```

This will build the following images:
- `e2e3d-base`: Base image with common dependencies
- `e2e3d-colmap`: COLMAP-enabled image for sparse reconstruction
- `e2e3d-reconstruction`: Main reconstruction image
- `e2e3d-airflow`: Airflow image for pipeline orchestration

### Step 2: Start the Services

To start the full pipeline including MinIO and Airflow:

```bash
# Make the script executable if needed
chmod +x start_pipeline.sh

# Start the services
./start_pipeline.sh
```

Access points:
- MinIO Console: http://localhost:9001 (login: minioadmin/minioadmin)
- Airflow Webserver: http://localhost:8080 (login: airflow/airflow)

### Step 3: Run the Reconstruction Pipeline

You can run the reconstruction pipeline in two ways:

#### Option 1: Using the Run Script (Recommended)

```bash
# Make the script executable if needed
chmod +x run_e2e3d_pipeline.sh

# Run the pipeline with your images
./run_e2e3d_pipeline.sh /path/to/your/images [/optional/output/path]
```

#### Option 2: Using Airflow DAG

1. Upload your images to the `data/input/FrameSequence` directory
2. Navigate to the Airflow UI at http://localhost:8080
3. Trigger the `e2e3d_reconstruction_dag` DAG
4. Monitor the progress through the Airflow UI
5. Once complete, download your mesh from MinIO at http://localhost:9000/models/reconstructed_mesh.obj

## Accessing the 3D Mesh

After reconstruction completes:

1. Access the MinIO console at http://localhost:9001 (login: minioadmin/minioadmin)
2. Navigate to the 'models' bucket
3. Download the reconstructed mesh file (typically named `reconstructed_mesh.obj`)
4. Or access it directly at: http://localhost:9000/models/reconstructed_mesh.obj

## Troubleshooting

### Docker Issues

If you encounter Docker-related errors:

```bash
# Remove all previous containers and volumes
docker-compose -f docker-compose-fixed.yml down -v

# Rebuild the Docker images
./build_fixed_images.sh
```

### MinIO Issues

If MinIO is inaccessible:

```bash
# Check if MinIO is running
docker ps | grep minio

# Restart MinIO services if needed
docker-compose -f docker-compose-minimal-test.yml restart
```

### Reconstruction Issues

If the reconstruction fails:

1. Ensure your images have sufficient overlap between consecutive shots
2. Try using higher quality images with good lighting
3. Adjust the quality setting in the run script:
   ```bash
   QUALITY_PRESET=high ./run_e2e3d_pipeline.sh /path/to/your/images
   ```

## Configuration Options

Configuration is managed through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `QUALITY_PRESET` | Reconstruction quality (low, medium, high) | medium |
| `S3_ENABLED` | Enable storage to MinIO | true |
| `S3_ENDPOINT` | MinIO endpoint URL | http://minio:9000 |
| `S3_BUCKET` | MinIO bucket name | models |
| `S3_ACCESS_KEY` | MinIO access key | minioadmin |
| `S3_SECRET_KEY` | MinIO secret key | minioadmin |

## Available Scripts

| Script | Description |
|--------|-------------|
| `docker-compose-minimal-test.yml` | Minimal Docker Compose file for MinIO only |
| `simple_run_pipeline.sh` | Simplified pipeline script that works with MinIO only |
| `build_fixed_images.sh` | Builds all required Docker images with fixed configurations |
| `start_pipeline.sh` | Starts the full pipeline services (MinIO, Airflow, etc.) |
| `run_e2e3d_pipeline.sh` | Runs the reconstruction process on a given image set |
| `test_pipeline.sh` | Tests if the pipeline is properly set up |
| `upload_mesh_to_minio.py` | Python script to upload mesh files to MinIO |

## Further Improvements

Potential improvements for future versions:

- Dense reconstruction for higher detail
- Texture mapping to add color to the mesh
- Support for more mesh export formats (glTF, FBX, etc.)
- Web UI for reconstruction monitoring and configuration
- CUDA acceleration for faster reconstruction
- Progress reporting during reconstruction

## Dependencies and Credits

This pipeline uses the following open-source technologies:

- COLMAP for Structure from Motion and Multi-View Stereo
- PyMeshLab for mesh processing
- MinIO for object storage
- Airflow for pipeline orchestration
- Docker for containerization 