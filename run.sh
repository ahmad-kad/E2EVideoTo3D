#!/bin/bash
set -e

echo "========== E2E3D Setup Script =========="
echo "Setting up 3D reconstruction pipeline environment..."

# Try to install ffmpeg if not present
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg not found. Attempting to install..."
    
    # Check which package manager is available
    if command -v apt-get &> /dev/null; then
        echo "Using apt-get to install FFmpeg..."
        sudo apt-get update
        sudo apt-get install -y ffmpeg
    elif command -v brew &> /dev/null; then
        echo "Using Homebrew to install FFmpeg..."
        brew install ffmpeg
    elif command -v yum &> /dev/null; then
        echo "Using yum to install FFmpeg..."
        sudo yum install -y ffmpeg
    elif command -v pacman &> /dev/null; then
        echo "Using pacman to install FFmpeg..."
        sudo pacman -S ffmpeg
    else
        echo "Could not automatically install FFmpeg. Please install it manually or use the Docker-based video processing script."
        echo "- macOS: brew install ffmpeg"
        echo "- Ubuntu/Debian: sudo apt-get install ffmpeg"
        echo "- CentOS/RHEL: sudo yum install ffmpeg"
        echo "- Arch Linux: sudo pacman -S ffmpeg"
    fi
fi

# Check if FFmpeg was installed successfully
if command -v ffmpeg &> /dev/null; then
    echo "FFmpeg is installed. Video processing is available."
else
    echo "FFmpeg is not installed. Docker-based video processing will be used."
fi

# Create necessary directories
mkdir -p airflow/dags
mkdir -p airflow/plugins
mkdir -p airflow/logs
mkdir -p data/input
mkdir -p data/output
mkdir -p data/videos
mkdir -p scripts

# Check if scripts exist, create them if not
for script in run_colmap.sh video_to_frames.sh fix_airflow.sh docker_video_process.sh init_airflow.sh; do
    if [ ! -f "scripts/$script" ]; then
        echo "Creating $script script..."
        if [ "$script" = "run_colmap.sh" ]; then
            cat > scripts/run_colmap.sh << 'EOL'
#!/bin/bash
set -e

# Default paths
INPUT_PATH=${INPUT_PATH:-/app/data/input}
OUTPUT_PATH=${OUTPUT_PATH:-/app/data/output}
WORKSPACE_PATH=${OUTPUT_PATH}/colmap_workspace

# Check if GPU should be used
USE_GPU=${USE_GPU:-false}

# Auto-detect NVIDIA GPU if not explicitly set
if [ "$USE_GPU" = "auto" ]; then
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        USE_GPU=true
        echo "NVIDIA GPU detected. Using GPU acceleration."
    else
        USE_GPU=false
        echo "No NVIDIA GPU detected. Using CPU mode."
    fi
fi

# Set GPU flags based on USE_GPU value
if [ "$USE_GPU" = "true" ]; then
    GPU_EXTRACTION_FLAG="1"
    GPU_MATCHING_FLAG="1"
    GPU_INDEX="0"
    echo "Running COLMAP with GPU acceleration"
else
    GPU_EXTRACTION_FLAG="0"
    GPU_MATCHING_FLAG="0"
    GPU_INDEX="-1"
    echo "Running COLMAP with CPU only"
fi

# Create workspace directories
mkdir -p "${WORKSPACE_PATH}"
mkdir -p "${WORKSPACE_PATH}/database"
mkdir -p "${WORKSPACE_PATH}/sparse"
mkdir -p "${WORKSPACE_PATH}/dense"

# Define paths
DATABASE_PATH="${WORKSPACE_PATH}/database/database.db"
SPARSE_PATH="${WORKSPACE_PATH}/sparse"
DENSE_PATH="${WORKSPACE_PATH}/dense"

echo "Starting COLMAP processing pipeline..."
echo "Input path: ${INPUT_PATH}"
echo "Output path: ${OUTPUT_PATH}"

# Feature extraction
echo "Step 1: Feature extraction..."
colmap feature_extractor \
    --database_path "${DATABASE_PATH}" \
    --image_path "${INPUT_PATH}" \
    --ImageReader.camera_model SIMPLE_RADIAL \
    --SiftExtraction.use_gpu ${GPU_EXTRACTION_FLAG}

# Feature matching
echo "Step 2: Feature matching..."
colmap exhaustive_matcher \
    --database_path "${DATABASE_PATH}" \
    --SiftMatching.use_gpu ${GPU_MATCHING_FLAG}

