# E2E3D Production Environment

This directory contains the production deployment configuration for the E2E3D 3D reconstruction pipeline.

## Overview

The E2E3D production environment is a containerized solution that provides a complete end-to-end 3D reconstruction pipeline. It includes:

- Object storage (MinIO)
- Workflow orchestration (Airflow)
- Reconstruction service
- Monitoring and metrics (Prometheus/Grafana)
- API gateway and web access (NGINX)

## Architecture

The production setup consists of the following components:

![E2E3D Architecture](https://via.placeholder.com/800x400?text=E2E3D+Production+Architecture)

1. **MinIO**: Object storage for input images and output meshes
2. **Airflow**: Workflow orchestration for managing reconstruction jobs
3. **Reconstruction Service**: Runs the 3D reconstruction process
4. **Prometheus**: Collects metrics from all services
5. **Grafana**: Visualizes metrics and provides monitoring dashboards
6. **NGINX**: API gateway and web interface for accessing services

## Requirements

- Docker 20.10 or higher
- Docker Compose 2.0 or higher
- 8GB RAM minimum (16GB recommended)
- 50GB free disk space

## Quick Start

1. Clone this repository:

```bash
git clone https://github.com/your-org/e2e3d.git
cd e2e3d
```

2. Build and start the production environment:

```bash
./production/scripts/run_production.sh build
```

3. Access the services:

- Main Dashboard: http://localhost:80
- MinIO Console: http://localhost:9001 (default login: minioadmin/minioadmin)
- Airflow: http://localhost:8080 (default login: admin/admin)
- Grafana: http://localhost:3000 (default login: admin/admin)
- Prometheus: http://localhost:9090

## Configuration

The environment can be configured using the `.env` file in the `production` directory. The first time you run the `run_production.sh` script, a default `.env` file will be created if it doesn't exist.

Important configuration options:

```properties
# Docker Registry Settings
DOCKER_REGISTRY=localhost
IMAGE_TAG=latest

# MinIO Settings
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# PostgreSQL Settings
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow

# Airflow Settings
AIRFLOW_FERNET_KEY=
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin

# Grafana Settings
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# Reconstruction Settings
USE_GPU=false
MAX_WORKERS=4
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

## Usage

### Running Reconstruction Jobs

There are two ways to run reconstruction jobs:

#### 1. Using Airflow

1. Place your input images in the `data/input` directory
2. Go to Airflow UI at http://localhost:8080
3. Enable and trigger the `e2e3d_reconstruction_dag` DAG
4. Monitor the progress in the Airflow UI
5. Access your output files in MinIO at http://localhost:9001

#### 2. Direct API Access

The reconstruction service also exposes an API endpoint that you can use to trigger jobs:

```bash
curl -X POST \
  http://localhost:80/api/reconstruction \
  -H 'Content-Type: application/json' \
  -d '{
    "input_dir": "/app/data/input",
    "quality": "medium",
    "use_gpu": "auto",
    "upload": true
  }'
```

### Accessing Output Files

Output files can be accessed in several ways:

1. Through the MinIO Console at http://localhost:9001
2. Through the web interface at http://localhost:80/output/
3. Directly in the `data/output` directory on the host

### Monitoring

The production environment includes comprehensive monitoring:

1. Grafana dashboards at http://localhost:3000
2. Prometheus metrics at http://localhost:9090
3. Airflow logs and monitoring at http://localhost:8080

## Management Commands

The `run_production.sh` script provides several commands:

```bash
# Build and start the environment
./production/scripts/run_production.sh build

# Start the environment with existing images
./production/scripts/run_production.sh

# Stop all services and remove containers
./production/scripts/run_production.sh clean
```

Additional Docker Compose commands:

```bash
# View logs from all services
docker-compose -f production/docker-compose.yml logs -f

# View logs from a specific service
docker-compose -f production/docker-compose.yml logs -f airflow-webserver

# Restart a specific service
docker-compose -f production/docker-compose.yml restart e2e3d-reconstruction-service

# Stop all services
docker-compose -f production/docker-compose.yml down
```

## Directory Structure

```
production/
├── config/                   # Configuration files
│   ├── grafana/              # Grafana configuration
│   ├── nginx/                # NGINX configuration
│   └── prometheus.yml        # Prometheus configuration
├── scripts/                  # Utility scripts
│   ├── entrypoint.sh         # Docker entrypoint script
│   ├── healthcheck.py        # Container health check
│   ├── reconstruct.py        # Reconstruction script
│   ├── run_production.sh     # Main startup script
│   └── upload_to_minio.py    # MinIO upload utility
├── .env                      # Environment variables
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile.airflow        # Airflow image definition
├── Dockerfile.reconstruction # Reconstruction image definition
└── README.md                 # This file
```

## Troubleshooting

### Common Issues

1. **Services not starting**: Check Docker logs with `docker-compose -f production/docker-compose.yml logs`
2. **MinIO not accessible**: Ensure port 9000 is not already in use by another application
3. **Reconstruction failing**: Check logs with `docker logs e2e3d-reconstruction-service`
4. **Airflow not starting**: Check logs with `docker logs e2e3d-airflow-webserver`

### Logs Location

- Container logs: Access with `docker logs` or through Airflow/Grafana UI
- Application logs: Located in the `logs` directory
- Output files: Located in the `data/output` directory

## Security Considerations

This default setup is intended for development and testing purposes. For production deployment, consider:

1. Setting strong passwords in the `.env` file
2. Enabling HTTPS for all services
3. Implementing proper authentication
4. Restricting network access
5. Regular security updates

## Advanced Configuration

For advanced configuration, refer to the documentation of each component:

- [Airflow Documentation](https://airflow.apache.org/docs/)
- [MinIO Documentation](https://docs.min.io/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [NGINX Documentation](https://nginx.org/en/docs/)

## Contributing

Contributions to improve the production environment are welcome. Please follow the standard pull request process. 