#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}  E2E3D MinIO & Video Extraction Fix Script   ${NC}"
echo -e "${BLUE}===============================================${NC}"

# Make sure we're in the project root directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml file not found in current directory!${NC}"
    echo "Please run this script from the root directory of your project."
    exit 1
fi

# Create backup
echo -e "\n${BLUE}Creating backup of docker-compose.yml...${NC}"
cp docker-compose.yml docker-compose.yml.minio_fix.backup
echo -e "${GREEN}Backup created: docker-compose.yml.minio_fix.backup${NC}"

# --- FIX 1: Fix MinIO connection issue ---
echo -e "\n${BLUE}Fixing MinIO connection issues...${NC}"

# Check if MinIO service exists in docker-compose.yml
if ! grep -q "services:.*minio:" docker-compose.yml; then
    echo -e "${RED}Error: MinIO service not found in docker-compose.yml${NC}"
    echo "Your setup might be different from expected."
    exit 1
fi

# Update MinIO port binding to ensure it's properly exposed
echo -e "${YELLOW}Updating MinIO port configurations...${NC}"

# Check for ports section in MinIO configuration
if grep -A 30 "services:.*minio:" docker-compose.yml | grep -q "ports:"; then
    # Update 9001 port binding if it exists but might be wrong
    if grep -A 30 "services:.*minio:" docker-compose.yml | grep -A 10 "ports:" | grep -q "9001"; then
        echo -e "${YELLOW}Updating MinIO UI port binding...${NC}"
        sed -i.tmp '/services:.*minio:/,/ports:/ {/9001/s/[0-9.]*:9001/0.0.0.0:9001/}' docker-compose.yml
    else
        echo -e "${YELLOW}Adding MinIO UI port binding...${NC}"
        sed -i.tmp '/services:.*minio:/,/ports:/ s/\([ ]*\)ports:/\1ports:\n\1  - "0.0.0.0:9001:9001"/' docker-compose.yml
    fi
    
    # Update 9000 port binding if it exists but might be wrong
    if grep -A 30 "services:.*minio:" docker-compose.yml | grep -A 10 "ports:" | grep -q "9000"; then
        echo -e "${YELLOW}Updating MinIO API port binding...${NC}"
        sed -i.tmp '/services:.*minio:/,/ports:/ {/9000/s/[0-9.]*:9000/0.0.0.0:9000/}' docker-compose.yml
    else
        echo -e "${YELLOW}Adding MinIO API port binding...${NC}"
        sed -i.tmp '/services:.*minio:/,/ports:/ s/\([ ]*\)ports:/\1ports:\n\1  - "0.0.0.0:9000:9000"/' docker-compose.yml
    fi
else
    # Add ports section if it doesn't exist
    echo -e "${YELLOW}Adding ports section to MinIO...${NC}"
    sed -i.tmp '/services:.*minio:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1ports:\n\1  - "0.0.0.0:9000:9000"\n\1  - "0.0.0.0:9001:9001"\n&/' docker-compose.yml
fi

# Make sure MinIO has the correct environment variables
echo -e "${YELLOW}Updating MinIO environment variables...${NC}"
if grep -A 30 "services:.*minio:" docker-compose.yml | grep -q "environment:"; then
    # Add MINIO_CONSOLE_ADDRESS if it doesn't exist
    if ! grep -A 30 "services:.*minio:" docker-compose.yml | grep -A 30 "environment:" | grep -q "MINIO_CONSOLE_ADDRESS"; then
        sed -i.tmp '/services:.*minio:/,/environment:/ s/\([ ]*\)environment:/\1environment:\n\1  - MINIO_CONSOLE_ADDRESS=:9001/' docker-compose.yml
    fi

    # Add MINIO_BROWSER_REDIRECT_URL if it doesn't exist (helps with accessing from localhost)
    if ! grep -A 30 "services:.*minio:" docker-compose.yml | grep -A 30 "environment:" | grep -q "MINIO_BROWSER_REDIRECT_URL"; then
        sed -i.tmp '/services:.*minio:/,/environment:/ s/\([ ]*\)environment:/\1environment:\n\1  - MINIO_BROWSER_REDIRECT_URL=http:\/\/localhost:9001/' docker-compose.yml
    fi
else
    # Add environment section if it doesn't exist
    sed -i.tmp '/services:.*minio:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1environment:\n\1  - MINIO_CONSOLE_ADDRESS=:9001\n\1  - MINIO_BROWSER_REDIRECT_URL=http:\/\/localhost:9001\n&/' docker-compose.yml
