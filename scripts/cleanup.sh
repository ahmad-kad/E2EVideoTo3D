#!/bin/bash
# cleanup.sh - Script to clean up Docker resources

# Define color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}E2E3D: Docker Cleanup Script${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    exit 1
fi

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    exit 1
fi

# Stop running containers
echo -e "${BLUE}Stopping running containers...${NC}"
$DOCKER_COMPOSE down

# Remove dangling images
echo -e "${BLUE}Removing dangling images...${NC}"
docker image prune -f

# Remove unused volumes
echo -e "${BLUE}Removing unused volumes...${NC}"
docker volume prune -f

# Remove unused networks
echo -e "${BLUE}Removing unused networks...${NC}"
docker network prune -f

# List remaining containers
echo -e "${BLUE}Remaining containers:${NC}"
docker ps -a

# List remaining images
echo -e "${BLUE}Remaining images:${NC}"
docker images | grep "e2e3d"

echo -e "${GREEN}Cleanup complete!${NC}"
exit 0 