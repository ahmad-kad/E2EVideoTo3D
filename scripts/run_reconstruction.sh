#!/bin/bash
# Script to run reconstruction directly on an image set

# Define color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print help
function print_help {
    echo "Usage: $0 <image_set> [options]"
    echo ""
    echo "Arguments:"
    echo "  <image_set>               Name of the image set in data/input/"
    echo ""
    echo "Options:"
    echo "  --quality <quality>       Quality preset (low, medium, high)"
    echo "  --mesh-method <method>    Mesh generation method (open3d, poisson, delaunay)"
    echo "  --depth <depth>           Octree depth for Poisson reconstruction (default: 9)"
    echo "  --skip-colmap             Skip COLMAP reconstruction"
    echo "  --skip-mesh               Skip mesh generation"
    echo "  --help                    Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 CognacStJacquesDoor --quality high --mesh-method open3d"
    exit 1
}

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Image set name is required${NC}"
    print_help
fi

# Get the image set name
IMAGE_SET=$1
shift

# Prepare command arguments
ARGS="$IMAGE_SET"

# Parse optional arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --quality)
            QUALITY="$2"
            ARGS="$ARGS --quality $QUALITY"
            shift 2
            ;;
        --mesh-method)
            METHOD="$2"
            ARGS="$ARGS --mesh-method $METHOD"
            shift 2
            ;;
        --depth)
            DEPTH="$2"
            ARGS="$ARGS --depth $DEPTH"
            shift 2
            ;;
        --skip-colmap)
            ARGS="$ARGS --skip-colmap"
            shift
            ;;
        --skip-mesh)
            ARGS="$ARGS --skip-mesh"
            shift
            ;;
        --help)
            print_help
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            print_help
            ;;
    esac
done

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    exit 1
fi

# Print summary
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Running reconstruction on image set: ${GREEN}$IMAGE_SET${NC}"
echo -e "${BLUE}Command: ${GREEN}reconstruct.py $ARGS${NC}"
echo -e "${BLUE}======================================${NC}"

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    exit 1
fi

# Execute the reconstruction
echo -e "${BLUE}Starting reconstruction...${NC}"
$DOCKER_COMPOSE exec reconstruction python3 /app/reconstruct.py $ARGS

STATUS=$?
if [ $STATUS -eq 0 ]; then
    echo -e "${GREEN}Reconstruction completed successfully!${NC}"
    echo -e "${BLUE}Output saved to: ${GREEN}data/output/$IMAGE_SET${NC}"
else
    echo -e "${RED}Reconstruction failed with status $STATUS${NC}"
    echo -e "${YELLOW}Check the logs for details${NC}"
fi

exit $STATUS 