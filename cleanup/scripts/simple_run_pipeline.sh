#!/bin/bash

# Simple E2E3D Pipeline Script
# This script provides a simplified approach to running the 3D reconstruction pipeline

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

# Get input and output directories
if [ -z "$1" ]; then
  print_error "Please provide an input directory containing images"
  echo "Usage: $0 <input_dir> [output_dir]"
  exit 1
fi

INPUT_DIR=$(realpath "$1")
OUTPUT_DIR=$(realpath "${2:-./output}")

# Check if input directory exists and has images
if [ ! -d "$INPUT_DIR" ]; then
  print_error "Input directory does not exist: $INPUT_DIR"
  exit 1
fi

IMAGE_COUNT=$(find "$INPUT_DIR" -type f \( -name "*.jpg" -o -name "*.png" -o -name "*.jpeg" \) | wc -l)
if [ "$IMAGE_COUNT" -eq 0 ]; then
  print_error "No images found in input directory: $INPUT_DIR"
  exit 1
fi

print_step "Found $IMAGE_COUNT images in $INPUT_DIR"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"
print_step "Output directory: $OUTPUT_DIR"

# Check if MinIO is running, if not, start it
if ! curl -s http://localhost:9000/minio/health/live > /dev/null; then
  print_step "MinIO is not running. Starting it now..."
  if ! docker-compose -f docker-compose-minimal-test.yml up -d; then
    print_error "Failed to start MinIO."
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
      docker-compose -f docker-compose-minimal-test.yml down
      exit 1
    fi
    echo -n "."
    sleep 1
  done
  echo ""
  print_success "MinIO service is ready"
fi

# Check if we should run locally or with Docker
if [ "$USE_DOCKER" = "false" ]; then
  # Run locally if Python environment is set up
  print_step "Running reconstruction process locally..."
  
  # Check if Python and required packages are installed
  if ! which python3 > /dev/null; then
    print_error "Python3 not found. Please install Python or use Docker mode."
    print_step "Set USE_DOCKER=true and run this script again."
    exit 1
  fi
  
  # Run the reconstruction process
  print_step "Starting local reconstruction..."
  if ! python3 reconstruct.py "$INPUT_DIR" "$OUTPUT_DIR"; then
    print_error "Reconstruction process failed"
    exit 1
  fi
  
  # Upload the mesh to MinIO
  print_step "Uploading mesh to MinIO..."
  MESH_FILE="$OUTPUT_DIR/mesh/reconstructed_mesh.obj"
  if [ -f "$MESH_FILE" ]; then
    if ! python3 upload_mesh_to_minio.py "$MESH_FILE"; then
      print_warning "Failed to upload mesh to MinIO"
    else
      print_success "Mesh uploaded to MinIO"
    fi
  else
    print_error "Mesh file not found at $MESH_FILE"
    exit 1
  fi
else
  # Try to use existing e2e3d-reconstruction image if available
  if docker image inspect e2e3d-reconstruction:latest > /dev/null 2>&1; then
    print_step "Using existing e2e3d-reconstruction Docker image..."
    
    # Run the 3D reconstruction process in a Docker container
    print_step "Starting 3D reconstruction process..."
    docker run --rm \
      --name e2e3d-reconstruction-run \
      --network host \
      -v "$INPUT_DIR:/app/data/input/FrameSequence" \
      -v "$OUTPUT_DIR:/app/data/output/FrameSequence" \
      -v "$(pwd)/upload_mesh_to_minio.py:/app/upload_mesh_to_minio.py" \
      -e S3_ENABLED=true \
      -e S3_ENDPOINT=http://localhost:9000 \
      -e S3_BUCKET=models \
      -e S3_ACCESS_KEY=minioadmin \
      -e S3_SECRET_KEY=minioadmin \
      e2e3d-reconstruction:latest \
      bash -c "
        echo 'Starting 3D reconstruction pipeline...'
        mkdir -p /app/data/output
        
        # Set quality preset
        QUALITY_PRESET=\${QUALITY_PRESET:-medium}
        echo \"Using quality preset: \$QUALITY_PRESET\"
        
        # Run the reconstruction process
        python /app/reconstruct.py /app/data/input/FrameSequence /app/data/output/FrameSequence --quality \$QUALITY_PRESET
        
        # Install MinIO client and upload the mesh
        pip install minio
        chmod +x /app/upload_mesh_to_minio.py
        
        # Check if mesh file exists
        MESH_FILE=/app/data/output/FrameSequence/mesh/reconstructed_mesh.obj
        if [ -f \"\$MESH_FILE\" ]; then
          echo 'Mesh file found, uploading to MinIO...'
          python /app/upload_mesh_to_minio.py \"\$MESH_FILE\" --endpoint localhost:9000
          echo 'Mesh upload completed'
        else
          echo 'Mesh file not found at '\$MESH_FILE
          exit 1
        fi
      "
  else
    print_warning "e2e3d-reconstruction Docker image not found"
    print_step "Using Python locally with Docker for MinIO only..."
    
    # Run locally
    if ! which python3 > /dev/null; then
      print_error "Python3 not found. Please install Python or build the Docker image."
      exit 1
    fi
    
    # Run the reconstruction process
    print_step "Starting local reconstruction..."
    if ! python3 reconstruct.py "$INPUT_DIR" "$OUTPUT_DIR"; then
      print_error "Reconstruction process failed"
      exit 1
    fi
    
    # Upload the mesh to MinIO
    print_step "Uploading mesh to MinIO..."
    MESH_FILE="$OUTPUT_DIR/mesh/reconstructed_mesh.obj"
    if [ -f "$MESH_FILE" ]; then
      if ! python3 upload_mesh_to_minio.py "$MESH_FILE"; then
        print_warning "Failed to upload mesh to MinIO"
      else
        print_success "Mesh uploaded to MinIO"
      fi
    else
      print_error "Mesh file not found at $MESH_FILE"
      exit 1
    fi
  fi
fi

# Check if reconstruction was successful
if [ $? -ne 0 ]; then
  print_error "Reconstruction process failed"
  exit 1
fi

# Confirm success and provide output information
print_success "3D reconstruction completed successfully!"
print_step "Checking for mesh file..."
MESH_FILE="$OUTPUT_DIR/mesh/reconstructed_mesh.obj"
if [ -f "$MESH_FILE" ]; then
  print_success "Mesh file created: $MESH_FILE"
  print_step "File size: $(du -h "$MESH_FILE" | cut -f1)"
  print_step "Download URL: http://localhost:9000/models/reconstructed_mesh.obj"
else
  print_warning "Mesh file not found at expected location: $MESH_FILE"
  print_step "Check MinIO console at http://localhost:9001 for uploaded files"
fi

print_step "MinIO web console: http://localhost:9001 (login with minioadmin/minioadmin)"
print_step "Input directory: $INPUT_DIR"
print_step "Output directory: $OUTPUT_DIR"

# Ask if the user wants to stop MinIO service
read -p "Do you want to stop MinIO service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  print_step "Stopping MinIO service..."
  docker-compose -f docker-compose-minimal-test.yml down
else
  print_step "MinIO service is still running to allow access to the files"
  print_step "To stop services: docker-compose -f docker-compose-minimal-test.yml down"
fi

exit 0 