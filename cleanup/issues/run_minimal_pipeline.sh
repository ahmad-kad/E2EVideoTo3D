#!/bin/bash

# Color variables for output formatting
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions for formatted output
print_success() {
    echo -e "${GREEN}[E2E3D Minimal] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[E2E3D Minimal] $1${NC}"
}

print_error() {
    echo -e "${RED}[E2E3D Minimal] $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create necessary directories
print_success "Creating data directories..."
mkdir -p data/input data/output airflow/logs

# Setup necessary scripts
print_success "Setting up necessary scripts..."
# Copy the Airflow reconstruct script for use in the container, renaming it to match what the container expects
cp issues/reconstruct.py issues/standalone_reconstruct.py
cp issues/upload_to_minio.py upload_to_minio.py.minimal

# Stop any running containers
print_warning "Stopping any running containers..."
docker-compose -f issues/docker-compose-minimal.yml down -v 2>/dev/null || true

# Build the minimal image
print_success "Building base image..."
if ! docker build -t e2e3d-base-minimal:latest -f issues/Dockerfile.minimal .; then
    print_error "Failed to build Docker image. See error above."
    exit 1
fi

# Create docker-compose file for the minimal setup
print_success "Creating minimal docker-compose file..."
cat > issues/docker-compose-minimal.yml << 'EOF'
version: '3.8'

services:
  minio:
    image: minio/minio
    container_name: e2e3d-minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-volume:/data
    networks:
      - e2e3d-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    
  minio-setup:
    image: minio/mc
    container_name: e2e3d-minio-setup
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      /usr/bin/mc config host add myminio http://minio:9000 minioadmin minioadmin;
      /usr/bin/mc mb -p myminio/models;
      /usr/bin/mc anonymous set download myminio/models;
      exit 0;
      "
    networks:
      - e2e3d-network

networks:
  e2e3d-network:
    name: issues_e2e3d-network

volumes:
  minio-volume:
    name: issues_minio-volume
EOF

# Start the services
print_success "Starting minimal E2E3D services..."
if ! docker-compose -f issues/docker-compose-minimal.yml up -d; then
    print_error "Failed to start services. See error above."
    exit 1
fi

print_success "Waiting for services to initialize..."
sleep 5

# Run the reconstruction container manually instead of as a service
print_success "Running reconstruction process..."
docker run --rm --name e2e3d-reconstruction \
  --network issues_e2e3d-network \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/issues/standalone_reconstruct.py:/app/reconstruct.py" \
  -v "$(pwd)/upload_to_minio.py.minimal:/app/upload_to_minio.py" \
  e2e3d-base-minimal:latest \
  /bin/bash -c "
    echo 'Initializing environment...'
    echo 'Running on platform: '$(uname -sm)
    
    # Create mock input data
    mkdir -p /app/data/input/images
    for i in {1..5}; do
      echo 'Test image '$i > /app/data/input/images/img_\$i.txt
    done
    
    echo 'Starting reconstruction process...'
    python3 /app/reconstruct.py /app/data/input/images --output /app/data/output/FrameSequence --quality medium
    
    echo 'Uploading reconstructed mesh to MinIO...'
    python3 /app/upload_to_minio.py /app/data/output/FrameSequence/mesh/reconstructed_mesh.obj --endpoint minio:9000 --access-key minioadmin --secret-key minioadmin
  "

print_success "Access MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
print_success "To check the output files, navigate to MinIO console and browse the 'models' bucket."
print_success "Reconstructed mesh URL: http://localhost:9000/models/reconstructed_mesh.obj" 