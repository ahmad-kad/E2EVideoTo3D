#!/bin/bash
# Setup script for the Airflow 3D reconstruction pipeline

set -e  # Exit on any error

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print with colors
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the base directory (where this script is located)
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
info "Base directory: $BASE_DIR"

# Create necessary directories
create_directories() {
    info "Creating directory structure..."
    mkdir -p "$BASE_DIR/data/input"
    mkdir -p "$BASE_DIR/data/output"
    mkdir -p "$BASE_DIR/data/videos"
    mkdir -p "$BASE_DIR/data/output/colmap_workspace"
    mkdir -p "$BASE_DIR/data/output/models"
    info "Directory structure created."
}

# Check if Docker and Docker Compose are installed
check_docker() {
    info "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    info "Checking Docker Compose installation..."
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    info "Docker and Docker Compose are installed."
}

# Check if COLMAP is installed
check_colmap() {
    info "Checking COLMAP installation..."
    if command -v colmap &> /dev/null; then
        COLMAP_PATH=$(which colmap)
        info "COLMAP is installed at: $COLMAP_PATH"
    else
        warn "COLMAP is not installed. The pipeline will run in test mode."
        
        # On macOS, offer to install COLMAP
        if [ "$(uname)" == "Darwin" ]; then
            if command -v brew &> /dev/null; then
                read -p "Would you like to install COLMAP using Homebrew? (y/n) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    info "Installing COLMAP using Homebrew..."
                    brew install colmap
                    if [ $? -eq 0 ]; then
                        COLMAP_PATH=$(which colmap)
                        info "COLMAP installed successfully at: $COLMAP_PATH"
                    else
                        error "COLMAP installation failed."
                    fi
                fi
            else
                warn "Homebrew is not installed. Please install COLMAP manually."
            fi
        elif [ "$(uname)" == "Linux" ]; then
            warn "To install COLMAP on Linux, you can use: sudo apt-get install colmap"
        fi
    fi
}

# Check for OpenCV installation
check_opencv() {
    info "Checking OpenCV installation in Docker container..."
    docker-compose exec -T airflow-scheduler python -c "import cv2; print('OpenCV version:', cv2.__version__)" 2>/dev/null || {
        warn "OpenCV is not installed in the Docker container. Installing now..."
        docker-compose exec -T airflow-scheduler python -m pip install opencv-python-headless
        if [ $? -eq 0 ]; then
            info "OpenCV installed successfully in the Docker container."
        else
            error "Failed to install OpenCV in the Docker container."
        fi
    }
}

# Configure environment variables
configure_environment() {
    info "Configuring environment variables..."
    
    # Create or update .env file
    ENV_FILE="$BASE_DIR/.env"
    touch "$ENV_FILE"
    
    # Set PROJECT_PATH
    grep -q "PROJECT_PATH=" "$ENV_FILE" || echo "PROJECT_PATH=$BASE_DIR/data" >> "$ENV_FILE"
    
    # Set COLMAP_PATH if found
    if [ ! -z "$COLMAP_PATH" ]; then
        grep -q "COLMAP_PATH=" "$ENV_FILE" && sed -i.bak "s|COLMAP_PATH=.*|COLMAP_PATH=$COLMAP_PATH|" "$ENV_FILE" || echo "COLMAP_PATH=$COLMAP_PATH" >> "$ENV_FILE"
    fi
    
    # Set test mode if COLMAP is not found
    if [ -z "$COLMAP_PATH" ]; then
        grep -q "AIRFLOW_TEST_MODE=" "$ENV_FILE" && sed -i.bak "s|AIRFLOW_TEST_MODE=.*|AIRFLOW_TEST_MODE=true|" "$ENV_FILE" || echo "AIRFLOW_TEST_MODE=true" >> "$ENV_FILE"
    fi
    
    # Other environment variables
    grep -q "INPUT_PATH=" "$ENV_FILE" || echo "INPUT_PATH=$BASE_DIR/data/input" >> "$ENV_FILE"
    grep -q "OUTPUT_PATH=" "$ENV_FILE" || echo "OUTPUT_PATH=$BASE_DIR/data/output" >> "$ENV_FILE"
    grep -q "VIDEO_PATH=" "$ENV_FILE" || echo "VIDEO_PATH=$BASE_DIR/data/videos" >> "$ENV_FILE"
    
    info "Environment variables configured in $ENV_FILE"
}

