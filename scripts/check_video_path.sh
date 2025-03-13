#!/bin/bash

# Script to check video file paths and diagnose Docker volume mounting issues

echo "=== Video Path Checker Tool ==="
echo "This script will help you verify your video files are properly accessible to the Airflow container."

# 1. Check if the videos directory exists locally
if [ -d "data/videos" ]; then
    echo "✅ Local data/videos directory exists"
    
    # List video files in the directory
    VIDEO_COUNT=$(find data/videos -type f -name "*.mp4" -o -name "*.mov" -o -name "*.avi" | wc -l)
    
    if [ $VIDEO_COUNT -gt 0 ]; then
        echo "✅ Found $VIDEO_COUNT video files in data/videos:"
        find data/videos -type f -name "*.mp4" -o -name "*.mov" -o -name "*.avi"
    else
        echo "❌ No video files found in data/videos directory"
        echo "   Please copy your video files to the data/videos directory"
    fi
else
    echo "❌ Local data/videos directory doesn't exist"
    echo "   Creating directory now..."
    mkdir -p data/videos
    echo "✅ Created data/videos directory"
    echo "   Please copy your video files to this directory"
fi

# 2. Check Docker container access
echo -e "\n=== Checking Docker Container Access ==="

# Check if Docker is running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker command not found. Please make sure Docker is installed."
    exit 1
fi

# Check if containers are running
AIRFLOW_RUNNING=$(docker ps | grep airflow-webserver | wc -l)

if [ $AIRFLOW_RUNNING -eq 0 ]; then
    echo "❌ Airflow container is not running"
    echo "   Please start the containers with: docker-compose up -d"
    exit 1
fi

echo "✅ Airflow container is running"

# Check if videos directory is accessible in container
echo -e "\n=== Checking video directory in Airflow container ==="
docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') bash -c "
    echo 'Inside Airflow container:'
    
    # Check if the directory exists
    if [ -d /opt/airflow/data/videos ]; then
        echo '✅ /opt/airflow/data/videos directory exists in container'
        
        # List files
        VIDEO_COUNT=\$(find /opt/airflow/data/videos -type f -name \"*.mp4\" -o -name \"*.mov\" -o -name \"*.avi\" | wc -l)
        
        if [ \$VIDEO_COUNT -gt 0 ]; then
            echo '✅ Found \$VIDEO_COUNT video files in container:'
            find /opt/airflow/data/videos -type f -name \"*.mp4\" -o -name \"*.mov\" -o -name \"*.avi\"
        else
            echo '❌ No video files found in container'
            echo '   Container directory exists but has no video files'
            ls -la /opt/airflow/data/videos
        fi
    else
        echo '❌ /opt/airflow/data/videos directory does not exist in container'
        echo '   Checking parent directory...'
        
        if [ -d /opt/airflow/data ]; then
            echo '✅ /opt/airflow/data directory exists. Contents:'
            ls -la /opt/airflow/data
        else
            echo '❌ /opt/airflow/data directory does not exist'
            echo '   Volume may not be mounted correctly'
        fi
    fi
"

echo -e "\n=== Recommendations ==="

if [ $VIDEO_COUNT -eq 0 ]; then
    echo "1. Copy a video file to the data/videos directory:"
    echo "   cp /path/to/your/video.mp4 data/videos/"
    echo ""
fi

echo "2. Ensure proper permissions:"
echo "   chmod -R 755 data/videos"
echo ""

echo "3. Restart Docker containers to ensure volumes are properly mounted:"
echo "   docker-compose down"
echo "   docker-compose up -d"
echo ""

echo "4. When triggering the DAG, you can manually specify the video path:"
echo "   - Go to Airflow UI (http://localhost:8080)"
echo "   - Find the 'video_to_3d_reconstruction' DAG"
echo "   - Click 'Trigger DAG w/ config'"
echo "   - Add JSON configuration: {\"video_path\": \"/opt/airflow/data/videos/your_video.mp4\"}"
echo ""

echo "5. If you need to completely shut down the system:"
echo "   ./scripts/shutdown.sh"
echo "   (This will gracefully stop all components and clean up resources)"
echo ""

echo "=== Diagnostics Complete ==="