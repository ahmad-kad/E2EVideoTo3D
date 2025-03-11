# Automated 3D Photogrammetry Pipeline

A production-grade data engineering pipeline that converts video input into textured 3D models using fully open-source components. The system demonstrates proficiency in distributed computing, workflow orchestration, and cloud-native architecture.

## Features

- Cloud-native scalable architecture
- Multi-platform support (Apple Silicon and NVIDIA GPU)
- Video-to-frames extraction for 3D reconstruction
- Distributed frame processing with PySpark
- Workflow orchestration with Apache Airflow
- S3-compatible storage with MinIO
- Infrastructure as Code with Terraform
- Quality monitoring with Evidently AI
- Data validation with Great Expectations

## Architecture

```mermaid
graph TD
A[Video Files] --> B[FFmpeg/OpenCV Frame Extraction]
B --> C[MinIO Raw Frame Storage]
C --> D[PySpark Distributed Preprocessing]
D --> E[COLMAP Photogrammetry Engine]
E --> F[3D Model Storage in MinIO]
F --> G[PostgreSQL Metadata Catalog]
G --> H[dbt-BigQuery Transformation]
H --> I[Metabase Analytics Dashboard]
J[Apache Airflow] -->|Orchestrates| B & D & E & G
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Optional: FFmpeg (for video processing, but can use Docker-based alternative)
- Either:
  - Apple Silicon Mac (M1/M2/M3) for ARM64 architecture
  - NVIDIA GPU with CUDA support and NVIDIA Container Toolkit
- Python 3.9+

### Quick Start (Recommended)

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/photogrammetry-pipeline.git
   cd photogrammetry-pipeline
   ```

2. Run the automated setup script
   ```bash
   chmod +x run.sh
   ./run.sh
   ```

3. Access services:
   - Airflow: http://localhost:8080 (username: admin, password: admin)
   - MinIO: http://localhost:9001 (username: minioadmin, password: minioadmin)
   - Spark Master UI: http://localhost:8001

### Processing a Video

Two options are available for video processing:

#### Option 1: Using Local FFmpeg (requires FFmpeg installation)

1. Install FFmpeg if not already installed (our setup script will attempt to install it):
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # CentOS/RHEL
   sudo yum install ffmpeg
   ```

2. Extract frames from the video:
   ```bash
   ./scripts/video_to_frames.sh data/videos/your_video.mp4 data/input 1
   ```

#### Option 2: Using Docker-based Processing (no FFmpeg installation needed)

1. Use the Docker-based processing script:
   ```bash
   ./scripts/docker_video_process.sh data/videos/your_video.mp4 data/input 1
   ```

Both scripts extract 1 frame per second. Adjust the last parameter to change the frame rate.

3. Run the reconstruction pipeline:
   - Access Airflow UI at http://localhost:8080
   - Trigger the 'reconstruction_pipeline' DAG
   - Monitor progress in the Airflow UI
   - Output 3D models will be in `data/output`

### Processing Images Directly

If you already have images instead of video:

1. Place your images in the `data/input` directory
2. Access Airflow UI and trigger the 'reconstruction_pipeline' DAG
3. Output 3D models will be available in the `data/output` directory

### Accessing MinIO Object Storage

MinIO provides S3-compatible object storage for the pipeline:

1. Access the MinIO console at http://localhost:9001
2. Log in with the default credentials:
   - Username: minioadmin
   - Password: minioadmin
3. Browse the default buckets:
   - raw-videos: For original video files
   - frames: For extracted video frames
   - processed-frames: For frames after preprocessing
   - models: For final 3D models

## Troubleshooting

### Can't access Airflow UI

If you cannot access the Airflow UI at http://localhost:8080, run the troubleshooting script:

```bash
./scripts/fix_airflow.sh
```

Common solutions:
- Ensure no other service is using port 8080
- Try accessing via http://127.0.0.1:8080 instead of localhost
- Check if your firewall is blocking the connection
- Restart Docker completely

### Video Processing Issues

If you get "permission denied" errors when running scripts:
```bash
chmod +x scripts/*.sh
```

If FFmpeg is not installed, you have two options:
1. Install FFmpeg manually as described above
2. Use the Docker-based video processing script: `./scripts/docker_video_process.sh`

### Platform Issues
- If you encounter "platform mismatch" errors, rerun the setup script: `./run.sh`
- For manual troubleshooting, ensure your `.env` file contains the correct platform:
  ```
  DOCKER_PLATFORM=linux/arm64  # for Apple Silicon
  # or
  DOCKER_PLATFORM=linux/amd64  # for Intel/AMD
  ```

### NVIDIA GPU Issues
- Ensure NVIDIA drivers are installed and up-to-date
- Verify NVIDIA Container Toolkit is properly installed
- Check docker permissions for GPU access

### Apple Silicon Issues
- Ensure you're using Docker Desktop 4.15+ with improved ARM64 support
- If MinIO fails to start, try manually specifying `--platform linux/arm64` in your docker-compose.yml

## Project Structure

- `src/`: Main Python package
  - `ingestion/`: Video ingestion and frame extraction
  - `processing/`: PySpark distributed processing
  - `reconstruction/`: COLMAP photogrammetry integration
  - `storage/`: MinIO storage interface
  - `monitoring/`: Quality monitoring with Evidently AI
- `airflow/`: Airflow DAGs and plugins
- `infra/`: Infrastructure as Code (Terraform, Kubernetes)
- `tests/`: Unit and integration tests
- `notebooks/`: Jupyter notebooks for exploration
- `scripts/`: Helper scripts for the pipeline
  - `run_colmap.sh`: Main COLMAP execution script
  - `video_to_frames.sh`: Video to images extraction script (requires FFmpeg)
  - `docker_video_process.sh`: Docker-based video processing (no FFmpeg required)
  - `fix_airflow.sh`: Troubleshooting script for Airflow
  - `setup_environment.sh`: Environment configuration script

## License

This project is licensed under the MIT License - see the LICENSE file for details. 


