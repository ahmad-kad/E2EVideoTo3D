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
   git clone https://github.com/yourusername/photogrammetry-pipeline.git
   cd photogrammetry-pipeline
   ```

2. **Create required directories**
   ```bash
   # On Windows:
   mkdir minio-data\raw-videos minio-data\frames minio-data\models minio-data\processed-frames

   # On Linux/macOS:
   mkdir -p minio-data/raw-videos minio-data/frames minio-data/models minio-data/processed-frames
   ```

3. **Start services**
   ```bash
   docker compose up -d
   ```

4. **Verify services are running**
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

## Using the Pipeline

1. **Access MinIO Console**
   - Open http://localhost:9001 in your browser
   - Login with:
     - Username: `minioadmin`
     - Password: `minioadmin`
   - Verify that the following buckets exist:
     - raw-videos
     - frames
     - processed-frames
     - models

2. **Access Airflow**
   - Open http://localhost:8080 in your browser
   - Login with:
     - Username: `airflow`
     - Password: `airflow`
   - Check that the DAG `photogrammetry_pipeline` is listed and in "Paused" state

3. **Upload a test video**
   - In the MinIO console, navigate to the `raw-videos` bucket
   - Click "Upload" and select a video file (recommended: 20-30 second MP4 file)
   - Alternatively, use the MinIO client CLI:
     ```bash
     docker compose exec minio mc cp /path/to/video.mp4 myminio/raw-videos/
     ```

4. **Run the pipeline**
   - In the Airflow UI, unpause the `photogrammetry_pipeline` DAG
   - The DAG will automatically detect the new video file and start processing
   - Monitor progress in the Airflow UI

5. **View results**
   - After processing completes (may take 30+ minutes for a typical video)
   - Check the `models` bucket in MinIO for the generated 3D model files
   - Download the .obj file along with associated texture files for viewing in your preferred 3D viewer

## Troubleshooting

### Common Issues

1. **Meshroom errors:**
   - Verify Meshroom is installed correctly:
     ```bash
     docker compose exec photogrammetry meshroom_batch --help
     ```
   - If not working, rebuild the container:
     ```bash
     docker compose build photogrammetry
     ```

2. **MinIO connection issues:**
   - Ensure buckets are created:
     ```bash
     docker compose exec minio mc ls myminio
     ```
   - If buckets are missing, create them manually:
     ```bash
     docker compose exec minio mc mb myminio/raw-videos
     docker compose exec minio mc mb myminio/frames
     docker compose exec minio mc mb myminio/processed-frames
     docker compose exec minio mc mb myminio/models
     ```

3. **Airflow DAG not running:**
   - Check if Airflow recognizes the DAG:
     ```bash
     docker compose exec airflow-scheduler airflow dags list
     ```
   - Restart the scheduler if needed:
     ```bash
     docker compose restart airflow-scheduler
     ```

4. **Performance issues:**
   - Adjust Spark worker resources in docker-compose.yml
   - For GPU acceleration, ensure the NVIDIA Docker runtime is properly configured

## Additional Resources

- [Complete Documentation](./docs/README.md)
- [DAG Configuration Guide](./docs/airflow.md)
- [MinIO Configuration](./docs/storage.md)

## Next Steps

1. **Customize the Pipeline**
   - Modify frame extraction parameters in `src/ingestion/frame_extractor.py`
   - Adjust quality settings in `src/photogrammetry/meshroom_runner.py`

2. **Add Authentication**
   - Change default MinIO credentials
   - Configure Airflow RBAC

3. **Deploy to Production**
   - Set up Kubernetes with Terraform (see `infra/terraform/`)
   - Configure cloud storage (AWS S3, GCP Cloud Storage, etc.) 