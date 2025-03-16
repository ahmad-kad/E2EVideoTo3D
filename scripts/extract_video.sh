#!/bin/bash
# extract_video.sh
# This script extracts frames from a video file at a specified frame rate

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
echo -e "${BLUE}E2E3D Video Frame Extraction${NC}"
echo -e "${BLUE}======================================${NC}"

# Load environment variables if .env exists
if [ -f ".env" ]; then
    source .env
    echo -e "${GREEN}Loaded environment variables from .env file${NC}"
fi

# Determine the base project directory
if [ -z "$PROJECT_DIR" ]; then
    # If not set, use current directory
    PROJECT_DIR=$(pwd)
    echo -e "${YELLOW}PROJECT_DIR not set, using current directory: ${PROJECT_DIR}${NC}"
else
    echo -e "${GREEN}Using PROJECT_DIR: ${PROJECT_DIR}${NC}"
fi

# Define directories
DATA_DIR="${PROJECT_DIR}/data"
INPUT_DIR="${DATA_DIR}/input"
VIDEOS_DIR="${DATA_DIR}/videos"

# Check if directories exist, if not create them
mkdir -p "$INPUT_DIR"
mkdir -p "$VIDEOS_DIR"

# Help function
show_help() {
    echo -e "${BLUE}Usage:${NC}"
    echo -e "  $0 -v <video_path> [-f <fps>]"
    echo
    echo -e "${BLUE}Options:${NC}"
    echo -e "  -v, --video    Path to the video file"
    echo -e "  -f, --fps      Frames per second to extract (default: 2)"
    echo -e "  -h, --help     Show this help message"
    echo
    echo -e "${BLUE}Examples:${NC}"
    echo -e "  $0 -v my_video.mp4"
    echo -e "  $0 -v /path/to/video.mp4 -f 5"
    echo
    exit 1
}

# Parse arguments
VIDEO_PATH=""
FPS=2

while (( "$#" )); do
    case "$1" in
        -v|--video)
            if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
                VIDEO_PATH=$2
                shift 2
            else
                echo -e "${RED}Error: Argument for $1 is missing${NC}" >&2
                show_help
            fi
            ;;
        -f|--fps)
            if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
                FPS=$2
                shift 2
            else
                echo -e "${RED}Error: Argument for $1 is missing${NC}" >&2
                show_help
            fi
            ;;
        -h|--help)
            show_help
            ;;
        -*|--*=)
            echo -e "${RED}Error: Unsupported flag $1${NC}" >&2
            show_help
            ;;
        *)
            echo -e "${RED}Error: Unknown argument $1${NC}" >&2
            show_help
            ;;
    esac
done

# Check if video path is provided
if [ -z "$VIDEO_PATH" ]; then
    echo -e "${RED}Error: Video path is required${NC}" >&2
    show_help
fi

# Check if video file exists
if [ ! -f "$VIDEO_PATH" ]; then
    echo -e "${RED}Error: Video file not found: $VIDEO_PATH${NC}" >&2
    echo -e "${YELLOW}Looking for video in other locations...${NC}"
    
    # Try alternative paths
    VIDEO_BASENAME=$(basename "$VIDEO_PATH")
    ALT_PATHS=(
        "${VIDEOS_DIR}/${VIDEO_BASENAME}"
        "${PROJECT_DIR}/${VIDEO_BASENAME}"
        "${PROJECT_DIR}/videos/${VIDEO_BASENAME}"
    )
    
    for ALT_PATH in "${ALT_PATHS[@]}"; do
        if [ -f "$ALT_PATH" ]; then
            echo -e "${GREEN}Found video at: $ALT_PATH${NC}"
            VIDEO_PATH="$ALT_PATH"
            break
        fi
    done
    
    # If still not found
    if [ ! -f "$VIDEO_PATH" ]; then
        echo -e "${RED}Error: Could not find video file in any location.${NC}" >&2
        exit 1
    fi
fi

