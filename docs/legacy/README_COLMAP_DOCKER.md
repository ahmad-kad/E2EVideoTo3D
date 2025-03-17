# 3D Reconstruction Pipeline with Docker COLMAP

This guide explains how to set up the 3D reconstruction pipeline using a pre-built COLMAP Docker image instead of building COLMAP from source.

## Overview

The pipeline has been updated to use the official COLMAP Docker image, which simplifies the setup and ensures consistent operations across different environments.

## Setup Instructions

1. Run the setup script to configure the environment:

```bash
./setup_colmap_environment.sh
```

This script will:
- Update or create the `.env` file with necessary configurations
- Pull the COLMAP Docker image
- Create required directories
- Set appropriate permissions

2. Place your videos in the `data/videos` directory or image frames in the `data/input` directory.

3. Start the Docker Compose services:

```bash
docker-compose up -d
```

4. Access the Airflow UI at http://localhost:8080

5. Trigger the `reconstruction_pipeline` DAG, optionally specifying a specific video path.

## How It Works

The pipeline now uses a Docker-based approach for COLMAP operations:

1. A dedicated `colmap` service is defined in `docker-compose.override.yml` using the official `colmap/colmap:latest` image.

2. The Airflow tasks have been updated to use the COLMAP Docker container when needed through a helper function called `run_colmap_command`.

3. Path mappings are handled automatically, translating paths between the host and Docker container.

## Benefits

- No need to build COLMAP from source
- Consistent environment for reconstruction tasks
- Simplified installation and dependency management
- Easy upgrades to newer COLMAP versions by updating the Docker image

## Troubleshooting

If you encounter issues:

1. Check the Airflow logs for specific error messages.

2. Verify that Docker can access the required directories.

3. Make sure the paths in your `.env` file match your setup.

4. If tasks fail, try enabling test mode by setting `AIRFLOW_TEST_MODE=true` in the `.env` file to debug the pipeline.

## Environment Variables

The following environment variables control the pipeline behavior:

- `USE_COLMAP_DOCKER`: Set to `true` to use the Docker container for COLMAP operations
- `COLMAP_DOCKER_SERVICE`: The name of the Docker service for COLMAP (default: `colmap`)
- `COLMAP_PATH`: Path to the COLMAP executable (should be `/usr/bin/colmap` for Docker mode)
- `AIRFLOW_TEST_MODE`: Set to `true` to enable test mode, which skips actual COLMAP processing and creates mock outputs

## File Structure

```
/
├── data/
│   ├── input/        # Input image frames
│   ├── output/       # Reconstruction outputs
│   └── videos/       # Input video files
├── dags/
│   └── reconstruction_pipeline.py  # The main Airflow DAG
├── docker-compose.override.yml     # Docker Compose override with COLMAP service
├── setup_colmap_environment.sh     # Setup script
└── README_COLMAP_DOCKER.md         # This README
``` 