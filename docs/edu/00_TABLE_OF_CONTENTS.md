# E2E3D Educational Documentation

Welcome to the E2E3D educational documentation. This collection of documents is designed to help new users and developers understand the E2E3D platform for automated 3D reconstruction from images.

## Overview

This documentation is organized into four main sections:

1. **Quick Start** - Get up and running quickly
2. **Project Overview** - A high-level introduction to the E2E3D system
3. **Core Components** - In-depth documentation of the main components
4. **Support Systems** - Documentation of supporting components and practices

Each document is designed to be both educational and practical, explaining not just how things work but also why they're designed that way.

## How to Use This Documentation

- **First-time users** should start with the Quick Start Guide
- **New users** should start with the Project Overview and then explore Core Components
- **Developers** should read the Project Overview and then focus on Development Workflow
- **System administrators** will benefit most from the Deployment and Metrics documents
- **Advanced users** may want to explore all documents to gain a comprehensive understanding

## Document Index

### Getting Started

[**09_QUICKSTART.md**](09_QUICKSTART.md)
- Quick installation guide
- Basic usage tutorial
- Complete workflow example
- Common issues and solutions
- Next steps

### Project Overview

[**01_PROJECT_OVERVIEW.md**](01_PROJECT_OVERVIEW.md)
- Introduction to the E2E3D system
- Basic concepts of photogrammetry and 3D reconstruction
- System architecture overview
- Workflow overview
- Directory structure
- Getting started guide

### Core Components

[**02_CORE_RECONSTRUCTION.md**](02_CORE_RECONSTRUCTION.md)
- Photogrammetry pipeline
- Reconstruction service
- Algorithms used
- Performance considerations
- Advanced reconstruction options

[**03_CORE_API.md**](03_CORE_API.md)
- API design and principles
- Job management
- API endpoints reference
- Authentication and security
- Client integration

[**04_CORE_AIRFLOW.md**](04_CORE_AIRFLOW.md)
- Workflow orchestration
- DAG structure
- Task scheduling
- Error handling
- Custom operators

[**05_CORE_STORAGE.md**](05_CORE_STORAGE.md)
- Object storage architecture
- File storage structure
- MinIO configuration
- Data lifecycle management
- Performance optimization

### Support Systems

[**06_SUPPORT_METRICS.md**](06_SUPPORT_METRICS.md)
- Monitoring architecture
- Prometheus and Grafana setup
- Key metrics explained
- Dashboard configuration
- Alerting and notification

[**07_SUPPORT_DEPLOYMENT.md**](07_SUPPORT_DEPLOYMENT.md)
- Containerization strategy
- Docker configuration
- Deployment options
- Scaling considerations
- Security best practices

[**08_SUPPORT_DEVELOPMENT.md**](08_SUPPORT_DEVELOPMENT.md)
- Development workflow
- Coding standards
- Testing guidelines
- Pull request process
- Documentation guidelines

## Learning Paths

### For New Users

1. [Quick Start Guide](09_QUICKSTART.md)
2. [Project Overview](01_PROJECT_OVERVIEW.md)
3. [API](03_CORE_API.md)

### For Operators

1. [Quick Start Guide](09_QUICKSTART.md)
2. [Project Overview](01_PROJECT_OVERVIEW.md)
3. [API](03_CORE_API.md)
4. [Storage](05_CORE_STORAGE.md)
5. [Metrics](06_SUPPORT_METRICS.md)
6. [Deployment](07_SUPPORT_DEPLOYMENT.md)

### For Developers

1. [Quick Start Guide](09_QUICKSTART.md)
2. [Project Overview](01_PROJECT_OVERVIEW.md)
3. [Development](08_SUPPORT_DEVELOPMENT.md)
4. [Reconstruction](02_CORE_RECONSTRUCTION.md)
5. [API](03_CORE_API.md)
6. [Airflow](04_CORE_AIRFLOW.md)
7. [Storage](05_CORE_STORAGE.md)

### For Data Scientists

1. [Quick Start Guide](09_QUICKSTART.md)
2. [Project Overview](01_PROJECT_OVERVIEW.md)
3. [Reconstruction](02_CORE_RECONSTRUCTION.md)
4. [Airflow](04_CORE_AIRFLOW.md)
5. [Metrics](06_SUPPORT_METRICS.md)

## Contributing to This Documentation

If you find any issues or have suggestions for improving this documentation, please refer to the [Development Workflow and Contribution Guidelines](08_SUPPORT_DEVELOPMENT.md) for information on how to contribute.

## Additional Resources

- [API Reference Documentation](../api/)
- [Architecture Documents](../architecture/)
- [System Usage Guide](../USAGE.md)
- [Full README](../../README.md) 