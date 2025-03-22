# E2E3D System Overview

## Introduction

Welcome to the E2E3D (End-to-End 3D) reconstruction system! This document provides a high-level overview of the system architecture, components, and workflow. E2E3D is designed to provide an end-to-end pipeline for converting 2D images into detailed 3D models through photogrammetry techniques.

## What is Photogrammetry?

Photogrammetry is the science of making measurements from photographs, especially for recovering the exact positions of surface points. In the context of 3D reconstruction, photogrammetry involves:

1. Taking multiple overlapping photographs of an object or scene from different angles
2. Identifying common features across these images
3. Using these common points to determine camera positions and orientations
4. Generating a 3D point cloud representing the structure
5. Creating a meshed surface with texture mapping

## System Architecture

The E2E3D system is designed with a microservices architecture, containerized with Docker, and orchestrated with Docker Compose for development and testing (with Kubernetes support for production deployments).

### Core Components

1. **Reconstruction Service**: The main engine that processes images and creates 3D models
2. **API**: HTTP interface for submitting jobs and retrieving results
3. **Airflow**: Workflow orchestration for complex job scheduling and monitoring
4. **Storage System**: MinIO object storage for input data and output models

### Support Components

1. **Monitoring**: Prometheus and Grafana for system metrics and monitoring
2. **Database**: PostgreSQL for job metadata and system state
3. **Cache/Queue**: Redis for job queuing and task distribution
4. **Proxy**: NGINX for routing and load balancing

## Workflow Overview

1. **Input**: A set of images is provided (either directly or through an API call)
2. **Processing**: The reconstruction service processes these images through several stages:
   - Feature detection and matching
   - Camera position estimation
   - Sparse point cloud generation
   - Dense point cloud generation
   - Mesh generation
   - Texture mapping
3. **Output**: The system produces several artifacts:
   - 3D mesh (OBJ file)
   - Texture maps (PNG files)
   - Point cloud data (PLY files)
   - Metadata

## Directory Structure

```
e2e3d/
├── data/              # Data directory for input and output
│   ├── input/         # Input images
│   └── output/        # Generated 3D models and artifacts
├── docs/              # Documentation
│   └── edu/           # Educational materials (you are here)
├── production/        # Production deployment files
│   ├── dags/          # Airflow DAG definitions
│   ├── scripts/       # Utility scripts
│   └── config/        # Configuration files
├── tests/             # Test suite
│   ├── unit/          # Unit tests
│   └── integration/   # Integration tests
└── README.md          # Main README
```

## Getting Started

If you're new to the project, we recommend exploring the documentation in the following order:

1. This overview document
2. Core components:
   - [Reconstruction Service](02_CORE_RECONSTRUCTION.md)
   - [API and Job Management](03_CORE_API.md)
   - [Workflow Orchestration with Airflow](04_CORE_AIRFLOW.md)
   - [Storage System](05_CORE_STORAGE.md)
3. Support components:
   - [Monitoring and Metrics](06_SUPPORT_MONITORING.md)
   - [Database Design](07_SUPPORT_DATABASE.md)
   - [Containerization and Deployment](08_SUPPORT_DEPLOYMENT.md)

## Learning Path

Depending on your role within the project, you might want to focus on different aspects:

- **3D Graphics Engineer**: Focus on the reconstruction service
- **Backend Developer**: API, database, and workflow orchestration
- **DevOps Engineer**: Containerization, deployment, and monitoring
- **Data Scientist**: Reconstruction algorithms and point cloud processing

## Conclusion

The E2E3D system is designed to be modular, scalable, and maintainable. Each component has a specific role in the pipeline, and they all work together to provide a seamless experience for converting 2D images to 3D models.

In the following documents, we will dive deeper into each component, explaining its purpose, design, implementation details, and how it fits into the overall system. 