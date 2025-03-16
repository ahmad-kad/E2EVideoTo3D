# 3D Reconstruction Pipeline for Airflow

This repository contains an Apache Airflow DAG for running a complete 3D reconstruction pipeline using COLMAP. The pipeline processes video files or image sequences and produces 3D point clouds, meshes, and camera positions.

## Prerequisites

### System Requirements

- Docker and Docker Compose
- NVIDIA GPU (optional but recommended)
- 16GB+ RAM
- 10GB+ free disk space for reconstruction data

### Software Dependencies

- COLMAP
- FFmpeg
- Python 3.8+
- OpenCV
- Open3D (for mesh generation)

## Installation

1. Clone this repository
2. Copy the `.env.template` file to `.env` and adjust the values
3. Build the Docker container:

```bash
docker-compose build
```

## Configuration

The pipeline can be configured using environment variables in the `.env` file:

### Basic Configuration

- `PROJECT_PATH`: Base path for all data (default: `/opt/airflow/data`)
- `INPUT_PATH`: Path for input frames (default: `${PROJECT_PATH}/input`)
- `OUTPUT_PATH`: Path for output models (default: `${PROJECT_PATH}/output`)
- `VIDEO_PATH`: Path for input videos (default: `${PROJECT_PATH}/videos`)

### COLMAP Configuration

- `COLMAP_PATH`: Path to COLMAP executable (default: `colmap`)
- `USE_GPU`: Whether to use GPU acceleration (default: `auto`, can be `true` or `false`)
- `QUALITY_PRESET`: Quality preset for reconstruction (default: `medium`, can be `low` or `high`)

### S3/MinIO Configuration

- `S3_ENABLED`: Whether to upload results to S3/MinIO (default: `false`)
- `S3_ENDPOINT`: S3/MinIO endpoint URL (default: `http://minio:9000`)
- `S3_BUCKET`: S3/MinIO bucket name (default: `models`)
- `S3_ACCESS_KEY`: S3/MinIO access key
- `S3_SECRET_KEY`: S3/MinIO secret key
- `S3_REGION`: S3/MinIO region (default: `us-east-1`)

### Notification Configuration

- `SLACK_WEBHOOK`: Slack webhook URL for notifications
- `ENABLE_EMAIL`: Whether to enable email notifications (default: `false`)
- `NOTIFICATION_EMAIL`: Email address for notifications

## Usage

### Input Data

Place your input data in one of the following locations:

- Videos: `/opt/airflow/data/videos`
- Image frames: `/opt/airflow/data/input`

The pipeline will automatically detect the data type and process it accordingly.

### Running the Pipeline

1. Start Airflow:

```bash
docker-compose up -d
```

2. Access the Airflow web interface at http://localhost:8080

3. Trigger the `reconstruction_pipeline` DAG manually with optional parameters:

- `video_path`: Optional path to a specific video file
- `quality`: Quality preset (`low`, `medium`, `high`)
- `s3_upload`: Whether to upload results to S3/MinIO

### Output Data

The pipeline produces the following outputs:

- Point cloud (PLY format)
- Mesh (PLY format)
- Camera positions
- Metadata

All outputs are stored in `/opt/airflow/data/output/models/<model_name>/`

## Pipeline Steps

1. Check dependencies
2. Find and extract frames from video (if needed)
3. Check if frames exist
4. Create COLMAP workspace
5. Extract features
6. Match features
7. Run sparse reconstruction
8. Run dense reconstruction
9. Generate mesh
10. Copy outputs
11. Upload to S3/MinIO (if enabled)

## Troubleshooting

Check the Airflow task logs for detailed error messages.

Common issues:

- **Missing COLMAP**: Ensure COLMAP is installed and available in the PATH
- **GPU issues**: Check that NVIDIA drivers are installed and working correctly
- **Memory issues**: Reduce the quality preset or use a smaller input dataset
- **S3 Upload fails**: Verify S3/MinIO credentials and endpoint URL

## License

MIT 