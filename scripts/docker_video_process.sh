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