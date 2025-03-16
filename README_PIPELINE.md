# 3D Reconstruction Pipeline

This pipeline takes images or videos and creates 3D models using COLMAP.

## Quick Start

1. Place your video file in the `data/videos` directory
2. Or place your images in the `data/input` directory
3. Start the pipeline:
   ```
   docker-compose up -d
   ```
4. Access Airflow at http://localhost:8080
5. Login with username: admin, password: admin
6. Enable and trigger the `reconstruction_pipeline` DAG
7. Find results in `data/output/models` directory

## Configuration

Edit the `.env` file to configure the pipeline:

- QUALITY_PRESET: low, medium, or high
- USE_GPU: auto, true, or false
- S3_ENABLED: true/false to enable model upload to S3/MinIO

## Troubleshooting

If the pipeline gets stuck:

1. Check logs: `docker-compose logs airflow-scheduler`
2. Make sure all dependencies are installed
3. Run `setup_airflow_pipeline.sh` to reinstall dependencies
