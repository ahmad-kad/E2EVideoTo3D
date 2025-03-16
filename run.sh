#!/bin/bash
# run.sh
# Main script to set up and run the E2E3D system

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

# Run the directory setup script
echo -e "${BLUE}Setting up directories...${NC}"
if [ -f "$PROJECT_DIR/scripts/setup_directories.sh" ]; then
    bash "$PROJECT_DIR/scripts/setup_directories.sh"
    
    # Source environment variables
    if [ -f "$PROJECT_DIR/.env" ]; then
        source "$PROJECT_DIR/.env"
        echo -e "${GREEN}Loaded environment variables from .env file${NC}"
    fi
else
    echo -e "${RED}Error: setup_directories.sh not found${NC}"
    echo -e "${YELLOW}Creating essential directories manually...${NC}"
    mkdir -p "$PROJECT_DIR/data/input"
    mkdir -p "$PROJECT_DIR/data/output"
    mkdir -p "$PROJECT_DIR/data/videos"
    mkdir -p "$PROJECT_DIR/airflow/dags"
    
    # Set environment variables manually
    export DATA_DIR="$PROJECT_DIR/data"
    export INPUT_DIR="$DATA_DIR/input"
    export OUTPUT_DIR="$DATA_DIR/output"
    export VIDEOS_DIR="$DATA_DIR/videos"
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
if ! command -v docker-compose &> /dev/null && ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    echo -e "${YELLOW}Please install docker-compose or use Docker Desktop which includes it${NC}"
    exit 1
fi

# Check if docker compose is separate command or subcommand
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

# Fix Docker services if needed
if [ -f "$PROJECT_DIR/scripts/fix_docker_services.sh" ]; then
    echo -e "${BLUE}Fixing Docker services configuration...${NC}"
    bash "$PROJECT_DIR/scripts/fix_docker_services.sh"
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

# Copy DAG file if it doesn't exist
if [ ! -f "$PROJECT_DIR/airflow/dags/reconstruction_pipeline.py" ]; then
    echo -e "${BLUE}Copying reconstruction pipeline DAG...${NC}"
    cp "$PROJECT_DIR/airflow/dags/reconstruction_pipeline.py.template" "$PROJECT_DIR/airflow/dags/reconstruction_pipeline.py" 2>/dev/null || true
fi

# Display available videos
echo -e "${BLUE}Available videos:${NC}"
find "$VIDEOS_DIR" -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.avi" \) | while read -r video; do
    echo "  - $(basename "$video")"
done

# Instructions for the user
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}E2E3D system is now running!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "You can access the following services:"
echo -e "  - Airflow UI: http://localhost:8080 (username: admin, password: admin)"
echo -e "  - MinIO UI: http://localhost:9001 (username: minioadmin, password: minioadmin)"
echo -e "  - Spark Master UI: http://localhost:8082"
echo -e "${BLUE}======================================${NC}"
echo -e "${YELLOW}Processing options:${NC}"
echo -e "1. Process a video to images:"
echo -e "   ./scripts/extract_video.sh -v <video_path> [-f <fps>]"
echo -e "   Example: ./scripts/extract_video.sh -v my_video.mp4 -f 2"
echo -e ""
echo -e "2. Process images directly through Airflow:"
echo -e "   - Access Airflow UI at http://localhost:8080"
echo -e "   - Login with username 'admin' and password 'admin'"
echo -e "   - Find and trigger the 'reconstruction_pipeline' DAG"
echo -e "${BLUE}======================================${NC}"

# Troubleshooting hint
echo -e "${YELLOW}If you have trouble accessing the Airflow UI, try:${NC}"
echo -e "./scripts/troubleshoot_airflow.sh"
echo -e "${BLUE}======================================${NC}"

exit 0 