fi

# Clean up tmp files
rm -f docker-compose.yml.tmp

# --- FIX 2: Fix video mounting and frame extraction issues ---
echo -e "\n${BLUE}Fixing video mounting and frame extraction issues...${NC}"

# Create necessary directories if they don't exist
echo -e "${YELLOW}Creating required directories...${NC}"
mkdir -p data/videos
mkdir -p data/input
mkdir -p data/output
chmod -R 755 data

# Fix volume mapping for airflow services
for service in "airflow-webserver" "airflow-scheduler"; do
    if grep -q "services:.*$service:" docker-compose.yml; then
        echo -e "${YELLOW}Adding/updating volume mapping for $service...${NC}"
        
        # Check if service has volumes section
        if grep -A 30 "services:.*$service:" docker-compose.yml | grep -q "volumes:"; then
            # Check if data volume mapping exists
            if ! grep -A 30 "services:.*$service:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "./data:/opt/airflow/data"; then
                sed -i.tmp "/services:.*$service:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/data:\/opt\/airflow\/data/" docker-compose.yml
                rm -f docker-compose.yml.tmp
            fi
        else
            # Add volumes section if it doesn't exist
            sed -i.tmp "/services:.*$service:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1volumes:\n\1  - \.\/data:\/opt\/airflow\/data\n&/" docker-compose.yml
            rm -f docker-compose.yml.tmp
        fi
    fi
done

# Fix volume mapping for photogrammetry service
if grep -q "services:.*photogrammetry:" docker-compose.yml; then
    echo -e "${YELLOW}Adding/updating volume mapping for photogrammetry service...${NC}"
    
    # Check if service has volumes section
    if grep -A 30 "services:.*photogrammetry:" docker-compose.yml | grep -q "volumes:"; then
        # Check if data volume mapping exists
        if ! grep -A 30 "services:.*photogrammetry:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "./data:/data"; then
            sed -i.tmp "/services:.*photogrammetry:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/data:\/data/" docker-compose.yml
            rm -f docker-compose.yml.tmp
        fi
    else
        # Add volumes section if it doesn't exist
        sed -i.tmp "/services:.*photogrammetry:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1volumes:\n\1  - \.\/data:\/data\n&/" docker-compose.yml
        rm -f docker-compose.yml.tmp
    fi
fi

# Update DAG to use volume-aware paths
echo -e "\n${BLUE}Updating Airflow DAG to use correct paths...${NC}"

mkdir -p airflow/dags
# Check if DAG file exists
if [ -f "airflow/dags/reconstruction_pipeline.py" ]; then
    # Backup the DAG file
    cp airflow/dags/reconstruction_pipeline.py airflow/dags/reconstruction_pipeline.py.backup
    
    # Update VIDEO_DIR, FRAMES_DIR, and OUTPUT_DIR paths in the DAG
    sed -i.tmp 's|VIDEO_DIR = .*|VIDEO_DIR = "/opt/airflow/data/videos"|' airflow/dags/reconstruction_pipeline.py
    sed -i.tmp 's|FRAMES_DIR = .*|FRAMES_DIR = "/opt/airflow/data/input"|' airflow/dags/reconstruction_pipeline.py
    sed -i.tmp 's|OUTPUT_DIR = .*|OUTPUT_DIR = "/opt/airflow/data/output"|' airflow/dags/reconstruction_pipeline.py
    rm -f airflow/dags/reconstruction_pipeline.py.tmp
    
    echo -e "${GREEN}Updated DAG file with correct paths.${NC}"
else
    echo -e "${YELLOW}Warning: DAG file not found at airflow/dags/reconstruction_pipeline.py${NC}"
    echo "Manual DAG updates may be needed."
fi

# Create a special helper script for video processing outside of Airflow
echo -e "\n${BLUE}Creating direct frame extraction script...${NC}"

cat > scripts/extract_frames_direct.sh << 'EOF'
#!/bin/bash

# Direct frame extraction script that bypasses Airflow
# Usage: ./scripts/extract_frames_direct.sh path/to/video.mp4 1

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

if [ "$#" -lt 1 ]; then
    echo -e "${RED}Error: Missing video path argument${NC}"
    echo "Usage: $0 path/to/video.mp4 [fps]"
    exit 1
fi

VIDEO_PATH="$1"
FPS="${2:-1}"  # Default to 1 frame per second if not specified

if [ ! -f "$VIDEO_PATH" ]; then
    echo -e "${RED}Error: Video file not found: $VIDEO_PATH${NC}"
    exit 1
