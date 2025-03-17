#!/bin/bash
# test_docker.sh - Test script for Docker setup

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
echo -e "${BLUE}E2E3D: Docker Test Script${NC}"
echo -e "${BLUE}======================================${NC}"

# Set up base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_DIR="$SCRIPT_DIR"
cd "$PROJECT_DIR"

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

# Create essential directories
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p "$PROJECT_DIR/data/input"
mkdir -p "$PROJECT_DIR/data/output"
mkdir -p "$PROJECT_DIR/data/videos"

# Build and run the test container
echo -e "${BLUE}Building and running test container...${NC}"
$DOCKER_COMPOSE -f docker-compose.test.yml up --build

echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Docker test completed successfully!${NC}"
echo -e "${BLUE}======================================${NC}"

exit 0 