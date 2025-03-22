#!/bin/bash

# E2E3D Fixed Image Builder
# This script builds Docker images using fixed Dockerfiles to address compatibility issues

# Color variables for pretty output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
  echo -e "${BLUE}[E2E3D Build]${NC} $1"
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

# Create data directories if they don't exist
print_step "Creating data directories..."
mkdir -p data/input data/output
mkdir -p airflow/logs

# Copy the fixed requirements file to the correct location
print_step "Setting up fixed requirements files..."
cp requirements-airflow-fixed.txt requirements-airflow.txt

# Copy the fixed Dockerfile for base image
print_step "Setting up fixed Dockerfiles..."
cp docker/base/Dockerfile.fixed docker/base/Dockerfile
cp docker/airflow/Dockerfile.fixed docker/airflow/Dockerfile

# Stop any running containers and clean up
print_step "Stopping any running containers..."
docker-compose down -v

# Build the base image first
print_step "Building base image (1/4)..."
if ! docker build -t e2e3d-base:latest -f docker/base/Dockerfile .; then
  print_error "Failed to build base image. Check the logs for details."
  exit 1
fi
print_success "Base image built successfully!"

# Build the COLMAP image
print_step "Building COLMAP image (2/4)..."
if ! docker build -t e2e3d-colmap:latest -f docker/colmap/Dockerfile .; then
  print_error "Failed to build COLMAP image. Check the logs for details."
  exit 1
fi
print_success "COLMAP image built successfully!"

# Build the reconstruction image
print_step "Building reconstruction image (3/4)..."
if ! docker build -t e2e3d-reconstruction:latest -f docker/e2e3d-reconstruction/Dockerfile .; then
  print_error "Failed to build reconstruction image. Check the logs for details."
  exit 1
fi
print_success "Reconstruction image built successfully!"

# Build the Airflow image with fixed Dockerfile
print_step "Building Airflow image (4/4)..."
if ! docker build -t e2e3d-airflow:latest -f docker/airflow/Dockerfile .; then
  print_error "Failed to build Airflow image. Check the logs for details."
  print_warning "Continuing without Airflow - you can still use MinIO and reconstruction services."
else
  print_success "Airflow image built successfully!"
fi

print_success "All images built successfully!"
echo 
echo "Next steps:"
echo "1. To start the full pipeline:    docker-compose -f docker-compose-fixed.yml up -d"
echo "2. For MinIO only:               docker-compose -f docker-compose-fixed.yml up -d minio minio-setup"
echo
print_step "You can also use ./start_pipeline.sh for a guided setup"

exit 0 