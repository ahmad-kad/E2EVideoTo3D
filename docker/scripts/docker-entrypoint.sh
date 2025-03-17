#!/bin/bash
set -e

echo "Initializing environment..."

# Get OS platform
PLATFORM=$(uname -s)
ARCH=$(uname -m)
echo "Running on platform: $PLATFORM $ARCH"

# Check if CUDA is available
if /usr/local/bin/detect_gpu.sh; then
    echo "GPU detected - using GPU acceleration"
    export USE_GPU=true
else
    echo "No GPU detected - using CPU mode"
    export USE_GPU=false
fi

# Check for reconstruction dependencies
echo "Checking reconstruction dependencies..."

# Check for Open3D
if pip3 list | grep -q "open3d"; then
    echo "✅ Open3D is installed"
else
    echo "⚠️ Open3D is not installed but will be needed for mesh generation"
fi

# Create standard directories if they don't exist
echo "Ensuring standard directories exist..."
mkdir -p /app/data/input
mkdir -p /app/data/output
mkdir -p /app/data/videos
mkdir -p /app/logs

# Print environment summary
echo "========================================"
echo "E2E3D Environment Summary"
echo "========================================"
echo "Platform: $PLATFORM $ARCH"
echo "GPU support: $USE_GPU"
echo "Python version: $(python3 --version)"
echo "Working directory: $(pwd)"
echo "========================================"

# Execute the provided command or default command
echo "Starting application..."
exec "$@" 