# Restart Airflow services
restart_airflow() {
    info "Restarting Airflow services..."
    
    # Check if Airflow is running
    if docker-compose ps | grep -q "airflow"; then
        docker-compose restart airflow-scheduler airflow-webserver
        info "Airflow services restarted."
    else
        warn "Airflow services are not running. Start them with: docker-compose up -d"
    fi
}

# Create demo frames if input is empty
create_demo_frames() {
    INPUT_DIR="$BASE_DIR/data/input"
    if [ -z "$(ls -A $INPUT_DIR)" ]; then
        info "Input directory is empty. Creating demo frames..."
        
        # Try to use Python to create a test image
        python3 -c "
import os
import numpy as np
try:
    import cv2
    # Create a simple test pattern
    img_size = 512
    img = np.zeros((img_size, img_size, 3), dtype=np.uint8)
    
    # Draw some colored shapes
    cv2.rectangle(img, (100, 100), (400, 400), (0, 0, 255), -1)
    cv2.circle(img, (img_size//2, img_size//2), 150, (0, 255, 0), -1)
    cv2.putText(img, 'TEST IMAGE', (130, 250), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Create demo frames directory
    demo_dir = os.path.join('$INPUT_DIR', 'demo_frames')
    os.makedirs(demo_dir, exist_ok=True)
    
    # Save multiple frames
    for i in range(5):
        # Rotate the hue for each frame to create motion effect
        rotated_img = img.copy()
        if i > 0:
            # Shift colors slightly
            rotated_img[:,:,0] = (img[:,:,0] + i*20) % 256
        
        cv2.imwrite(os.path.join(demo_dir, f'frame_{i:04d}.jpg'), rotated_img)
        
    print(f'Created 5 demo frames in {demo_dir}')
except ImportError:
    print('OpenCV not available. Creating simple demo frames instead.')
    # Create a very simple file if CV2 is not available
    demo_dir = os.path.join('$INPUT_DIR', 'demo_frames')
    os.makedirs(demo_dir, exist_ok=True)
    for i in range(5):
        with open(os.path.join(demo_dir, f'frame_{i:04d}.jpg'), 'w') as f:
            f.write('DEMO FRAME')
    print(f'Created 5 simple demo frames in {demo_dir}')
" || {
            warn "Failed to create demo frames with Python. Creating empty files instead."
            mkdir -p "$INPUT_DIR/demo_frames"
            for i in {1..5}; do
                touch "$INPUT_DIR/demo_frames/frame_$(printf "%04d" $i).jpg"
            done
        }
        
        info "Demo frames created in $INPUT_DIR/demo_frames"
    else
        info "Input directory already contains files. Skipping demo frames creation."
    fi
}

# Main function
main() {
    info "Starting Airflow pipeline setup..."
    check_docker
    create_directories
    check_colmap
    configure_environment
    create_demo_frames
    
    # Only try to check OpenCV and restart Airflow if Docker is running
    if docker-compose ps | grep -q "airflow"; then
        check_opencv
        restart_airflow
        
        # Unpause the DAG
        info "Unpausing the reconstruction_pipeline DAG..."
        docker-compose exec -T airflow-scheduler airflow dags unpause reconstruction_pipeline
        
        info "Setup complete! You can now access the Airflow UI at: http://localhost:8080"
        info "Username: admin"
        info "Password: admin"
    else
        info "Setup partially complete. Start Airflow with: docker-compose up -d"
        info "After Airflow is running, rerun this script to complete the setup."
    fi
}

# Run main function
main 