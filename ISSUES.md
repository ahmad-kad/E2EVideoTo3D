# Known Issues and Resolutions

This document tracks issues encountered during setup and operation of the E2E Video to 3D Pipeline, along with their resolutions.

## Resolved Issues

### Meshroom Path and Symbolic Links

**Issue**: The Meshroom installation directory structure didn't match what was expected in the original Dockerfile. The extracted directory was named `Meshroom-2021.1.0-av2.4.0-centos7-cuda10.2` instead of the expected `Meshroom-2021.1.0-linux-cuda10` or `Meshroom-2021.1.0-cuda10`.

**Resolution**: 
- Updated the Dockerfile to use a more robust method to find the Meshroom directory
- Added a more comprehensive check in `setup_environment.sh` to correctly create symbolic links
- The system now dynamically finds the correct Meshroom directory regardless of its exact name

### Airflow DAG Module Import Errors

**Issue**: The Airflow DAG was failing to import necessary modules from the `src` directory.

**Resolution**:
- Implemented a mock mode in the DAG that provides basic implementations when the actual modules aren't available
- This allows the DAG to be properly loaded and recognized by Airflow even if the source modules aren't complete

### MinIO Bucket Creation

**Issue**: MinIO buckets needed to be manually created after each restart.

**Resolution**:
- Added a dedicated `minio-init` service to docker-compose.yml that automatically creates required buckets
- Buckets are now created automatically when the system starts up

### Spark Configuration

**Issue**: Spark workers weren't properly connecting to the Spark master.

**Resolution**:
- Verified and corrected the Spark configuration in docker-compose.yml
- Ensured that the Spark master URL is correctly specified for workers

## Current Limitations

### CPU Usage for Photogrammetry

- The Meshroom process is resource-intensive and can take a long time without GPU acceleration
- On systems without an NVIDIA GPU, expect processing times to be significantly longer

### Storage Considerations

- Processing videos generates large amounts of intermediate data
- Ensure adequate disk space is available (at least 10GB for a typical short video)

### Security Considerations

- Default credentials are used for development purposes only (minioadmin/minioadmin for MinIO, airflow/airflow for Airflow)
- These should be changed before any production deployment

## Reporting New Issues

If you encounter new issues, please report them in the GitHub Issues section with:

1. A clear description of the problem
2. Steps to reproduce
3. Expected vs. actual behavior
4. Any relevant logs or error messages

---

**Last Updated**: 2024-07-16 