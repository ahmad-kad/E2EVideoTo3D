# E2E3D - End-to-End 3D Reconstruction Pipeline

This project provides a complete end-to-end pipeline for reconstructing 3D meshes from image sequences using photogrammetry techniques. The pipeline is containerized with Docker and can be easily run on any system with Docker installed.

## Features

- Complete photogrammetry pipeline from images to 3D mesh
- Fully containerized with Docker for easy deployment
- MinIO integration for object storage and easy access to results
- Airflow-based orchestration for workflow management
- Prometheus and Grafana for metrics and monitoring
- Reliable metrics collection for system health and performance

## Quick Start

```bash
# Navigate to the production directory
cd production

# Start the production environment
./scripts/run_production.sh
```

After starting the production environment, you can access:
- Main Dashboard: http://localhost/
- MinIO Console: http://localhost:9001 (user: minioadmin, password: minioadmin)
- Airflow UI: http://localhost:8080 (user: admin, password: admin)
- Grafana: http://localhost:3000 (user: admin, password: admin)
- Prometheus: http://localhost:9090
- API: http://localhost/api

## Documentation

For detailed instructions on setup, configuration, and usage, please see:
- [E2E3D Production Guide](e2e3d_production_report.md)
- [Deployment Summary](e2e3d_deployment_summary.md)
- [Project Documentation](docs/README.md)

## Components

The E2E3D pipeline consists of the following components:

- **COLMAP**: For Structure from Motion and Multi-View Stereo
- **PyMeshLab**: For mesh processing and optimization
- **MinIO**: For object storage of the resulting meshes
- **Airflow**: For workflow orchestration
- **Docker**: For containerization and easy deployment
- **Prometheus**: For metrics collection
- **Grafana**: For metrics visualization and dashboards
- **NGINX**: For web server and API gateway

## Project Structure

```
production/               # Production-ready configuration and services
├── config/               # Configuration files for services
├── dags/                 # Airflow DAG definitions
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile.*          # Service-specific Dockerfiles
└── scripts/              # Scripts for managing the production environment
    ├── api.py            # API service for reconstruction
    ├── entrypoint.sh     # Container entrypoint script
    ├── healthcheck.py    # Service health checks
    ├── reconstruct.py    # Core reconstruction logic
    ├── run_production.sh # Main script to run the production environment
    └── upload_to_minio.py # File upload utility
```

## Requirements

- Docker and Docker Compose
- Image dataset (a sequence of images capturing an object from different angles)
- At least 8GB RAM recommended for reconstruction
- Approximately 10GB free disk space

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

This project makes use of several open-source technologies:

- COLMAP for Structure from Motion and Multi-View Stereo
- PyMeshLab for mesh processing
- MinIO for object storage
- Airflow for pipeline orchestration
- Docker for containerization
- Prometheus for metrics collection
- Grafana for metrics visualization