fi

# Create output directory
VIDEO_NAME=$(basename "$VIDEO_PATH" | sed 's/\.[^.]*$//')
OUTPUT_DIR="data/input/$VIDEO_NAME"
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}Extracting frames directly using Docker...${NC}"
echo -e "Video: ${YELLOW}$VIDEO_PATH${NC}"
echo -e "Output: ${YELLOW}$OUTPUT_DIR${NC}"
echo -e "Frame rate: ${YELLOW}$FPS fps${NC}"

# Run ffmpeg in Docker to extract frames
docker run --rm -v "$(pwd)/data:/data" jrottenberg/ffmpeg:latest \
    -i "/data/videos/$(basename "$VIDEO_PATH")" \
    -vf "fps=$FPS" \
    "/data/input/$VIDEO_NAME/frame_%04d.jpg"

RESULT=$?
if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}Successfully extracted frames to $OUTPUT_DIR${NC}"
    echo -e "Number of frames: $(ls -1 "$OUTPUT_DIR" | wc -l)"
    
    echo -e "\n${BLUE}To process these frames with COLMAP:${NC}"
    echo -e "1. Go to the Airflow UI: ${YELLOW}http://localhost:8080${NC}"
    echo -e "2. Find the video_to_3d_reconstruction DAG"
    echo -e "3. Click 'Trigger DAG w/ config' and add this config:"
    echo -e "${YELLOW}{\"video_path\": \"/opt/airflow/data/videos/$(basename "$VIDEO_PATH")\"}${NC}"
else
    echo -e "${RED}Failed to extract frames. Error code: $RESULT${NC}"
fi
EOF

chmod +x scripts/extract_frames_direct.sh

# Restart containers to apply changes
echo -e "\n${BLUE}Stopping containers to apply changes...${NC}"
docker-compose down

echo -e "\n${BLUE}Starting containers with updated configurations...${NC}"
docker-compose up -d

# Wait for containers to start
echo -e "${YELLOW}Waiting for containers to start...${NC}"
sleep 10

# Test MinIO connectivity
echo -e "\n${BLUE}Testing MinIO connectivity...${NC}"
if curl -s http://localhost:9001 > /dev/null; then
    echo -e "${GREEN}MinIO UI is accessible at http://localhost:9001${NC}"
else
    echo -e "${RED}MinIO UI is not accessible at http://localhost:9001${NC}"
    echo -e "Checking MinIO logs..."
    docker-compose logs minio | tail -n 20
fi

# Test volume mounting
echo -e "\n${BLUE}Testing volume mounting...${NC}"
# Create test file
echo "test" > data/test_mounting.txt

# Check if test file is accessible in container
if docker ps | grep -q "airflow-webserver"; then
    if docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') cat /opt/airflow/data/test_mounting.txt 2>/dev/null | grep -q "test"; then
        echo -e "${GREEN}Volume mounting is working properly!${NC}"
    else
        echo -e "${RED}Volume mounting is NOT working properly.${NC}"
        echo -e "Creating direct path in container..."
        docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') mkdir -p /opt/airflow/data
        docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') chmod 777 /opt/airflow/data
    fi
else
    echo -e "${RED}Airflow webserver is not running.${NC}"
fi

# Clean up test file
rm -f data/test_mounting.txt

echo -e "\n${BLUE}===============================================${NC}"
echo -e "${GREEN}MinIO and frame extraction fix completed!${NC}"
echo -e "${BLUE}===============================================${NC}"
echo -e "\n${YELLOW}How to use:${NC}"
echo -e "1. Place your videos in the ${BLUE}data/videos${NC} directory"
echo -e "2. Run the direct frame extraction script:"
echo -e "   ${YELLOW}./scripts/extract_frames_direct.sh data/videos/your_video.mp4${NC}"
echo -e "3. Access MinIO at: ${BLUE}http://localhost:9001${NC}"
echo -e "   Username: ${BLUE}minioadmin${NC}, Password: ${BLUE}minioadmin${NC}"
echo -e "4. Access Airflow at: ${BLUE}http://localhost:8080${NC}"
echo -e "   Username: ${BLUE}admin${NC}, Password: ${BLUE}admin${NC}"
echo -e ""
echo -e "${YELLOW}If MinIO still isn't accessible, try these alternative URLs:${NC}"
echo -e "- ${BLUE}http://127.0.0.1:9001${NC}"
echo -e "- ${BLUE}http://[your-machine-ip]:9001${NC}" 