#!/bin/bash

# Color variables for output formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function for printing success messages
print_success() {
    echo -e "${GREEN}[E2E3D Production] $1${NC}"
}

# Function for printing warning messages
print_warning() {
    echo -e "${YELLOW}[E2E3D Production] $1${NC}"
}

# Function for printing error messages
print_error() {
    echo -e "${RED}[E2E3D Production] $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create necessary directories
print_success "Creating data directories..."
mkdir -p data/input data/output airflow/logs

# Setup Airflow reconstruct.py script
print_success "Setting up Airflow reconstruct script..."
cp issues/airflow_reconstruct.py reconstruct.py.airflow

# Clean up existing containers
print_warning "Stopping any running containers..."
docker-compose -f docker-compose-fixed.yml down -v

# Build the images with fixed Dockerfiles
print_success "Building Docker images..."

# Build base image
print_success "Building base image (1/4)..."
docker build -t e2e3d-base:latest -f docker/base/Dockerfile .
if [ $? -ne 0 ]; then
    print_error "Failed to build base image. Check the logs for details."
    exit 1
fi

# Build COLMAP image
print_success "Building COLMAP image (2/4)..."
docker build -t e2e3d-colmap:latest -f docker/colmap/Dockerfile .
if [ $? -ne 0 ]; then
    print_error "Failed to build COLMAP image. Check the logs for details."
    exit 1
fi

# Build reconstruction image
print_success "Building reconstruction image (3/4)..."
docker build -t e2e3d-reconstruction:latest -f docker/e2e3d-reconstruction/Dockerfile .
if [ $? -ne 0 ]; then
    print_error "Failed to build reconstruction image. Check the logs for details."
    exit 1
fi

# Check if requirements-airflow-fixed.txt exists, create if not
if [ ! -f "requirements-airflow-fixed.txt" ]; then
    print_warning "Creating fixed airflow requirements file..."
    cp requirements-airflow.txt requirements-airflow-fixed.txt
    # Remove problematic packages or update versions
    sed -i.bak 's/numpy==1.18.5/numpy==1.21.6/g' requirements-airflow-fixed.txt
fi

# Check if Dockerfile.fixed exists for airflow, create if not
if [ ! -f "docker/airflow/Dockerfile.fixed" ]; then
    print_warning "Creating fixed airflow Dockerfile..."
    cp docker/airflow/Dockerfile docker/airflow/Dockerfile.fixed
    # Update to use fixed requirements file
    sed -i.bak 's/requirements-airflow.txt/requirements-airflow-fixed.txt/g' docker/airflow/Dockerfile.fixed
fi

# Build Airflow image using fixed Dockerfile
print_success "Building Airflow image (4/4)..."
docker build -t e2e3d-airflow:latest -f docker/airflow/Dockerfile.fixed .
if [ $? -ne 0 ]; then
    print_error "Failed to build Airflow image. Check the logs for details."
    exit 1
fi

# Create docker-compose-fixed.yml if it doesn't exist
if [ ! -f "docker-compose-fixed.yml" ]; then
    print_warning "Creating fixed docker-compose file..."
    cat > docker-compose-fixed.yml << 'EOF'
version: '3.8'

services:
  minio:
    container_name: e2e3d-minio
    image: minio/minio:RELEASE.2023-07-21T21-12-44Z
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-volume:/data
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
    networks:
      - e2e3d-network

  minio-setup:
    container_name: e2e3d-minio-setup
    image: minio/mc
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      sleep 5;
      /usr/bin/mc config host add myminio http://minio:9000 minioadmin minioadmin;
      /usr/bin/mc mb myminio/models;
      /usr/bin/mc policy set public myminio/models;
      /usr/bin/mc mb myminio/input-data;
      /usr/bin/mc policy set public myminio/input-data;
      exit 0;
      "
    networks:
      - e2e3d-network

  postgres:
    container_name: e2e3d-postgres
    image: postgres:13
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - postgres-db-volume:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - e2e3d-network

  airflow-webserver:
    container_name: e2e3d-airflow-webserver
    image: e2e3d-airflow:latest
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./data:/app/data
      - ./reconstruct.py.airflow:/opt/airflow/reconstruct.py
    ports:
      - "8080:8080"
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
      AIRFLOW__CORE__FERNET_KEY: ""
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "true"
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__API__AUTH_BACKENDS: "airflow.api.auth.backend.basic_auth"
      AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: "1"
      AIRFLOW_HOME: "/opt/airflow"
      AIRFLOW__S3__ENDPOINT_URL: "http://minio:9000"
      AIRFLOW__S3__AWS_ACCESS_KEY_ID: "minioadmin"
      AIRFLOW__S3__AWS_SECRET_ACCESS_KEY: "minioadmin"
      AIRFLOW_WEBSERVER_PORT: "8080"
    command: >
      bash -c "airflow db init && 
      airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com &&
      airflow webserver"
    networks:
      - e2e3d-network

  airflow-scheduler:
    container_name: e2e3d-airflow-scheduler
    image: e2e3d-airflow:latest
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./data:/app/data
      - ./reconstruct.py.airflow:/opt/airflow/reconstruct.py
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
      AIRFLOW__CORE__FERNET_KEY: ""
      AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: "true"
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__API__AUTH_BACKENDS: "airflow.api.auth.backend.basic_auth"
      AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: "1"
      AIRFLOW_HOME: "/opt/airflow"
      AIRFLOW__S3__ENDPOINT_URL: "http://minio:9000"
      AIRFLOW__S3__AWS_ACCESS_KEY_ID: "minioadmin"
      AIRFLOW__S3__AWS_SECRET_ACCESS_KEY: "minioadmin"
    command: airflow scheduler
    networks:
      - e2e3d-network

  e2e3d-reconstruction-service:
    container_name: e2e3d-reconstruction-service
    image: e2e3d-reconstruction:latest
    volumes:
      - ./data:/app/data
    environment:
      MINIO_ENDPOINT: "minio:9000"
      MINIO_ACCESS_KEY: "minioadmin"
      MINIO_SECRET_KEY: "minioadmin"
      MINIO_SECURE: "false"
      USE_GPU: "false"
    # Command to keep container running - actual reconstruction will be triggered through Airflow
    command: tail -f /dev/null
    networks:
      - e2e3d-network

volumes:
  minio-volume:
  postgres-db-volume:

networks:
  e2e3d-network:
    driver: bridge
EOF
fi

# Start the services
print_success "Starting E2E3D services..."
docker-compose -f docker-compose-fixed.yml up -d

# Check if services started successfully
if [ $? -ne 0 ]; then
    print_error "Failed to start services. Check the logs for details."
    exit 1
fi

# Wait for Airflow to be ready
print_success "Waiting for Airflow to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8080 > /dev/null; then
        print_success "Airflow is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT+1))
    print_warning "Waiting for Airflow... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Airflow did not start within the expected time."
    print_warning "Please check Docker logs for errors: docker logs e2e3d-airflow-webserver"
    exit 1
fi

# Print access information
print_success "Production environment is running!"
print_success "Access MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
print_success "Access Airflow: http://localhost:8080 (admin/admin)"
print_success "To trigger the DAG, go to Airflow UI and enable the e2e3d_reconstruction_dag, then trigger it manually."
print_success "To monitor logs: docker logs -f e2e3d-airflow-webserver" 