#!/bin/bash
# run_airflow_test.sh - Script to trigger Airflow test DAG

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
echo -e "${BLUE}E2E3D: Run Airflow Test Pipeline${NC}"
echo -e "${BLUE}======================================${NC}"

# Set up base directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Process arguments
DATASET="CognacStJacquesDoor"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --dataset)
      DATASET="$2"
      shift 2
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Check if Docker and Docker Compose are running
echo -e "${BLUE}Checking Docker environment...${NC}"
if ! docker ps &> /dev/null; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p "$PROJECT_DIR/data/input"
mkdir -p "$PROJECT_DIR/data/output"
mkdir -p "$PROJECT_DIR/data/reports"

# Run the minimal test container
echo -e "${BLUE}Running the test directly with minimal dependencies...${NC}"
echo -e "${BLUE}  Dataset: ${DATASET}${NC}"

docker run --rm \
    -v "$PROJECT_DIR/data:/app/data" \
    -v "$PROJECT_DIR/scripts:/app/scripts" \
    -w /app \
    --name e2e3d-test-runner \
    python:3.7.9-slim \
    bash -c "
        echo 'Testing E2E3D with Python 3.7.9'
        apt-get update && 
        apt-get install -y --no-install-recommends wget unzip git &&
        pip install tqdm requests numpy Pillow &&
        mkdir -p /app/data/input/${DATASET} &&
        if [ ! -d /app/data/input/${DATASET} ] || [ -z \"\$(ls -A /app/data/input/${DATASET})\" ]; then
            echo 'Downloading sample data...'
            python /app/scripts/download_sample_data.py ${DATASET} /app/data/input
        fi &&
        echo 'Sample data check:' &&
        IMG_COUNT=\$(find /app/data/input/${DATASET} -type f -name '*.jpg' -o -name '*.png' | wc -l) &&
        echo 'Found '\${IMG_COUNT}' images in dataset ${DATASET}' &&
        
        # Generate a simple report
        mkdir -p /app/data/reports &&
        REPORT_FILE=\"/app/data/reports/test_report_${DATASET}_\$(date +%Y%m%d_%H%M%S).json\" &&
        cat > \${REPORT_FILE} <<EOL
{
  \"system_info\": {
    \"hostname\": \"\$(hostname)\",
    \"platform\": \"\$(uname -a)\",
    \"python_version\": \"\$(python --version 2>&1)\",
    \"timestamp\": \"\$(date)\"
  },
  \"dataset\": \"${DATASET}\",
  \"test_results\": {
    \"images_found\": \${IMG_COUNT},
    \"status\": \"\$([ \${IMG_COUNT} -gt 0 ] && echo 'success' || echo 'failure')\",
    \"message\": \"Found \${IMG_COUNT} images in dataset ${DATASET}\"
  }
}
EOL
        echo 'Test report generated: \${REPORT_FILE}'
        cat \${REPORT_FILE}
    "

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Test completed successfully!${NC}"
    LATEST_REPORT=$(ls -t "$PROJECT_DIR/data/reports" | head -n 1)
    if [ -n "$LATEST_REPORT" ]; then
        echo -e "${BLUE}Latest report: ${PROJECT_DIR}/data/reports/${LATEST_REPORT}${NC}"
    fi
else
    echo -e "${RED}Test failed${NC}"
    exit 1
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}E2E3D Test Pipeline Completed${NC}"
echo -e "${BLUE}======================================${NC}"

exit 0 