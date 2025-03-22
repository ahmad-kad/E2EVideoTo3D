# E2E3D Pipeline Workaround Solution

This document explains the workaround solution for running the E2E3D pipeline when there are issues with building Docker images.

## Overview

The E2E3D pipeline has been simplified to focus on the core functionality:
1. Running MinIO for storage
2. Running the reconstruction process either locally or with an existing Docker image
3. Uploading the resulting mesh to MinIO for easy access

## Setup Instructions

### Step 1: Start MinIO Service

We've created a minimal Docker Compose file that only runs MinIO:

```bash
# Start MinIO service
docker-compose -f docker-compose-minimal-test.yml up -d
```

This will start the MinIO service and make it accessible at:
- http://localhost:9000 - MinIO API endpoint
- http://localhost:9001 - MinIO web console (login: minioadmin/minioadmin)

### Step 2: Run the Simplified Pipeline

We've created a simplified pipeline script that will:
1. Ensure MinIO is running
2. Run the reconstruction process
3. Upload the resulting mesh to MinIO

```bash
# Run with local Python
USE_DOCKER=false ./simple_run_pipeline.sh /path/to/your/images [/optional/output/path]

# OR use existing Docker image if available
USE_DOCKER=true ./simple_run_pipeline.sh /path/to/your/images [/optional/output/path]
```

## Accessing the Results

After the reconstruction completes:

1. The mesh file will be saved to the output directory as `<output_dir>/mesh/reconstructed_mesh.obj`
2. The mesh will be uploaded to MinIO and accessible at http://localhost:9000/models/reconstructed_mesh.obj
3. You can also browse files using the MinIO web console at http://localhost:9001

## Troubleshooting

### MinIO Issues

If MinIO is not accessible:

```bash
# Restart MinIO
docker-compose -f docker-compose-minimal-test.yml restart

# Check logs
docker logs e2e3d-minio
```

### Reconstruction Issues

If reconstruction fails:

1. Check that Python is properly installed with all required dependencies
2. Try running `python3 reconstruct.py` directly to see any error messages
3. Check that the input directory contains valid image files

## Next Steps

Once the Docker image building issues are resolved, you can:

1. Run `./build_fixed_images.sh` to build all Docker images
2. Run `./test_pipeline.sh` to verify the setup
3. Use the full pipeline with `./run_e2e3d_pipeline.sh /path/to/your/images` 