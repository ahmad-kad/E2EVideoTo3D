# E2E3D Mac Setup Guide

This guide provides detailed instructions on how to set up and run the E2E3D Docker environment on macOS. Follow these steps to ensure everything is configured correctly and running smoothly.

## Prerequisites

Before you begin, ensure you have the following installed on your macOS system:

- **Docker Desktop for Mac**: This is required to run Docker containers on macOS. You can download and install it from [Docker's official website](https://docs.docker.com/desktop/install/mac-install/).

- **Command Line Tools**: Ensure you have the necessary command line tools installed. You can install them by running:
  ```bash
  xcode-select --install
  ```

## Setup Instructions

1. **Clone the Repository**
   
   First, clone the E2E3D repository to your local machine:
   ```bash
   git clone <repository-url>
   cd e2e3d
   ```

2. **Run the Mac Startup Helper Script**

   The `mac-start.sh` script is designed to set up the Docker environment specifically for macOS. It configures the necessary platform settings and starts the services.

   ```bash
   ./mac-start.sh
   ```

   This script will:
   - Set the Docker build platform to `linux/amd64` for compatibility.
   - Check if Docker is installed and running.
   - Build the Docker containers with the correct platform settings.
   - Start the services in detached mode.

3. **Access the Services**

   Once the services are started, you can access them through the following endpoints:
   - **Airflow Webserver**: [http://localhost:8080](http://localhost:8080)
   - **MinIO Console**: [http://localhost:9001](http://localhost:9001) (login: `minioadmin` / `minioadmin`)
   - **Spark Master UI**: [http://localhost:8001](http://localhost:8001)

## Verification Steps

1. **Upload a Test Video File**

   Upload a test video file to the `raw-videos` bucket in MinIO to ensure the storage is working correctly.

2. **Unpause the Photogrammetry Pipeline DAG**

   In the Airflow UI, navigate to the DAGs page and unpause the `photogrammetry_pipeline` DAG to start processing.

3. **Monitor the Pipeline Execution**

   Use the Airflow UI to monitor the execution of the pipeline. Check the logs and task statuses to ensure everything is running smoothly.

4. **Verify the Generated 3D Model**

   After the pipeline execution, verify that the generated 3D model is available in the `models` bucket in MinIO.

## Troubleshooting

- If you encounter any issues with Docker not starting, ensure Docker Desktop is running and try restarting it.
- Check the logs for any errors by running:
  ```bash
  docker-compose logs -f <service_name>
  ```
- If services fail to start, try rebuilding the containers:
  ```bash
  docker-compose build --no-cache
  ```

## Stopping the Services

To stop all running services, execute:
```bash
  docker-compose down
```

This will gracefully stop and remove all containers.

---

By following this guide, you should be able to set up and run the E2E3D environment on macOS successfully. If you encounter any issues, refer to the troubleshooting section or consult the Docker and service logs for more information. 