# Sparse reconstruction (Structure from Motion)
echo "Step 3: Sparse reconstruction..."
mkdir -p "${SPARSE_PATH}/0"
colmap mapper \
    --database_path "${DATABASE_PATH}" \
    --image_path "${INPUT_PATH}" \
    --output_path "${SPARSE_PATH}"

# Check if sparse reconstruction succeeded
if [ ! -f "${SPARSE_PATH}/0/cameras.bin" ]; then
    echo "Sparse reconstruction failed. Exiting."
    exit 1
fi

# Image undistortion for dense reconstruction
echo "Step 4: Image undistortion..."
colmap image_undistorter \
    --image_path "${INPUT_PATH}" \
    --input_path "${SPARSE_PATH}/0" \
    --output_path "${DENSE_PATH}" \
    --output_type COLMAP

# Dense reconstruction (patch matching and stereo fusion)
echo "Step 5: Patch match stereo..."
colmap patch_match_stereo \
    --workspace_path "${DENSE_PATH}" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index ${GPU_INDEX}

# Stereo fusion
echo "Step 6: Stereo fusion..."
colmap stereo_fusion \
    --workspace_path "${DENSE_PATH}" \
    --workspace_format COLMAP \
    --input_type geometric \
    --output_path "${DENSE_PATH}/fused.ply"

# Meshing (optional)
echo "Step 7: Meshing..."
colmap poisson_mesher \
    --input_path "${DENSE_PATH}/fused.ply" \
    --output_path "${DENSE_PATH}/meshed.ply"

# Texture mapping (optional)
echo "Step 8: Texture mapping..."
colmap model_converter \
    --input_path "${SPARSE_PATH}/0" \
    --output_path "${SPARSE_PATH}/0" \
    --output_type TXT

colmap model_converter \
    --input_path "${SPARSE_PATH}/0" \
    --output_path "${WORKSPACE_PATH}/model-normalized.ply" \
    --output_type PLY

echo "COLMAP processing completed!"
echo "Output files are in ${OUTPUT_PATH}"

# Keep container running if in interactive mode
if [ "$1" = "interactive" ]; then
    echo "Running in interactive mode. Press Ctrl+C to exit."
    tail -f /dev/null
fi
EOL
        elif [ "$script" = "video_to_frames.sh" ]; then
            cat > scripts/video_to_frames.sh << 'EOL'
#!/bin/bash
set -e

# Default settings
INPUT_VIDEO=${1:-""}
OUTPUT_DIR=${2:-"data/input"}
FPS=${3:-1}  # Extract 1 frame per second by default

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed. Please install it first."
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo ""
    echo "Alternatively, use the Docker-based script that doesn't require FFmpeg installation:"
    echo "  ./scripts/docker_video_process.sh $INPUT_VIDEO $OUTPUT_DIR $FPS"
    exit 1
fi

# Check if input video is provided
if [ -z "$INPUT_VIDEO" ]; then
    echo "Error: No input video provided."
    echo "Usage: $0 <input_video_path> [output_directory] [frames_per_second]"
    exit 1
fi

# Check if input video exists
if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Input video file not found: $INPUT_VIDEO"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Get video information
DURATION=$(ffmpeg -i "$INPUT_VIDEO" 2>&1 | grep "Duration" | cut -d ' ' -f 4 | sed 's/,//')
echo "Video duration: $DURATION"

# Extract frames from video
echo "Extracting frames from video at $FPS frames per second..."
echo "Output will be saved to $OUTPUT_DIR"

ffmpeg -i "$INPUT_VIDEO" -vf "fps=$FPS" -q:v 2 "$OUTPUT_DIR/frame_%04d.jpg"

# Count extracted frames
FRAME_COUNT=$(ls "$OUTPUT_DIR" | grep -c "frame_")
echo "Successfully extracted $FRAME_COUNT frames from video."
echo ""
echo "Next steps:"
echo "1. Run the 3D reconstruction pipeline with these frames"
echo "2. To start the pipeline, run ./run.sh"
echo "3. Access Airflow UI and trigger the 'reconstruction_pipeline' DAG"
echo "4. Results will be available in 'data/output'"
EOL
        elif [ "$script" = "fix_airflow.sh" ]; then
            cat > scripts/fix_airflow.sh << 'EOL'
#!/bin/bash
set -e

echo "==== Diagnosing Airflow Connection Issues ===="

# Check if containers are running
echo "Checking container status..."
CONTAINER_STATUS=$(docker-compose ps)
echo "$CONTAINER_STATUS"

# Check if Airflow webserver container is running
if ! echo "$CONTAINER_STATUS" | grep -q "airflow-webserver.*Up"; then
    echo "Error: Airflow webserver container is not running."
    echo "Attempting to restart..."
    docker-compose restart airflow-webserver
    sleep 10
