#!/bin/bash
# setup_directories.sh
# This script ensures all required directories exist with proper permissions for the E2E3D project

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
echo -e "${BLUE}E2E3D Directory Setup${NC}"
echo -e "${BLUE}======================================${NC}"

# Determine the base project directory
if [ -z "$PROJECT_DIR" ]; then
    # If not set, use current directory
    PROJECT_DIR=$(pwd)
    echo -e "${YELLOW}PROJECT_DIR not set, using current directory: ${PROJECT_DIR}${NC}"
else
    echo -e "${GREEN}Using PROJECT_DIR: ${PROJECT_DIR}${NC}"
fi

# Define all required directories
AIRFLOW_DIR="${PROJECT_DIR}/airflow"
DATA_DIR="${PROJECT_DIR}/data"
INPUT_DIR="${DATA_DIR}/input"
OUTPUT_DIR="${DATA_DIR}/output"
VIDEOS_DIR="${DATA_DIR}/videos"
LOGS_DIR="${PROJECT_DIR}/logs"
SCRIPTS_DIR="${PROJECT_DIR}/scripts"

# Create directories with proper permissions
create_directory() {
    local dir=$1
    if [ ! -d "$dir" ]; then
        echo -e "${YELLOW}Creating directory: $dir${NC}"
        mkdir -p "$dir"
        # Set permissions to allow airflow user to access
        chmod 777 "$dir"
    else
        echo -e "${GREEN}Directory already exists: $dir${NC}"
        # Ensure correct permissions
        chmod 777 "$dir"
    fi
}

# Create all required directories
echo -e "${BLUE}Creating required directories...${NC}"
create_directory "$AIRFLOW_DIR"
create_directory "$DATA_DIR"
create_directory "$INPUT_DIR"
create_directory "$OUTPUT_DIR"
create_directory "$VIDEOS_DIR"
create_directory "$LOGS_DIR"
create_directory "$SCRIPTS_DIR"
create_directory "$AIRFLOW_DIR/dags"

# Create symlinks for backward compatibility if needed
if [ ! -L "${PROJECT_DIR}/input" ] && [ ! -d "${PROJECT_DIR}/input" ]; then
    echo -e "${YELLOW}Creating symlink: ${PROJECT_DIR}/input -> ${INPUT_DIR}${NC}"
    ln -sf "$INPUT_DIR" "${PROJECT_DIR}/input"
fi

if [ ! -L "${PROJECT_DIR}/output" ] && [ ! -d "${PROJECT_DIR}/output" ]; then
    echo -e "${YELLOW}Creating symlink: ${PROJECT_DIR}/output -> ${OUTPUT_DIR}${NC}"
    ln -sf "$OUTPUT_DIR" "${PROJECT_DIR}/output"
fi

if [ ! -L "${PROJECT_DIR}/videos" ] && [ ! -d "${PROJECT_DIR}/videos" ]; then
    echo -e "${YELLOW}Creating symlink: ${PROJECT_DIR}/videos -> ${VIDEOS_DIR}${NC}"
    ln -sf "$VIDEOS_DIR" "${PROJECT_DIR}/videos"
fi

# Update docker-compose volume paths
if [ -f "${PROJECT_DIR}/docker-compose.yml" ]; then
    echo -e "${BLUE}Updating docker-compose.yml with correct volume paths...${NC}"
    
    # Backup the original docker-compose file
    cp "${PROJECT_DIR}/docker-compose.yml" "${PROJECT_DIR}/docker-compose.yml.bak"
    
    # Create a temporary file with updated paths
    # This is a simplified approach and may need adjustment for complex docker-compose files
    sed -i.bak "s|\\./data|${DATA_DIR}|g" "${PROJECT_DIR}/docker-compose.yml"
    
    echo -e "${GREEN}docker-compose.yml updated. Original backed up as docker-compose.yml.bak${NC}"
fi

# Create a .env file for environment variables
echo -e "${BLUE}Creating .env file with directory paths...${NC}"
cat > "${PROJECT_DIR}/.env" <<EOL
# E2E3D Environment Variables
PROJECT_DIR=${PROJECT_DIR}
DATA_DIR=${DATA_DIR}
INPUT_DIR=${INPUT_DIR}
OUTPUT_DIR=${OUTPUT_DIR}
VIDEOS_DIR=${VIDEOS_DIR}
LOGS_DIR=${LOGS_DIR}
EOL

echo -e "${GREEN}.env file created with directory paths${NC}"

# Summary
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Directory setup complete!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "Project root: ${PROJECT_DIR}"
echo -e "Data directory: ${DATA_DIR}"
echo -e "Input directory: ${INPUT_DIR}"
echo -e "Output directory: ${OUTPUT_DIR}"
echo -e "Videos directory: ${VIDEOS_DIR}"
echo -e "${BLUE}======================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Place your videos in: ${VIDEOS_DIR}"
echo -e "2. Start the system with: ./run.sh"
echo -e "3. Access Airflow UI at: http://localhost:8080"
echo -e "4. Access MinIO UI at: http://localhost:9001"
echo -e "${BLUE}======================================${NC}" 