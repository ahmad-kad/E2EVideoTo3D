# E2E3D Quick Start Guide

This quick start guide will help you get up and running with the E2E3D system for 3D reconstruction from images. We'll cover installation, basic usage, and provide a simple end-to-end example.

## Prerequisites

Before starting, ensure you have:

- **Docker** and **Docker Compose** installed
- At least 8GB RAM and 20GB free disk space
- A set of images for 3D reconstruction (we'll use a sample dataset)

## Installation

### Step 1: Get the Code

Clone the E2E3D repository:

```bash
git clone https://github.com/yourusername/e2e3d.git
cd e2e3d
```

### Step 2: Environment Setup

Create a `.env` file with basic configuration:

```bash
cp .env.example .env
```

The default values should work for a quick start, but you can adjust them if needed.

### Step 3: Start the System

Launch the system using Docker Compose:

```bash
docker-compose up -d
```

This will start all required services:
- API service
- Reconstruction service
- MinIO for storage
- PostgreSQL for database
- Airflow for workflow orchestration
- Prometheus and Grafana for monitoring

### Step 4: Verify the Installation

Check that all services are running:

```bash
docker-compose ps
```

All services should have the "Up" status.

Access the main interfaces:
- API: http://localhost:5000
- MinIO Console: http://localhost:9001 (login with `minioadmin`/`minioadmin`)
- Airflow: http://localhost:8080
- Grafana: http://localhost:3000 (login with `admin`/`admin`)

## Basic Usage

### Step 1: Prepare Images

For this quick start, we'll use the `CognacStJacquesDoor` sample dataset that comes with E2E3D.

If you want to use your own images, place them in a directory with a descriptive name. Good images for reconstruction should:
- Have good lighting
- Provide 60-80% overlap between consecutive images
- Capture the subject from multiple angles
- Be in focus and high resolution

### Step 2: Create a New Job

You can create a new reconstruction job through the API. Let's use curl for this example:

```bash
curl -X POST http://localhost:5000/api/job \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "CognacStJacquesDoor",
    "reconstruction_quality": "medium",
    "generate_textures": true
  }'
```

The response will include a `job_id` that you'll use to track your job.

### Step 3: Monitor the Job

Check the status of your job:

```bash
curl http://localhost:5000/api/job/YOUR_JOB_ID
```

Replace `YOUR_JOB_ID` with the actual job ID from the previous step.

You can also monitor the job in the Airflow interface (http://localhost:8080) to see the detailed progress.

### Step 4: View Results

Once the job is complete, you can access the results:

```bash
curl http://localhost:5000/api/job/YOUR_JOB_ID/results
```

This will return links to download:
- 3D mesh (OBJ format)
- Texture maps
- Point cloud data (PLY format)
- Preview images

You can also access these files directly through the MinIO Console (http://localhost:9001) in the `output` bucket.

## Complete Workflow Example

Here's a complete example workflow that processes the sample dataset and downloads the results:

```bash
# Start the system
docker-compose up -d

# Wait for all services to initialize (about 30 seconds)
echo "Waiting for services to initialize..."
sleep 30

# Create a new reconstruction job
echo "Creating a new reconstruction job..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:5000/api/job \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "CognacStJacquesDoor",
    "reconstruction_quality": "medium",
    "generate_textures": true
  }')

# Extract the job ID
JOB_ID=$(echo $JOB_RESPONSE | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo "Job created with ID: $JOB_ID"

# Poll the job status until it's complete
echo "Monitoring job status..."
JOB_STATUS="pending"
while [ "$JOB_STATUS" != "completed" ] && [ "$JOB_STATUS" != "failed" ]; do
  sleep 10
  JOB_RESPONSE=$(curl -s http://localhost:5000/api/job/$JOB_ID)
  JOB_STATUS=$(echo $JOB_RESPONSE | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
  echo "Current status: $JOB_STATUS"
done

# If job completed successfully, get the results
if [ "$JOB_STATUS" = "completed" ]; then
  echo "Job completed successfully! Getting results..."
  RESULTS=$(curl -s http://localhost:5000/api/job/$JOB_ID/results)
  
  # Create a directory for the results
  mkdir -p e2e3d_results
  
  # Extract download URLs
  MESH_URL=$(echo $RESULTS | grep -o '"mesh":"[^"]*"' | cut -d'"' -f4)
  TEXTURE_URL=$(echo $RESULTS | grep -o '"texture":"[^"]*"' | cut -d'"' -f4)
  POINT_CLOUD_URL=$(echo $RESULTS | grep -o '"pointcloud":"[^"]*"' | cut -d'"' -f4)
  
  # Download the results
  echo "Downloading mesh..."
  curl -s "$MESH_URL" -o e2e3d_results/mesh.obj
  
  echo "Downloading texture..."
  curl -s "$TEXTURE_URL" -o e2e3d_results/texture.png
  
  echo "Downloading point cloud..."
  curl -s "$POINT_CLOUD_URL" -o e2e3d_results/pointcloud.ply
  
  echo "Results downloaded to e2e3d_results directory!"
else
  echo "Job failed. Check the logs for more information."
fi
```

## Viewing 3D Models

To view your 3D models, you can use:

- **Meshlab**: An open-source system for processing and editing 3D models
- **Blender**: A professional 3D creation suite
- **Online viewers** like Sketchfab or Google's Model Viewer

For a quick browser-based view, you can use the built-in preview at:
```
http://localhost:5000/api/job/YOUR_JOB_ID/preview
```

## Common Issues and Solutions

### Services Won't Start

**Issue**: Docker Compose fails to start all services.

**Solution**:
1. Check if ports are already in use: `netstat -tuln`
2. Ensure you have enough system resources
3. Check Docker logs: `docker-compose logs`

### Job Processing Fails

**Issue**: The reconstruction job fails with errors.

**Solution**:
1. Check the Airflow logs for specific error messages
2. Ensure your dataset has enough quality images
3. Try with a different dataset to rule out image quality issues

### Can't Access Web Interfaces

**Issue**: Unable to access MinIO, Airflow, or other web interfaces.

**Solution**:
1. Verify that all containers are running: `docker-compose ps`
2. Check if your firewall is blocking the ports
3. Try using `localhost` instead of 127.0.0.1

## Next Steps

Now that you've completed a basic reconstruction, you can:

1. **Try with your own images**: Use photos you've taken of a real object
2. **Experiment with settings**: Adjust quality settings for better results
3. **Learn the API**: Explore other API endpoints and options
4. **Set up automation**: Use the API to automate your reconstruction workflow

For more detailed information, refer to the following documentation:

- [Project Overview](01_PROJECT_OVERVIEW.md) for a comprehensive introduction
- [Reconstruction Service](02_CORE_RECONSTRUCTION.md) for details on the reconstruction process
- [API Documentation](03_CORE_API.md) for a complete reference of all API endpoints

## Support and Feedback

If you encounter issues or have questions, please:

1. Check the [documentation](00_TABLE_OF_CONTENTS.md) for guidance
2. Review common issues in this quick start guide
3. Submit an issue on the GitHub repository
4. Reach out to the community through the discussion forums 