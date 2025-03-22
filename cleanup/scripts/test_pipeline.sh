#!/bin/bash

# Test script for E2E3D Pipeline
# This script verifies that the fixed pipeline works properly

# Color variables for pretty output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
  echo -e "${BLUE}[TEST]${NC} $1"
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

# Test 1: Check if fixed Docker Compose file exists
print_step "Test 1: Checking for fixed Docker Compose file..."
if [ -f "docker-compose-fixed.yml" ]; then
  print_success "docker-compose-fixed.yml exists"
else
  print_error "docker-compose-fixed.yml does not exist. Please run build_fixed_images.sh first."
  exit 1
fi

# Test 2: Check if required Docker images exist
print_step "Test 2: Checking for required Docker images..."
MISSING_IMAGES=0

check_image() {
  if docker image inspect $1:latest > /dev/null 2>&1; then
    print_success "$1 image exists"
  else
    print_error "$1 image does not exist"
    MISSING_IMAGES=$((MISSING_IMAGES+1))
  fi
}

check_image "e2e3d-base"
check_image "e2e3d-colmap"
check_image "e2e3d-reconstruction" 
check_image "e2e3d-airflow"

if [ $MISSING_IMAGES -gt 0 ]; then
  print_error "$MISSING_IMAGES image(s) missing. Please run build_fixed_images.sh to build all required images."
  exit 1
fi

# Test 3: Check if MinIO can be started
print_step "Test 3: Testing MinIO startup..."
if docker-compose -f docker-compose-fixed.yml up -d minio minio-setup; then
  print_success "MinIO started successfully"
else
  print_error "Failed to start MinIO"
  exit 1
fi

# Wait for MinIO to be ready
print_step "Waiting for MinIO to be ready..."
RETRY_COUNT=0
MAX_RETRIES=30
while ! curl -s http://localhost:9000/minio/health/live > /dev/null; do
  RETRY_COUNT=$((RETRY_COUNT+1))
  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "MinIO service failed to start after $MAX_RETRIES attempts"
    docker-compose -f docker-compose-fixed.yml down
    exit 1
  fi
  echo -n "."
  sleep 1
done
echo ""
print_success "MinIO service is ready"

# Test 4: Check MinIO accessibility
print_step "Test 4: Testing MinIO accessibility..."
if curl -s http://localhost:9000/minio/health/live > /dev/null; then
  print_success "MinIO is accessible"
else
  print_error "MinIO is not accessible"
  docker-compose -f docker-compose-fixed.yml down
  exit 1
fi

# Test 5: Check if run script exists and is executable
print_step "Test 5: Checking run script..."
if [ -f "run_e2e3d_pipeline.sh" ]; then
  print_success "run_e2e3d_pipeline.sh exists"
  if [ -x "run_e2e3d_pipeline.sh" ]; then
    print_success "run_e2e3d_pipeline.sh is executable"
  else
    print_warning "run_e2e3d_pipeline.sh is not executable. Making it executable..."
    chmod +x run_e2e3d_pipeline.sh
    print_success "Made run_e2e3d_pipeline.sh executable"
  fi
else
  print_error "run_e2e3d_pipeline.sh does not exist"
  docker-compose -f docker-compose-fixed.yml down
  exit 1
fi

# Test 6: Check if upload script exists
print_step "Test 6: Checking upload script..."
if [ -f "upload_mesh_to_minio.py" ]; then
  print_success "upload_mesh_to_minio.py exists"
else
  print_error "upload_mesh_to_minio.py does not exist"
  docker-compose -f docker-compose-fixed.yml down
  exit 1
fi

# Stop services
print_step "Stopping test services..."
docker-compose -f docker-compose-fixed.yml down

# Test summary
print_step "All tests passed successfully!"
print_success "The E2E3D pipeline is properly set up and ready to use."
print_step "To run the pipeline, use: ./run_e2e3d_pipeline.sh /path/to/your/images"
print_step "To start the full environment including Airflow, use: ./start_pipeline.sh"

exit 0 