#!/bin/bash
# run.sh - Main script to set up and run the E2E3D system

# Enable error handling
set -e

# Define color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}E2E3D: End-to-End 3D Reconstruction${NC}"
echo -e "${BLUE}======================================${NC}"

# Set up base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_DIR="$SCRIPT_DIR"
cd "$PROJECT_DIR"

# Make scripts executable
echo -e "${BLUE}Making scripts executable...${NC}"
chmod +x docker/scripts/*.sh 2>/dev/null || echo -e "${YELLOW}No scripts to make executable or permission denied${NC}"
chmod +x scripts/*.sh 2>/dev/null || echo -e "${YELLOW}No scripts to make executable or permission denied${NC}"

# Create essential directories
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p "$PROJECT_DIR/data/input"
mkdir -p "$PROJECT_DIR/data/output"
mkdir -p "$PROJECT_DIR/data/videos"
mkdir -p "$PROJECT_DIR/airflow/dags"
mkdir -p "$PROJECT_DIR/airflow/logs"
mkdir -p "$PROJECT_DIR/airflow/plugins"

# Set environment variables
export DATA_DIR="$PROJECT_DIR/data"
export INPUT_DIR="$DATA_DIR/input"
export OUTPUT_DIR="$DATA_DIR/output"
export VIDEOS_DIR="$DATA_DIR/videos"

# Create or source .env file
if [ -f "$PROJECT_DIR/.env" ]; then
    echo -e "${GREEN}Loading environment from .env file${NC}"
    set -a
    source "$PROJECT_DIR/.env"
    set +a
else
    echo -e "${YELLOW}Creating .env file with default settings${NC}"
    cat > "$PROJECT_DIR/.env" << EOF
DATA_DIR=./data
DOCKER_PLATFORM=linux/arm64
USE_GPU=auto
QUALITY_PRESET=medium
S3_ENABLED=true
S3_ENDPOINT=http://minio:9000
S3_BUCKET=models
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
EOF
fi

# Check if Docker is installed
echo -e "${BLUE}Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo -e "${YELLOW}Please install Docker Desktop from https://www.docker.com/products/docker-desktop/${NC}"
    exit 1
fi

# Check if Docker is running
echo -e "${BLUE}Checking if Docker is running...${NC}"
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    exit 1
fi

# Check if docker-compose is installed
echo -e "${BLUE}Checking docker-compose installation...${NC}"
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    echo -e "${YELLOW}Please install docker-compose or use Docker Desktop which includes it${NC}"
    exit 1
fi

# Force rebuild if requested or not previously installed
FORCE_REBUILD=0
if [ "$1" == "build" ] || [ "$1" == "--build" ] || [ "$1" == "-b" ]; then
    echo -e "${BLUE}Force rebuild requested${NC}"
    FORCE_REBUILD=1
fi

if [ $FORCE_REBUILD -eq 1 ] || [ ! -f "$PROJECT_DIR/.e2e3d_installed" ]; then
    echo -e "${BLUE}Building Docker images...${NC}"
    
    # Build the base image first
    echo -e "${BLUE}Building base image...${NC}"
    docker build -t e2e3d-base:latest -f docker/base/Dockerfile .
    BASE_STATUS=$?
    
    if [ $BASE_STATUS -ne 0 ]; then
        echo -e "${RED}Error building base image. See logs above for details.${NC}"
        exit 1
    fi
    
    # Build the COLMAP image
    echo -e "${BLUE}Building COLMAP image...${NC}"
    docker build -t e2e3d-colmap:latest -f docker/colmap/Dockerfile .
    COLMAP_STATUS=$?
    
    if [ $COLMAP_STATUS -ne 0 ]; then
        echo -e "${RED}Error building COLMAP image. See logs above for details.${NC}"
        exit 1
    fi
    
    # Build the Airflow image
    echo -e "${BLUE}Building Airflow image...${NC}"
    docker build -t e2e3d-airflow:latest -f docker/airflow/Dockerfile .
    AIRFLOW_STATUS=$?
    
    if [ $AIRFLOW_STATUS -ne 0 ]; then
        echo -e "${RED}Error building Airflow image. See logs above for details.${NC}"
        exit 1
    fi
    
    touch "$PROJECT_DIR/.e2e3d_installed"
else
    echo -e "${BLUE}Using existing Docker images. Use 'run.sh build' to rebuild.${NC}"
fi

# Start Docker services
echo -e "${BLUE}Starting Docker services...${NC}"
$DOCKER_COMPOSE up -d

# Wait for services to start
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 10

# Check if Airflow webserver is running
echo -e "${BLUE}Checking Airflow webserver...${NC}"
RETRY_COUNT=0
MAX_RETRIES=5

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8080 -o /dev/null; then
        echo -e "${GREEN}Airflow webserver is running!${NC}"
        break
    else
        echo -e "${YELLOW}Airflow webserver not ready yet. Retrying in 5 seconds... (${RETRY_COUNT}/${MAX_RETRIES})${NC}"
        sleep 5
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}Error: Airflow webserver did not start successfully${NC}"
    echo -e "${YELLOW}Checking Docker container logs for issues...${NC}"
    $DOCKER_COMPOSE logs airflow-webserver | tail -n 20
    
    # Try to restart the webserver
    echo -e "${YELLOW}Attempting to restart the Airflow webserver...${NC}"
    $DOCKER_COMPOSE restart airflow-webserver
    sleep 10
fi

# Check if MinIO is running
echo -e "${BLUE}Checking MinIO service...${NC}"
if curl -s http://localhost:9001 -o /dev/null; then
    echo -e "${GREEN}MinIO is running!${NC}"
else
    echo -e "${YELLOW}MinIO may not be running properly. Checking logs...${NC}"
    $DOCKER_COMPOSE logs minio | tail -n 20
fi

# Display available videos
echo -e "${BLUE}Available videos:${NC}"
find "$VIDEOS_DIR" -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.avi" \) | while read -r video; do
    echo "  - $(basename "$video")"
done

# Display available image sets
echo -e "${BLUE}Available image sets:${NC}"
find "$INPUT_DIR" -maxdepth 1 -type d | grep -v "^\.$" | while read -r dir; do
    if [ "$dir" != "$INPUT_DIR" ]; then
        count=$(find "$dir" -type f \( -name "*.jpg" -o -name "*.png" \) | wc -l)
        echo "  - $(basename "$dir") ($count images)"
    fi
done

# Instructions for the user
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}E2E3D system is now running!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "You can access the following services:"
echo -e "  - Airflow UI: http://localhost:8080 (username: admin, password: admin)"
echo -e "  - MinIO UI: http://localhost:9001 (username: minioadmin, password: minioadmin)"
echo -e "${BLUE}======================================${NC}"
echo -e "${YELLOW}Processing options:${NC}"
echo -e "1. Run direct reconstruction on image set:"
echo -e "   docker compose exec reconstruction python3 /app/reconstruct.py [IMAGESET_NAME]"
echo -e ""
echo -e "2. Process images through Airflow:"
echo -e "   - Access Airflow UI at http://localhost:8080"
echo -e "   - Login with username 'admin' and password 'admin'"
echo -e "   - Find and trigger the 'reconstruction_pipeline' DAG"
echo -e "${BLUE}======================================${NC}"

exit 0 