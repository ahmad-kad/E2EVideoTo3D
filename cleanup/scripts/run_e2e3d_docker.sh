#!/bin/bash
# run_e2e3d_docker.sh - Script to run the E2E3D system using Docker from start to end

set -e  # Exit on error

# Define color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}E2E3D: Full Docker Pipeline${NC}"
echo -e "${BLUE}======================================${NC}"

# Parse arguments
if [ "$#" -lt 1 ]; then
    echo -e "${RED}Error: Missing input directory${NC}"
    echo -e "Usage: $0 <input_directory> [output_directory]"
    echo -e "  <input_directory>: Path to directory with input images"
    echo -e "  [output_directory]: Optional path to output directory (default: ./output)"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_DIR="${2:-./output}"

# Get the absolute path for directories
INPUT_DIR=$(realpath "$INPUT_DIR")
OUTPUT_DIR=$(realpath "$OUTPUT_DIR")
IMAGE_SET_NAME=$(basename "$INPUT_DIR")
MESH_OUTPUT_DIR="$OUTPUT_DIR/$IMAGE_SET_NAME/mesh"

echo -e "${BLUE}Input directory: ${NC}$INPUT_DIR"
echo -e "${BLUE}Output directory: ${NC}$OUTPUT_DIR"
echo -e "${BLUE}Image set name: ${NC}$IMAGE_SET_NAME"

# Check if Docker is running
echo -e "${BLUE}Checking Docker service...${NC}"
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running.${NC}"
    echo -e "${YELLOW}Please start Docker and try again.${NC}"
    exit 1
fi

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"
mkdir -p "$MESH_OUTPUT_DIR"

# Step 1: Start MinIO service
echo -e "${BLUE}Starting MinIO service...${NC}"
docker-compose up -d minio
echo -e "${GREEN}MinIO started successfully!${NC}"

# Wait for MinIO to be ready
echo -e "${BLUE}Waiting for MinIO to be ready...${NC}"
sleep 5

# Step 2: Run the reconstruction in Docker using the latest image
echo -e "${BLUE}Running 3D reconstruction...${NC}"
docker run --rm \
    -v "$INPUT_DIR:/app/input" \
    -v "$OUTPUT_DIR:/app/output" \
    --name e2e3d-reconstruction-temp \
    -e COLMAP_PATH=/usr/local/bin/colmap \
    -e USE_GPU=auto \
    -e QUALITY_PRESET=medium \
    python:3.7-slim \
    bash -c "
    apt-get update && \
    apt-get install -y git wget python3-pip && \
    pip install tqdm numpy pillow open3d && \
    git clone https://github.com/yourusername/e2e3d.git && \
    cd e2e3d && \
    python3 reconstruct.py /app/input --output /app/output/$IMAGE_SET_NAME
    "

# Check if reconstruction was successful
if [ ! -f "$MESH_OUTPUT_DIR/reconstructed_mesh.obj" ]; then
    echo -e "${RED}Error: Reconstruction failed - mesh not found${NC}"
    exit 1
fi

echo -e "${GREEN}3D reconstruction completed successfully!${NC}"

# Step 3: Upload the mesh to MinIO
echo -e "${BLUE}Uploading mesh to MinIO...${NC}"
python upload_to_minio.py "$MESH_OUTPUT_DIR/reconstructed_mesh.obj" \
    --endpoint localhost:9000 \
    --bucket models \
    --access-key minioadmin \
    --secret-key minioadmin

echo -e "${GREEN}Mesh uploaded successfully!${NC}"
echo -e "${BLUE}Download URL: ${NC}http://localhost:9000/models/reconstructed_mesh.obj"

# Print summary
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}E2E3D Pipeline completed successfully!${NC}"
echo -e "${BLUE}Input: ${NC}$INPUT_DIR"
echo -e "${BLUE}Output: ${NC}$OUTPUT_DIR/$IMAGE_SET_NAME"
echo -e "${BLUE}Mesh file: ${NC}$MESH_OUTPUT_DIR/reconstructed_mesh.obj"
echo -e "${BLUE}Download URL: ${NC}http://localhost:9000/models/reconstructed_mesh.obj"
echo -e "${BLUE}======================================${NC}" 