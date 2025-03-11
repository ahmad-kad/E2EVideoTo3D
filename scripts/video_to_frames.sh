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