# Define video basename and destination
VIDEO_BASENAME=$(basename "$VIDEO_PATH")
VIDEO_NAME="${VIDEO_BASENAME%.*}"
DEST_VIDEO_PATH="${VIDEOS_DIR}/${VIDEO_BASENAME}"
OUTPUT_DIR="${INPUT_DIR}"

echo -e "${BLUE}Video Processing Information:${NC}"
echo -e "  Source video: ${VIDEO_PATH}"
echo -e "  Output directory: ${OUTPUT_DIR}"
echo -e "  Frame rate: ${FPS} fps"

# Copy video to videos directory if not already there
if [ "$VIDEO_PATH" != "$DEST_VIDEO_PATH" ]; then
    echo -e "${YELLOW}Copying video to videos directory...${NC}"
    cp "$VIDEO_PATH" "$DEST_VIDEO_PATH"
    echo -e "${GREEN}Video copied to: $DEST_VIDEO_PATH${NC}"
fi

# Clear existing frames if any
if [ -n "$(ls -A "$OUTPUT_DIR" 2>/dev/null)" ]; then
    echo -e "${YELLOW}Warning: Output directory is not empty.${NC}"
    read -p "Do you want to clear existing frames? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Clearing existing frames...${NC}"
        rm -f "${OUTPUT_DIR}"/*.jpg "${OUTPUT_DIR}"/*.png
        echo -e "${GREEN}Existing frames cleared.${NC}"
    fi
fi

# Check if ffmpeg is installed locally
echo -e "${BLUE}Checking for ffmpeg...${NC}"
if command -v ffmpeg >/dev/null 2>&1; then
    echo -e "${GREEN}ffmpeg found. Using local installation.${NC}"
    echo -e "${BLUE}Extracting frames with ffmpeg...${NC}"
    
    # Extract frames with local ffmpeg
    ffmpeg -i "$VIDEO_PATH" -vf "fps=$FPS" -q:v 1 "${OUTPUT_DIR}/frame_%04d.jpg"
    
    FRAME_COUNT=$(ls -1 "${OUTPUT_DIR}"/frame_*.jpg 2>/dev/null | wc -l)
    echo -e "${GREEN}Extracted $FRAME_COUNT frames to $OUTPUT_DIR${NC}"
else
    echo -e "${YELLOW}ffmpeg not found. Trying with Docker...${NC}"
    
    # Check if Docker is installed
    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}Error: Neither ffmpeg nor Docker is installed.${NC}" >&2
        echo -e "${YELLOW}Please install ffmpeg or Docker to continue.${NC}" >&2
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not running.${NC}" >&2
        echo -e "${YELLOW}Please start Docker and try again.${NC}" >&2
        exit 1
    fi
    
    echo -e "${BLUE}Pulling ffmpeg Docker image...${NC}"
    docker pull jrottenberg/ffmpeg:latest
    
    echo -e "${BLUE}Extracting frames with Docker...${NC}"
    # Extract frames with Docker ffmpeg
    docker run --rm \
        -v "$(dirname "$VIDEO_PATH"):/tmp/video" \
        -v "${OUTPUT_DIR}:/tmp/output" \
        jrottenberg/ffmpeg \
        -i "/tmp/video/$(basename "$VIDEO_PATH")" \
        -vf "fps=$FPS" \
        -q:v 1 "/tmp/output/frame_%04d.jpg"
    
    FRAME_COUNT=$(ls -1 "${OUTPUT_DIR}"/frame_*.jpg 2>/dev/null | wc -l)
    echo -e "${GREEN}Extracted $FRAME_COUNT frames to $OUTPUT_DIR${NC}"
fi

# Summary
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Frame extraction complete!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "Video: ${VIDEO_PATH}"
echo -e "Frames: ${FRAME_COUNT} (at ${FPS} fps)"
echo -e "Output: ${OUTPUT_DIR}"
echo -e "${BLUE}======================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Access Airflow UI at: http://localhost:8080"
echo -e "2. Trigger the reconstruction_pipeline DAG"
echo -e "3. The 3D model will be available at: ${DATA_DIR}/output/final_model.ply"
echo -e "${BLUE}======================================${NC}"

exit 0