fi

# Check Airflow logs for errors
echo "Checking Airflow webserver logs for errors..."
docker-compose logs --tail=50 airflow-webserver

# Check if database initialization is needed
if docker-compose logs airflow-webserver | grep -q "You need to initialize the database"; then
    echo "Database initialization needed. Running init script..."
    ./scripts/init_airflow.sh
fi

# Check if port 8080 is already in use by another process
echo "Checking if port 8080 is already in use..."
if command -v lsof &> /dev/null; then
    PROCESSES_ON_8080=$(lsof -i :8080 | grep LISTEN)
    if [ -n "$PROCESSES_ON_8080" ]; then
        echo "Warning: Port 8080 is already in use by another process:"
        echo "$PROCESSES_ON_8080"
        echo "Please stop that process or change the Airflow port in docker-compose.yml"
    else
        echo "Port 8080 is available."
    fi
else
    echo "lsof command not found, skipping port check..."
fi

# Check network connectivity to the container
echo "Checking network connectivity to Airflow webserver..."
if docker-compose exec airflow-webserver curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health; then
    echo "Airflow webserver is responding to health checks within the container."
else
    echo "Error: Airflow webserver is not responding to health checks."
    echo "Attempting to restart..."
    docker-compose restart airflow-webserver
    sleep 10
fi

# Create Airflow user if it doesn't exist
echo "Checking if Airflow user exists..."
USER_EXISTS=$(docker-compose exec airflow-webserver airflow users list | grep -c "admin")
if [ "$USER_EXISTS" -eq 0 ]; then
    echo "Creating admin user for Airflow..."
    docker-compose exec airflow-webserver airflow users create \
        --username admin \
        --password admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com
    echo "Admin user created with username 'admin' and password 'admin'"
fi

echo ""
echo "==== Airflow Connection Diagnostics Complete ===="
echo ""
echo "If you're still having issues connecting to Airflow:"
echo "1. Try accessing Airflow using a different browser or incognito mode"
echo "2. Make sure your firewall isn't blocking port 8080"
echo "3. Try using the IP address instead of localhost: http://127.0.0.1:8080"
echo "4. If all else fails, try restarting Docker completely"
echo ""
echo "You can restart the entire stack with:"
echo "  docker-compose down"
echo "  docker-compose up -d"
EOL
        elif [ "$script" = "docker_video_process.sh" ]; then
            cat > scripts/docker_video_process.sh << 'EOL'
#!/bin/bash
set -e

# Default settings
INPUT_VIDEO=${1:-""}
OUTPUT_DIR=${2:-"data/input"}
FPS=${3:-1}  # Extract 1 frame per second by default

# Ensure input video is provided
if [ -z "$INPUT_VIDEO" ]; then
    echo "Error: No input video provided."
    echo "Usage: $0 <input_video_path> [output_directory] [frames_per_second]"
    exit 1
fi

# Check if input video exists
if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Input video file not found: $INPUT_VIDEO"
    exit 1
fi

# Get absolute paths
INPUT_VIDEO_ABS=$(realpath "$INPUT_VIDEO")
OUTPUT_DIR_ABS=$(realpath "$OUTPUT_DIR")

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR_ABS"

echo "Processing video with Docker (no local FFmpeg installation required)"
echo "Video: $INPUT_VIDEO_ABS"
echo "Output: $OUTPUT_DIR_ABS"
echo "FPS: $FPS"

# Run FFmpeg in a Docker container
docker run --rm \
    -v "$INPUT_VIDEO_ABS:/video/input.mp4" \
    -v "$OUTPUT_DIR_ABS:/video/output" \
    jrottenberg/ffmpeg:4.4 \
    -i /video/input.mp4 \
    -vf "fps=$FPS" \
    -q:v 2 \
    /video/output/frame_%04d.jpg

# Count extracted frames
FRAME_COUNT=$(ls "$OUTPUT_DIR_ABS" | grep -c "frame_")
echo "Successfully extracted $FRAME_COUNT frames from video."
echo ""
echo "Next steps:"
echo "1. Run the 3D reconstruction pipeline with these frames"
echo "2. To start the pipeline, run ./run.sh"
echo "3. Access Airflow UI and trigger the 'reconstruction_pipeline' DAG"
echo "4. Results will be available in 'data/output'"
EOL
        elif [ "$script" = "init_airflow.sh" ]; then
            cat > scripts/init_airflow.sh << 'EOL'
#!/bin/bash
set -e

echo "==== Initializing Airflow Database ===="

