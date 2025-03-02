# Quick Start Guide: E2E Video to 3D Pipeline

This guide will help you quickly set up and run the automated photogrammetry pipeline on your local machine.

## Prerequisites

1. **Docker and Docker Compose**
   - [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Ensure you have at least 10GB of free disk space
   - Recommended: 16GB RAM, quad-core CPU

2. **NVIDIA GPU (Optional)**
   - For accelerated processing, an NVIDIA GPU with CUDA support is recommended
   - Install [NVIDIA Docker Runtime](https://github.com/NVIDIA/nvidia-docker)

## Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/E2EVideoTo3D.git
   cd E2EVideoTo3D
   ```

2. **Start all services**
   ```bash
   docker compose up -d
   ```

3. **Verify services are running**
   ```bash
   docker compose ps
   ```

   You should see the following services running:
   - airflow-webserver (http://localhost:8080)
   - airflow-scheduler
   - postgres
   - minio (http://localhost:9001)
   - spark-master (http://localhost:8001)
   - spark-worker
   - photogrammetry
   - minio-init (should complete and exit)

## Verify Setup

1. **Check MinIO buckets**
   - Open http://localhost:9001 in your browser
   - Login with:
     - Username: `minioadmin`
     - Password: `minioadmin`
   - Verify that the following buckets exist:
     - raw-videos
     - frames
     - processed-frames
     - models

2. **Verify Airflow DAG**
   - Open http://localhost:8080 in your browser
   - Login with:
     - Username: `airflow`
     - Password: `airflow`
   - Check that the DAG `photogrammetry_pipeline` is listed (may be in "Paused" state)

3. **Verify Meshroom**
   ```bash
   docker compose exec photogrammetry meshroom_batch --help
   ```
   You should see the Meshroom help output.

4. **Verify Spark**
   ```bash
   docker compose exec spark-master spark-submit --master spark://spark-master:7077 --version
   ```
   You should see the Spark version information.

## Using the Pipeline

1. **Upload a test video**
   - In the MinIO console, navigate to the `raw-videos` bucket
   - Click "Upload" and select a video file (recommended: 15-30 second MP4 file)

2. **Run the pipeline**
   - In the Airflow UI, unpause the `photogrammetry_pipeline` DAG by clicking the toggle switch
   - The DAG will automatically detect the new video file and start processing
   - Monitor progress in the Airflow UI

3. **View results**
   - After processing completes (may take 30+ minutes depending on your hardware)
   - Check the `models` bucket in MinIO for the generated 3D model files
   - Download the .obj file along with associated texture files for viewing in your preferred 3D viewer

## Monitoring the Pipeline

You can monitor the pipeline execution in several ways:

1. **Airflow UI**
   - Shows task status, execution times, and logs
   - Navigate to DAG > Grid view to see status of all tasks

2. **Container logs**
   ```bash
   # View logs from all services
   docker compose logs -f
   
   # View logs from a specific service
   docker compose logs -f photogrammetry
   docker compose logs -f airflow-scheduler
   ```

3. **Spark UI**
   - Open http://localhost:8001 to monitor Spark jobs
   - Shows cluster resources, running applications, and job details

## Troubleshooting

### Common Issues

1. **DAG not finding newly uploaded videos:**
   - The S3KeySensor polls every 5 minutes by default
   - Try manually triggering the DAG in Airflow UI

2. **"No such file or directory" errors:**
   - Check if the directory structure in containers matches the paths in DAG
   - Ensure file permissions are correct

3. **"Module not found" errors in Airflow:**
   - The DAG is configured to use mock implementations when modules aren't found
   - This should allow the DAG to run in isolation without the actual implementation

4. **Performance issues:**
   - Adjust Spark worker resources in docker-compose.yml
   - For GPU acceleration, ensure the NVIDIA Docker runtime is properly configured

## System Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Raw Video  │    │    Video    │    │   Frames    │
│   Upload    │───▶│   to Frame  │───▶│  Processing │
│  (MinIO)    │    │ (Extraction)│    │   (Spark)   │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Final    │    │     3D      │    │ Photogrammetry│
│    Model    │◀───│   Model     │◀───│  (Meshroom)  │
│   (MinIO)   │    │  Generation │    │              │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Next Steps

1. **Customize the Pipeline**
   - Modify frame extraction parameters
   - Adjust Meshroom settings for quality vs. speed
   - Configure error handling and notification settings

2. **Add Authentication**
   - Change default MinIO credentials
   - Configure Airflow RBAC

3. **Optimize Performance**
   - Fine-tune Spark worker configuration
   - Adjust resource allocation for containers
   - Implement caching strategies

---

**Last Updated**: 2024-07-16