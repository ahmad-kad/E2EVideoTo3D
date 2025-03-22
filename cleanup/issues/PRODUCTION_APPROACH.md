# E2E3D Production Approach

This document outlines our approach to productionizing the E2E3D pipeline, the issues encountered, and the solutions implemented.

## Approach Overview

Our approach to running the E2E3D pipeline in production focused on:

1. Simplifying dependencies to improve reliability
2. Using Docker for consistent deployment
3. Creating a minimal but functional pipeline
4. Implementing robust error handling
5. Documenting issues and their solutions

## Production Components

The production pipeline consists of the following components:

1. **MinIO Object Storage**: For storing input data and output 3D meshes
2. **Reconstruction Service**: A containerized service for processing input images and generating 3D meshes
3. **Upload Service**: A utility for uploading reconstructed meshes to MinIO with public access

## Issues and Solutions

During the productionization process, we encountered several issues:

### 1. Package Dependency Issues

**Issue**: Numpy 1.18.5 was failing to build in the Docker container due to Cython compilation errors.

**Solution**: Updated to numpy 1.21.6 which provides pre-compiled wheels for the Python 3.7 environment.

### 2. Complex Dependencies Management

**Issue**: The original requirements file contained many packages with complex interdependencies.

**Solution**: Created a minimal requirements set with only essential packages for the reconstruction pipeline.

### 3. Docker Build Process

**Issue**: The Docker build process was failing due to package installation errors.

**Solution**: Simplified the Dockerfile and installed packages individually to isolate and fix issues.

### 4. DAG Execution in Airflow

**Issue**: Airflow DAG execution was complex and had many dependencies.

**Solution**: Created a simplified approach that runs the reconstruction directly without Airflow for testing and validation.

## Production Pipeline Flow

The production pipeline follows these steps:

1. Start MinIO object storage service
2. Set up MinIO buckets with proper access permissions
3. Run the reconstruction process on input images
4. Upload the resulting 3D mesh to MinIO
5. Make the mesh accessible via a public URL

## Running the Production Pipeline

To run the production pipeline:

```bash
./issues/run_minimal_pipeline.sh
```

This script will:
1. Build the necessary Docker images
2. Start the required services
3. Run the reconstruction process
4. Upload the output to MinIO

## Accessing the Output

After running the pipeline, you can access:

- The MinIO console at: http://localhost:9001 (login: minioadmin/minioadmin)
- The reconstructed mesh directly at: http://localhost:9000/models/reconstructed_mesh.obj

## Future Improvements

Potential future improvements for the production pipeline:

1. Implement proper monitoring and alerting
2. Add more robust error handling and recovery mechanisms
3. Support for processing multiple input datasets in parallel
4. Integration with a workflow orchestration system for complex pipelines
5. Automated testing for the complete pipeline
6. Optimized resource usage for larger-scale deployments 