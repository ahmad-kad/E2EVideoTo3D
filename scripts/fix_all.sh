#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}      E2E3D Complete Fix Script      ${NC}"
echo -e "${BLUE}======================================${NC}"

# Make all scripts executable
echo -e "${BLUE}Making helper scripts executable...${NC}"
chmod +x scripts/fix_docker_compose.sh
chmod +x scripts/fix_volumes.sh
chmod +x scripts/check_video_path.sh
chmod +x scripts/init_airflow.sh
chmod +x scripts/shutdown.sh

# Run docker-compose fix script
echo -e "\n${BLUE}Step 1: Fixing docker-compose.yml file...${NC}"
./scripts/fix_docker_compose.sh

# Ask user if they want to continue
echo -e "\n${YELLOW}Docker-compose.yml has been updated. Continue with applying changes?${NC}"
read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Process stopped. You can inspect the changes in docker-compose.yml${NC}"
    echo -e "To restore the original file: ${YELLOW}cp docker-compose.yml.backup docker-compose.yml${NC}"
    exit 1
fi

# Stop all containers
echo -e "\n${BLUE}Step 2: Stopping all containers...${NC}"
docker-compose down

# Run volume fix script
echo -e "\n${BLUE}Step 3: Setting up directories and permissions...${NC}"
./scripts/fix_volumes.sh

# Initialize Airflow
echo -e "\n${BLUE}Step 4: Initializing Airflow...${NC}"
./scripts/init_airflow.sh

# Run check script
echo -e "\n${BLUE}Step 5: Verifying video path...${NC}"
./scripts/check_video_path.sh

echo -e "\n${GREEN}All fixes have been applied!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "You should now be able to:"
echo -e "1. Access Airflow at ${BLUE}http://localhost:8080${NC}"
echo -e "   Username: ${BLUE}admin${NC}, Password: ${BLUE}admin${NC}"
echo -e "2. Access MinIO at ${BLUE}http://localhost:9001${NC}"
echo -e "   Username: ${BLUE}minioadmin${NC}, Password: ${BLUE}minioadmin${NC}"
echo -e "3. Process videos by placing them in the ${BLUE}data/videos${NC} directory"
echo -e "   and triggering the DAG in Airflow"
echo -e "\nIf you still encounter issues, you can run: ${YELLOW}./scripts/shutdown.sh${NC}"
echo -e "to shut down everything and start fresh." 