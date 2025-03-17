# Project Structure Guide

This document explains the organization of the E2E3D project.

## Overview

The E2E3D project is organized into the following main components:

1. **Source Code**: Python modules for reconstruction and processing
2. **Docker Configuration**: Dockerfiles and related scripts
3. **Airflow DAGs**: Workflow definitions for Airflow
4. **Scripts**: Utility scripts for various tasks
5. **Data**: Input and output data directories

## Directory Structure

```
e2e3d/
├── src/                       # Source code
│   ├── reconstruction/        # Reconstruction modules
│   │   ├── colmap/            # COLMAP integration
│   │   ├── mesh/              # Mesh generation
│   │   └── cli.py             # Command-line interface
│   ├── photogrammetry/        # Photogrammetry utilities
│   └── utils/                 # Utility functions
├── docker/                    # Docker configuration
│   ├── base/                  # Base Docker image
│   ├── colmap/                # COLMAP Docker image
│   ├── airflow/               # Airflow Docker image
│   └── scripts/               # Docker entrypoint scripts
├── scripts/                   # Utility scripts
├── airflow/                   # Airflow DAGs
│   ├── dags/                  # DAG definitions
│   └── plugins/               # Airflow plugins
├── image_sets/                # Input image sets
├── data/                      # Data directory (created at runtime)
│   ├── input/                 # Input data
│   ├── output/                # Output data
│   └── videos/                # Input videos
├── docs/                      # Documentation
├── reconstruct.py             # Main entry point script
├── docker-compose.yml         # Docker Compose configuration
├── requirements-*.txt         # Dependency files
└── run.sh                     # Main startup script
```

## Key Components

### Source Code (`src/`)

The `src/` directory contains the Python modules for the project:

- `reconstruction/`: Core reconstruction functionality
  - `colmap/`: Integration with COLMAP
  - `mesh/`: Mesh generation algorithms
  - `cli.py`: Command-line interface
- `photogrammetry/`: Photogrammetry utilities
- `utils/`: Shared utility functions

### Docker Configuration (`docker/`)

The `docker/` directory contains Dockerfiles and related scripts:

- `base/`: Base Docker image with common dependencies
- `colmap/`: COLMAP Docker image for reconstruction
- `airflow/`: Airflow Docker image for workflow orchestration
- `scripts/`: Docker entrypoint scripts

### Airflow DAGs (`airflow/`)

The `airflow/` directory contains Airflow DAGs and plugins:

- `dags/`: DAG definitions for workflow orchestration
- `plugins/`: Custom Airflow plugins

### Scripts (`scripts/`)

The `scripts/` directory contains utility scripts:

- `run_reconstruction.sh`: Script to run reconstruction directly
- Other utility scripts for various tasks

### Data Directories

The following directories are used for data:

- `image_sets/`: Input image sets
- `data/`: Data directory (created at runtime)
  - `input/`: Input data
  - `output/`: Output data
  - `videos/`: Input videos

### Configuration Files

The project includes the following configuration files:

- `docker-compose.yml`: Docker Compose configuration
- `requirements-*.txt`: Dependency files
- `.env`: Environment variables (created at runtime)

## Entry Points

The main entry points for the project are:

- `reconstruct.py`: Main entry point script for reconstruction
- `run.sh`: Main startup script for Docker services
- `scripts/run_reconstruction.sh`: Script to run reconstruction directly 