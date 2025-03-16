#!/bin/bash

# Enable error handling
set -e

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}   E2E3D Docker Services Configuration Fix    ${NC}"
echo -e "${BLUE}===============================================${NC}"

# Get the base directory of the project
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BASE_DIR"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found in $BASE_DIR${NC}"
    exit 1
fi

# Create a backup of the original docker-compose.yml
echo -e "${BLUE}Creating backup of docker-compose.yml...${NC}"
cp docker-compose.yml docker-compose.yml.original.backup
echo -e "${GREEN}Backup created: docker-compose.yml.original.backup${NC}"

# Analyze docker-compose.yml to find services
echo -e "${BLUE}Analyzing docker-compose.yml...${NC}"
AIRFLOW_WEBSERVER=$(grep -l "airflow-webserver:" docker-compose.yml || echo "")
AIRFLOW_SCHEDULER=$(grep -l "airflow-scheduler:" docker-compose.yml || echo "")
MINIO_SERVICE=$(grep -l "minio:" docker-compose.yml || echo "")
POSTGRES_SERVICE=$(grep -l "postgres:" docker-compose.yml || echo "")
COLMAP_SERVICE=$(grep -l "colmap:" docker-compose.yml || echo "")

# Check for alternative service names
if [ -z "$MINIO_SERVICE" ]; then
    MINIO_SERVICE=$(grep -l "image: minio/minio" docker-compose.yml || echo "")
fi

if [ -z "$COLMAP_SERVICE" ]; then
    COLMAP_SERVICE=$(grep -l "image: colmap" docker-compose.yml || echo "")
    if [ -z "$COLMAP_SERVICE" ]; then
        COLMAP_SERVICE=$(grep -l "photogrammetry:" docker-compose.yml || echo "")
    fi
fi

# Determine service names
MINIO_NAME="minio"
if [ -n "$MINIO_SERVICE" ]; then
    TEMP_MINIO_NAME=$(grep -A1 "minio:" docker-compose.yml | grep "container_name" | cut -d: -f2 | tr -d ' ' || echo "")
    if [ -n "$TEMP_MINIO_NAME" ]; then
        MINIO_NAME="$TEMP_MINIO_NAME"
    fi
fi

COLMAP_NAME="photogrammetry"
if [ -n "$COLMAP_SERVICE" ]; then
    TEMP_COLMAP_NAME=$(grep -A1 "colmap:" docker-compose.yml | grep "container_name" | cut -d: -f2 | tr -d ' ' || echo "")
    if [ -n "$TEMP_COLMAP_NAME" ]; then
        COLMAP_NAME="$TEMP_COLMAP_NAME"
    fi
fi

# Print service status
echo -e "Services found:"
echo -e "- Airflow Webserver: ${AIRFLOW_WEBSERVER:+${GREEN}✅${NC}}${AIRFLOW_WEBSERVER:-${RED}❌${NC}}"
echo -e "- Airflow Scheduler: ${AIRFLOW_SCHEDULER:+${GREEN}✅${NC}}${AIRFLOW_SCHEDULER:-${RED}❌${NC}}"
echo -e "- MinIO service: ${MINIO_SERVICE:+${GREEN}✅${NC}}${MINIO_SERVICE:-${RED}❌${NC}}${MINIO_SERVICE:+ (named: $MINIO_NAME)}"
echo -e "- Postgres: ${POSTGRES_SERVICE:+${GREEN}✅${NC}}${POSTGRES_SERVICE:-${RED}❌${NC}}"
echo -e "- COLMAP service: ${COLMAP_SERVICE:+${GREEN}✅${NC}}${COLMAP_SERVICE:-${RED}❌${NC}}${COLMAP_SERVICE:+ (named: $COLMAP_NAME)}"
echo

