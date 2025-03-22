# E2E3D Usage Guide

This document provides instructions for setting up, running, and using the E2E3D reconstruction system.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Starting the System](#starting-the-system)
4. [Using the API](#using-the-api)
5. [Submitting Reconstruction Jobs](#submitting-reconstruction-jobs)
6. [Monitoring Job Status](#monitoring-job-status)
7. [Retrieving Results](#retrieving-results)
8. [Accessing Metrics](#accessing-metrics)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Usage](#advanced-usage)

## System Requirements

### Hardware Requirements

- **CPU**: Minimum 4 cores, 8+ cores recommended for faster processing
- **RAM**: Minimum 8GB, 16GB+ recommended
- **Storage**: Minimum 50GB of free space
- **GPU**: Optional but recommended for faster processing (NVIDIA GPU with CUDA support)

### Software Requirements

- **Docker**: Version 20.10.0 or higher
- **Docker Compose**: Version 2.0.0 or higher
- **Operating System**: Linux, macOS, or Windows with WSL2
- **Web Browser**: Chrome, Firefox, or Safari (latest version)

## Installation

### Clone the Repository

```bash
git clone https://github.com/e2e3d/e2e3d.git
cd e2e3d
```

### Set Up Environment Variables

Copy the example environment file and modify it if needed:

```bash
cp .env.example .env
```

Edit the `.env` file to configure your environment:

```bash
# Basic configuration
E2E3D_DATA_DIR=/path/to/your/data
E2E3D_ENABLE_METRICS=true
E2E3D_USE_GPU=auto

# MinIO configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# PostgreSQL configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=e2e3d
```

### Build the Docker Images

```bash
cd production
docker compose build
```

This will build all the required Docker images for the E2E3D system.

## Starting the System

### Start All Services

From the production directory, run:

```bash
docker compose up -d
```

This will start all the services defined in the docker-compose.yml file in detached mode.

### Verify Services are Running

Check if all containers are running correctly:

```bash
docker compose ps
```

You should see all containers with a status of "Up".

### Initialization

Wait for all services to initialize. This may take a few minutes on the first run as data directories are created and initial setup is performed.

## Using the API

### API Base URL

The API is accessible at:

```
http://localhost/api
```

### Health Check

To check if the API is running correctly:

```bash
curl http://localhost/api/health
```

You should receive a response like:

```json
{"status": "healthy"}
```

### Metrics Check

To check if metrics are available:

```bash
curl http://localhost/api/metrics
```

You should receive a response indicating the metrics status.

## Submitting Reconstruction Jobs

### Preparing Input Data

Place your image set in the input directory, which is accessible as `/app/data/input/` inside the Docker containers. For example:

```bash
mkdir -p ./data/input/my_image_set
cp path/to/your/images/*.jpg ./data/input/my_image_set/
```

### Submitting a Job via API

To submit a reconstruction job:

```bash
curl -X POST http://localhost/api/reconstruct \
  -H "Content-Type: application/json" \
  -d '{
    "image_set_path": "/app/data/input/my_image_set",
    "quality": "medium",
    "job_id": "my_first_job"
  }'
```

You should receive a response like:

```json
{
  "status": "submitted",
  "job_id": "my_first_job"
}
```

### Job Parameters

| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `image_set_path` | Path to the directory containing images | Required | Any valid path |
| `quality` | Quality setting for reconstruction | `medium` | `low`, `medium`, `high` |
| `job_id` | Unique identifier for the job | Auto-generated | Any string |
| `use_gpu` | Whether to use GPU for processing | `auto` | `true`, `false`, `auto` |
| `upload` | Whether to upload results to MinIO | `false` | `true`, `false` |
| `notify_url` | URL to receive notification when job completes | None | Any valid URL |

## Monitoring Job Status

### Listing All Jobs

To list all jobs and their status:

```bash
curl http://localhost/api/jobs
```

### Checking a Specific Job

To check the status of a specific job:

```bash
curl http://localhost/api/job/my_first_job
```

You'll receive a response with details about the job status:

```json
{
  "job_id": "my_first_job",
  "status": "running",
  "start_time": 1715386012.4529,
  "elapsed": 45.2,
  "output_dir": "/app/data/output/my_first_job"
}
```

### Cancelling a Job

To cancel a running job:

```bash
curl -X POST http://localhost/api/job/my_first_job/cancel
```

## Retrieving Results

### Checking Available Results

Once a job is completed, you can check the available result files:

```bash
curl http://localhost/api/job/my_first_job/results
```

You'll receive a response listing all result files:

```json
{
  "job_id": "my_first_job",
  "result_dir": "my_first_job/my_first_job_20230426_125423",
  "files": [
    {
      "path": "my_first_job/my_first_job_20230426_125423/mesh/reconstructed_mesh.obj",
      "type": "obj",
      "size": 1048576,
      "url": "/api/file/my_first_job/my_first_job_20230426_125423/mesh/reconstructed_mesh.obj"
    }
  ]
}
```

### Downloading Files

To download a specific file:

```bash
curl -o my_mesh.obj http://localhost/api/file/my_first_job/my_first_job_20230426_125423/mesh/reconstructed_mesh.obj
```

### Accessing Files via MinIO

You can also access the files directly through the MinIO web interface:

1. Open `http://localhost:9000` in your browser
2. Log in with the MinIO credentials (default: minioadmin/minioadmin)
3. Navigate to the `output` bucket and browse your job results

## Accessing Metrics

### Prometheus Metrics

Metrics are exposed at:

```
http://localhost:9101/metrics
```

### Prometheus UI

The Prometheus web interface is available at:

```
http://localhost:9090
```

Use it to query metrics and check targets.

### Grafana Dashboards

Grafana is available at:

```
http://localhost:3000
```

Default login is admin/admin. The E2E3D dashboard should be available after login.

## Troubleshooting

### Checking Logs

To check logs for a specific service:

```bash
docker compose logs reconstruction-service
```

To follow the logs in real-time:

```bash
docker compose logs -f reconstruction-service
```

### Common Issues

#### Jobs Not Starting

If jobs are not starting:

1. Check that the reconstruction service is running:
   ```bash
   docker compose ps reconstruction-service
   ```

2. Check the logs for errors:
   ```bash
   docker compose logs reconstruction-service
   ```

3. Verify that the input path exists and contains images:
   ```bash
   docker exec e2e3d-reconstruction-service ls -la /app/data/input/my_image_set
   ```

#### API Not Responding

If the API is not responding:

1. Check if the API service is running:
   ```bash
   docker compose ps api
   ```

2. Check the logs for errors:
   ```bash
   docker compose logs api
   ```

3. Check if Nginx is running and properly configured:
   ```bash
   docker compose logs nginx
   ```

#### Results Not Visible

If results are not visible:

1. Check if the job completed successfully:
   ```bash
   curl http://localhost/api/job/my_first_job
   ```

2. Check if files were generated:
   ```bash
   docker exec e2e3d-reconstruction-service ls -la /app/data/output/my_first_job
   ```

3. Check if MinIO is running:
   ```bash
   docker compose ps minio
   ```

## Advanced Usage

### Using GPU Acceleration

To explicitly enable GPU acceleration for a job:

```bash
curl -X POST http://localhost/api/reconstruct \
  -H "Content-Type: application/json" \
  -d '{
    "image_set_path": "/app/data/input/my_image_set",
    "quality": "high",
    "job_id": "my_gpu_job",
    "use_gpu": true
  }'
```

Note: This requires a CUDA-compatible GPU and the proper Docker setup for GPU passthrough.

### Batch Processing Multiple Datasets

For batch processing multiple datasets, you can use a shell script:

```bash
#!/bin/bash
for dataset in dataset1 dataset2 dataset3; do
  curl -X POST http://localhost/api/reconstruct \
    -H "Content-Type: application/json" \
    -d "{
      \"image_set_path\": \"/app/data/input/${dataset}\",
      \"quality\": \"medium\",
      \"job_id\": \"batch_${dataset}\"
    }"
  echo "Submitted job for ${dataset}"
  sleep 5  # Optional delay between submissions
done
```

### Setting Up Webhooks for Job Completion

To receive a notification when a job completes:

```bash
curl -X POST http://localhost/api/reconstruct \
  -H "Content-Type: application/json" \
  -d '{
    "image_set_path": "/app/data/input/my_image_set",
    "quality": "medium",
    "job_id": "webhook_job",
    "notify_url": "https://your-server.com/webhook"
  }'
```

When the job completes, a POST request will be sent to the specified URL with details about the job result.

### Stopping the System

To stop all services:

```bash
docker compose down
```

To stop all services and remove volumes (WARNING: this will delete all data):

```bash
docker compose down -v
``` 