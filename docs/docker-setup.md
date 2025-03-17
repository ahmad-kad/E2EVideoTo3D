# Docker Setup Guide

This guide provides instructions for setting up and running the E2E3D pipeline using Docker.

## Prerequisites

- Docker and Docker Compose
- Either:
  - Apple Silicon Mac (M1/M2/M3) for ARM64 architecture
  - NVIDIA GPU with CUDA support and NVIDIA Container Toolkit

## Quick Start

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/e2e3d.git
   cd e2e3d
   ```

2. Run the automated setup script
   ```bash
   ./run.sh
   ```

3. Access services:
   - Airflow: http://localhost:8080 (username: admin, password: admin)
   - MinIO: http://localhost:9001 (username: minioadmin, password: minioadmin)

## Docker Images

The E2E3D system uses three main Docker images:

1. **e2e3d-base**: Base image with Python 3.7.9 and common dependencies
2. **e2e3d-colmap**: Image with COLMAP and reconstruction tools
3. **e2e3d-airflow**: Image with Airflow and workflow management tools

## Configuration

The system can be configured through environment variables in the `.env` file:

```
DATA_DIR=./data
DOCKER_PLATFORM=linux/arm64
USE_GPU=auto
QUALITY_PRESET=medium
S3_ENABLED=true
S3_ENDPOINT=http://minio:9000
S3_BUCKET=models
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
```

### Important Configuration Options

- `DOCKER_PLATFORM`: Set to `linux/arm64` for Apple Silicon or `linux/amd64` for Intel/AMD
- `USE_GPU`: Set to `auto` (detect), `true` (force use), or `false` (disable)
- `QUALITY_PRESET`: Set to `low`, `medium`, or `high`

## Testing the System

### Option 1: Using the Simplified Test Container

To run a simplified test of the reconstruction pipeline:

```bash
./test_docker.sh
```

This will:
1. Check Docker installation
2. Build a test container
3. Download sample data
4. Run a test reconstruction

### Option 2: Using the Airflow Test DAG

To test the system through Airflow:

```bash
./scripts/run_airflow_test.sh
```

This will:
1. Check if Docker and Airflow are running
2. Set up directories
3. Trigger the `test_reconstruction_pipeline` DAG
4. Generate a test report

You can customize the test parameters:

```bash
./scripts/run_airflow_test.sh --dataset CognacStJacquesDoor --quality high --use-gpu true
```

### Monitoring the Test

1. Access the Airflow UI at http://localhost:8080
2. Navigate to the `test_reconstruction_pipeline` DAG
3. Monitor the progress of each task
4. Check the test report in the `docs` directory after completion

## Troubleshooting

### Docker Build Issues

If you encounter issues with Docker builds:

```bash
./run.sh build  # Force rebuild all images
```

### Container Not Starting

Check for port conflicts:

```bash
docker ps -a  # List all containers
lsof -i :8080  # Check if port 8080 is in use
```

### Memory Issues

If containers crash due to memory limitations:

1. Increase Docker memory limit in Docker Desktop settings
2. For COLMAP, use a lower quality preset: `--quality low`

### CUDA Issues

For NVIDIA GPU users, verify NVIDIA Docker runtime:

```bash
docker info | grep -i runtime
```

Should include `nvidia` in the output. 