#!/bin/bash
# run_minimal_test.sh - Simple script to test E2E3D with minimal dependencies

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
echo -e "${BLUE}E2E3D: Run Minimal Test${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if Docker is running
echo -e "${BLUE}Checking Docker environment...${NC}"
if ! docker ps &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    exit 1
fi

# Check if docker-compose is installed
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p ./data/input
mkdir -p ./data/output

# Run the minimal test
echo -e "${BLUE}Running minimal test...${NC}"
$DOCKER_COMPOSE -f docker-compose-minimal.yml up --force-recreate

echo -e "${GREEN}Test complete!${NC}"
exit 0 