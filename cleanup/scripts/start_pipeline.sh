#!/bin/bash

# E2E3D Pipeline Starter
# This script builds necessary Docker images and starts the pipeline services

# Color variables for pretty output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
  echo -e "${BLUE}[E2E3D Pipeline]${NC} $1"
}

print_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  print_error "Docker is not running. Please start Docker Desktop and try again."
  exit 1
fi

# Check if fixed config file exists
if [ ! -f "docker-compose-fixed.yml" ]; then
  print_error "Fixed Docker Compose file not found. Please run build_fixed_images.sh first."
  exit 1
fi

# Create data directories if they don't exist
print_step "Creating data directories..."
mkdir -p data/input data/output
mkdir -p airflow/logs

# Check if we need to build images
if ! docker images | grep -q "e2e3d-base"; then
  print_warning "Required Docker images not found. Running build_fixed_images.sh first..."
  if [ -f "./build_fixed_images.sh" ]; then
    ./build_fixed_images.sh
  else
    print_error "build_fixed_images.sh not found. Please run it manually."
    exit 1
  fi
fi

# Start minimal services for reconstruction
if [ "$1" == "--minimal" ]; then
  print_step "Starting minimal services (MinIO only)..."
  if ! docker-compose -f docker-compose-fixed.yml up -d minio minio-setup; then
    print_error "Failed to start minimal services."
    exit 1
  fi
  print_success "MinIO services are running!"
  print_step "Use run_e2e3d_pipeline.sh to process images"
  echo
  echo "MinIO web console: http://localhost:9001 (login: minioadmin/minioadmin)"
  exit 0
fi

# Start all services
print_step "Starting all services (MinIO, PostgreSQL, Airflow)..."
if ! docker-compose -f docker-compose-fixed.yml up -d minio minio-setup postgres airflow-webserver airflow-scheduler; then
  print_warning "Failed to start all services. Trying with minimal setup (MinIO only)..."
  if ! docker-compose -f docker-compose-fixed.yml up -d minio minio-setup; then
    print_error "Failed to start even minimal services."
    exit 1
  fi
  print_success "MinIO services are running, but Airflow services failed."
  print_step "You can still use run_e2e3d_pipeline.sh to process images directly."
  echo
  echo "MinIO web console: http://localhost:9001 (login: minioadmin/minioadmin)"
  exit 1
fi

print_success "E2E3D pipeline is running!"
echo
echo "Access points:"
echo "• Airflow: http://localhost:8080 (login: admin/admin)"
echo "• MinIO Console: http://localhost:9001 (login: minioadmin/minioadmin)"
echo
print_step "To process images directly, use: ./run_e2e3d_pipeline.sh /path/to/images"
print_step "To stop all services: docker-compose -f docker-compose-fixed.yml down"
echo

# Wait for Airflow to be ready
print_step "Waiting for Airflow to be ready..."
RETRY_COUNT=0
MAX_RETRIES=30
while ! curl -s http://localhost:8080/health > /dev/null; do
  RETRY_COUNT=$((RETRY_COUNT+1))
  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_warning "Airflow might still be starting. Check http://localhost:8080 in a moment."
    break
  fi
  echo -n "."
  sleep 2
done
echo

if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
  print_success "Airflow is ready! Access the UI at http://localhost:8080"
fi

exit 0 