# Fix service naming in scripts
echo -e "${BLUE}Fixing service naming in scripts...${NC}"
for script in "$SCRIPT_DIR"/*.sh; do
    if [ -f "$script" ]; then
        SCRIPT_NAME=$(basename "$script")
        echo -e "Updating $SCRIPT_NAME with correct service names..."
        sed -i.bak "s/minio/$MINIO_NAME/g" "$script"
        sed -i.bak "s/photogrammetry/$COLMAP_NAME/g" "$script"
        rm -f "${script}.bak"
    fi
done
echo

# Fix docker-compose.yml for MinIO connectivity
echo -e "${BLUE}Fixing docker-compose.yml for MinIO connectivity...${NC}"

# Check if MinIO service exists
if [ -z "$MINIO_SERVICE" ]; then
    echo -e "${YELLOW}MinIO service not found in docker-compose.yml${NC}"
    echo -e "${YELLOW}Skipping MinIO service addition as it may cause conflicts${NC}"
else
    # Check if MinIO service has ports section
    MINIO_PORTS=$(grep -A10 "minio:" docker-compose.yml | grep -A5 "ports:" || echo "")
    if [ -z "$MINIO_PORTS" ]; then
        echo -e "${YELLOW}Adding ports section to MinIO service...${NC}"
        sed -i.bak '/minio:/,/volumes:/ s/volumes:/ports:\n      - "9000:9000"\n      - "9001:9001"\n    volumes:/' docker-compose.yml
        rm -f docker-compose.yml.bak
    fi

    # Check if MinIO service has environment section
    MINIO_ENV=$(grep -A10 "minio:" docker-compose.yml | grep -A5 "environment:" || echo "")
    if [ -z "$MINIO_ENV" ]; then
        echo -e "${YELLOW}Adding environment section to MinIO service...${NC}"
        sed -i.bak '/minio:/,/volumes:/ s/volumes:/environment:\n      - MINIO_ROOT_USER=minioadmin\n      - MINIO_ROOT_PASSWORD=minioadmin\n      - MINIO_CONSOLE_ADDRESS=:9001\n    volumes:/' docker-compose.yml
        rm -f docker-compose.yml.bak
    fi
fi

# Fix volume mounts for all services
echo -e "${BLUE}Fixing volume mounts for all services...${NC}"

# Create necessary directories
mkdir -p data/videos data/input data/output
mkdir -p airflow/dags airflow/logs airflow/plugins
chmod -R 755 data airflow

# Function to ensure a service has proper volume mounts
ensure_volumes() {
    local service=$1
    local service_line=$(grep -n "$service:" docker-compose.yml | cut -d: -f1 || echo "")
    
    if [[ "$service_line" =~ ^[0-9]+$ ]] && [ "$service_line" -gt 0 ]; then
        echo -e "Checking volumes for $service..."
        
        # Check if volumes section exists
        local volumes_exist=$(tail -n +"$service_line" docker-compose.yml | grep -m 1 -c "volumes:" || echo "0")
        
        if [ "$volumes_exist" -eq 0 ]; then
            echo -e "${YELLOW}Adding volumes section to $service...${NC}"
            sed -i'.bak' "$service_line a\\
    volumes:\\
      - ./data:/opt/airflow/data\\
      - ./airflow/dags:/opt/airflow/dags\\
      - ./airflow/logs:/opt/airflow/logs\\
      - ./airflow/plugins:/opt/airflow/plugins" docker-compose.yml
            rm -f docker-compose.yml.bak
        else
            # Check if data volume is mounted
            local data_mount_exists=$(tail -n +"$service_line" docker-compose.yml | grep -m 1 -A 10 "volumes:" | grep -c "/data" || echo "0")
            if [ "$data_mount_exists" -eq 0 ]; then
                echo -e "${YELLOW}Adding data volume mount to $service...${NC}"
                local volumes_line=$(tail -n +"$service_line" docker-compose.yml | grep -n "volumes:" | head -1 | cut -d: -f1 || echo "")
                if [[ "$volumes_line" =~ ^[0-9]+$ ]] && [ -n "$volumes_line" ]; then
                    volumes_line=$((service_line + volumes_line - 1))
                    sed -i'.bak' "$volumes_line a\\
      - ./data:/opt/airflow/data" docker-compose.yml
                    rm -f docker-compose.yml.bak
                fi
            fi
        fi
    fi
}

# Fix volumes for Airflow services
if [ "$AIRFLOW_WEBSERVER" ]; then
    ensure_volumes "airflow-webserver"
fi

if [ "$AIRFLOW_SCHEDULER" ]; then
    ensure_volumes "airflow-scheduler"
fi

# Fix COLMAP service volumes
if [ "$COLMAP_SERVICE" ]; then
    # Slightly different volume path for COLMAP
    COLMAP_LINE=$(grep -n "$COLMAP_NAME:" docker-compose.yml | cut -d: -f1 || echo "")
    
    if [[ "$COLMAP_LINE" =~ ^[0-9]+$ ]] && [ "$COLMAP_LINE" -gt 0 ]; then
        echo -e "Checking volumes for COLMAP service..."
        
        # Check if volumes section exists
        COLMAP_VOLUMES_EXIST=$(tail -n +"$COLMAP_LINE" docker-compose.yml | grep -m 1 -c "volumes:" || echo "0")
        
        if [ "$COLMAP_VOLUMES_EXIST" -eq 0 ]; then
            echo -e "${YELLOW}Adding volumes section to COLMAP service...${NC}"
            sed -i'.bak' "$COLMAP_LINE a\\
    volumes:\\
      - ./data:/data" docker-compose.yml
            rm -f docker-compose.yml.bak
        else
            # Check if data volume is mounted
            COLMAP_DATA_MOUNT_EXISTS=$(tail -n +"$COLMAP_LINE" docker-compose.yml | grep -m 1 -A 10 "volumes:" | grep -c "/data" || echo "0")
            if [ "$COLMAP_DATA_MOUNT_EXISTS" -eq 0 ]; then
                echo -e "${YELLOW}Adding data volume mount to COLMAP service...${NC}"
                COLMAP_VOLUMES_LINE=$(tail -n +"$COLMAP_LINE" docker-compose.yml | grep -n "volumes:" | head -1 | cut -d: -f1 || echo "")
                if [[ "$COLMAP_VOLUMES_LINE" =~ ^[0-9]+$ ]] && [ -n "$COLMAP_VOLUMES_LINE" ]; then
                    COLMAP_VOLUMES_LINE=$((COLMAP_LINE + COLMAP_VOLUMES_LINE - 1))
                    sed -i'.bak' "$COLMAP_VOLUMES_LINE a\\
      - ./data:/data" docker-compose.yml
                    rm -f docker-compose.yml.bak
                fi
            fi
        fi
    fi
fi

# Create improved direct video extraction script
echo -e "${BLUE}Creating improved direct video extraction script...${NC}"
cat > "$SCRIPT_DIR/extract_video.sh" << 'EOL'
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
EOL

chmod +x "$SCRIPT_DIR/extract_video.sh"
echo -e "${GREEN}Created improved video extraction script: $SCRIPT_DIR/extract_video.sh${NC}"
echo

# Final message
echo -e "${BLUE}Ready to apply changes and restart containers...${NC}"
echo -e "You can now restart your Docker services with:"
echo -e "  docker-compose down"
echo -e "  docker-compose up -d"
echo
echo -e "${GREEN}Docker services configuration has been fixed!${NC}"

exit 0 