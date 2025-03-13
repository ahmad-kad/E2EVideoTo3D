#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  E2E3D Volume Mounting Fix Script   ${NC}"
echo -e "${BLUE}======================================${NC}"

# Create essential directories
echo -e "\n${BLUE}Creating required directories...${NC}"
mkdir -p data/videos
mkdir -p data/input
mkdir -p data/output
mkdir -p airflow/logs
mkdir -p airflow/dags
mkdir -p airflow/plugins

# Set proper permissions
echo -e "\n${BLUE}Setting proper permissions...${NC}"
chmod -R 755 data
chmod -R 755 airflow

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml file not found in current directory!${NC}"
    echo "Please run this script from the root directory of your project."
    exit 1
fi

# Check if volumes are properly configured in docker-compose.yml
echo -e "\n${BLUE}Checking docker-compose.yml for volume configurations...${NC}"

# Check for airflow volume configurations
AIRFLOW_VOLUMES=$(grep -A 30 "airflow" docker-compose.yml | grep -c "volumes:")
if [ "$AIRFLOW_VOLUMES" -eq 0 ]; then
    echo -e "${YELLOW}Warning: No volumes section found for Airflow in docker-compose.yml${NC}"
    echo -e "You may need to manually update docker-compose.yml to include volume mappings."
    echo -e "Example volume configuration to add under airflow services:"
    echo -e "    volumes:"
    echo -e "      - ./data:/opt/airflow/data"
    echo -e "      - ./airflow/dags:/opt/airflow/dags"
    echo -e "      - ./airflow/logs:/opt/airflow/logs"
    echo -e "      - ./airflow/plugins:/opt/airflow/plugins"
else
    echo -e "${GREEN}Airflow volume configurations found.${NC}"
fi

# Create a test file to verify mounting
echo -e "\n${BLUE}Creating test files to verify volume mounting...${NC}"
echo "This is a test file to verify volume mounting" > data/test_file.txt
echo "This is a test file to verify volume mounting" > airflow/dags/test_file.txt

# Restart containers
echo -e "\n${BLUE}Stopping containers...${NC}"
docker-compose down

echo -e "\n${BLUE}Starting containers...${NC}"
docker-compose up -d

# Wait for containers to start
echo -e "\n${BLUE}Waiting for containers to start...${NC}"
sleep 10

# Check if the Airflow container is running
if docker ps | grep -q "airflow-webserver"; then
    echo -e "\n${GREEN}Airflow container is running.${NC}"
    
    # Check if test files are visible in containers
    echo -e "\n${BLUE}Checking if volumes are properly mounted...${NC}"
    
    # Check data volume
    if docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') ls -la /opt/airflow/data 2>/dev/null | grep -q "test_file.txt"; then
        echo -e "${GREEN}Success: data volume is properly mounted in Airflow container.${NC}"
        # Remove test file
        docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') rm /opt/airflow/data/test_file.txt
    else
        echo -e "${RED}Error: data volume is NOT properly mounted in Airflow container.${NC}"
        echo -e "Manual docker-compose.yml update required. Please check the volume mappings."
    fi
    
    # Check dags volume
    if docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') ls -la /opt/airflow/dags 2>/dev/null | grep -q "test_file.txt"; then
        echo -e "${GREEN}Success: dags volume is properly mounted in Airflow container.${NC}"
        # Remove test file
        docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') rm /opt/airflow/dags/test_file.txt
    else
        echo -e "${RED}Error: dags volume is NOT properly mounted in Airflow container.${NC}"
        echo -e "Manual docker-compose.yml update required. Please check the volume mappings."
    fi
    
    # Check for MinIO container
    if docker ps | grep -q "minio"; then
        echo -e "\n${GREEN}MinIO container is running.${NC}"
        echo -e "MinIO should be accessible at: ${BLUE}http://localhost:9001${NC}"
        echo -e "Login with username: ${BLUE}minioadmin${NC} and password: ${BLUE}minioadmin${NC}"
    else
        echo -e "\n${RED}MinIO container is not running.${NC}"
        echo -e "Check docker-compose logs for errors: ${YELLOW}docker-compose logs minio${NC}"
    fi
    
    # Create a video directory inside the container if it doesn't exist
    echo -e "\n${BLUE}Ensuring /opt/airflow/data/videos exists inside container...${NC}"
    docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') mkdir -p /opt/airflow/data/videos
    
    # Try to copy any video files to the correct location
    if ls data/videos/*.mp4 >/dev/null 2>&1 || ls data/videos/*.mov >/dev/null 2>&1 || ls data/videos/*.avi >/dev/null 2>&1; then
        echo -e "${GREEN}Found video files in data/videos directory.${NC}"
        
        # Copy them to container if needed
        if ! docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') ls -la /opt/airflow/data/videos 2>/dev/null | grep -q ".mp4\|.mov\|.avi"; then
            echo -e "${YELLOW}No video files found in container. Copying from host...${NC}"
            for video in data/videos/*; do
                if [[ $video == *.mp4 || $video == *.mov || $video == *.avi ]]; then
                    video_name=$(basename "$video")
                    docker cp "$video" $(docker ps | grep airflow-webserver | awk '{print $1}'):/opt/airflow/data/videos/
                    echo -e "${GREEN}Copied $video_name to container.${NC}"
                fi
            done
        fi
    else
        echo -e "${YELLOW}No video files found in data/videos directory.${NC}"
        echo -e "Please add video files to the ${BLUE}data/videos${NC} directory."
        
        # Create a sample mount point to verify it works
        docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') touch /opt/airflow/data/videos/place_videos_here
    fi
    
else
    echo -e "\n${RED}Error: Airflow container is not running.${NC}"
    echo -e "Check docker-compose logs for errors: ${YELLOW}docker-compose logs airflow-webserver${NC}"
fi

# Clean up test files
rm -f data/test_file.txt
rm -f airflow/dags/test_file.txt

echo -e "\n${BLUE}======================================${NC}"
echo -e "${GREEN}Fix process completed!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "If volumes are still not mounting correctly, you may need to:"
echo -e "1. Check your ${YELLOW}docker-compose.yml${NC} file for proper volume configurations"
echo -e "2. Restart Docker completely (not just the containers)"
echo -e "3. Run ${YELLOW}docker system prune${NC} to clean up any stale Docker resources"
echo -e "\nTo verify video path is now working, run: ${YELLOW}./scripts/check_video_path.sh${NC}"
echo -e "\nTo access MinIO: ${BLUE}http://localhost:9001${NC}"
echo -e "Login with username: ${BLUE}minioadmin${NC} and password: ${BLUE}minioadmin${NC}"
echo -e "\nTo access Airflow: ${BLUE}http://localhost:8080${NC}"
echo -e "Login with username: ${BLUE}admin${NC} and password: ${BLUE}admin${NC}" 