# Stop any running Airflow containers
echo "Stopping Airflow containers..."
docker-compose stop airflow-webserver airflow-scheduler || true

# Reset Airflow database
echo "Initializing Airflow database..."
docker-compose run --rm airflow-webserver airflow db init

# Create default connections
echo "Creating default connections..."
docker-compose run --rm airflow-webserver airflow connections add 'fs_default' \
    --conn-type 'fs' \
    --conn-extra '{"path": "/"}' || true

# Create admin user
echo "Creating admin user..."
docker-compose run --rm airflow-webserver airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com || true

# Start Airflow services
echo "Starting Airflow services..."
docker-compose start airflow-webserver airflow-scheduler || docker-compose up -d airflow-webserver airflow-scheduler

echo "==== Airflow Initialization Complete ===="
echo ""
echo "You can now access Airflow at: http://localhost:8080"
echo "Username: admin"
echo "Password: admin"
EOL
        fi
        chmod +x "scripts/$script"
        echo "Script created successfully."
    fi
done

# Make sure all scripts are executable
chmod +x scripts/*.sh

# Run the setup script
chmod +x scripts/setup_environment.sh
./scripts/setup_environment.sh

# Stop any running containers
echo "Stopping any running containers..."
docker-compose down

# Determine if we need memory-optimized build
MEMORY_OPTIMIZED=false
MEMORY_LIMIT_MB=0

# Check available memory (this works on Linux and macOS)
if [ "$(uname)" = "Darwin" ]; then
    # macOS
    MEMORY_TOTAL_KB=$(sysctl hw.memsize | awk '{print $2}')
    MEMORY_TOTAL_MB=$((MEMORY_TOTAL_KB / 1024 / 1024))
else
    # Linux
    MEMORY_TOTAL_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    MEMORY_TOTAL_MB=$((MEMORY_TOTAL_KB / 1024))
fi

echo "Total system memory: ${MEMORY_TOTAL_MB}MB"

# If less than 8GB RAM, use memory optimized build
if [ "$MEMORY_TOTAL_MB" -lt 8192 ]; then
    MEMORY_OPTIMIZED=true
    echo "Memory-optimized build will be used (system has less than 8GB RAM)"
    
    # Set Docker memory limit to 75% of available memory
    MEMORY_LIMIT_MB=$((MEMORY_TOTAL_MB * 75 / 100))
    echo "Setting Docker build memory limit to ${MEMORY_LIMIT_MB}MB"
fi

# Rebuild the photogrammetry container
echo "Building the photogrammetry container..."
if [ "$MEMORY_OPTIMIZED" = true ]; then
    # Memory optimized build
    DOCKER_BUILDKIT=1 docker build \
        --memory=${MEMORY_LIMIT_MB}m \
        --build-arg BASE_IMAGE=${BASE_IMAGE:-ubuntu:20.04} \
        -f Dockerfile.colmap \
        -t e2e3d-photogrammetry .
        
    # Update docker-compose to use the pre-built image
    cat > docker-compose.override.yml << EOL
version: '3.7'

services:
  photogrammetry:
    image: e2e3d-photogrammetry
EOL
    
    docker-compose up -d
else
    # Standard build
    docker-compose build --no-cache photogrammetry
    
    # Start all services
    echo "Starting all services..."
    docker-compose up -d
fi

# Initialize Airflow database
echo "Initializing Airflow..."
sleep 10  # Give all containers time to start

# Run Airflow initialization script
./scripts/init_airflow.sh

# Show running containers
echo "Services started. Running containers:"
docker-compose ps

echo ""
echo "Access your services at:"
echo "  - Airflow: http://localhost:8080 (username: admin, password: admin)"
echo "  - MinIO: http://localhost:9000 (console: http://localhost:9001)"
echo "  - Spark Master UI: http://localhost:8001"
echo ""
echo "To process video to images:"
if command -v ffmpeg &> /dev/null; then
    echo "  Option 1 (Local FFmpeg): "
    echo "    ./scripts/video_to_frames.sh data/videos/your_video.mp4 data/input 1"
fi
echo "  Option 2 (Docker-based processing - no FFmpeg installation required): "
echo "    ./scripts/docker_video_process.sh data/videos/your_video.mp4 data/input 1"
echo ""
echo "To process images directly:"
echo "  1. Place your input images in the 'data/input' directory"
echo "  2. Access Airflow UI and trigger the 'reconstruction_pipeline' DAG"
echo "  3. Results will be available in 'data/output'"
echo ""
echo "If you cannot access Airflow UI, run the troubleshooting script:"
echo "  ./scripts/fix_airflow.sh" 