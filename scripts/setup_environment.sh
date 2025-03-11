#!/bin/bash
set -e

# Detect architecture
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

# Set appropriate platform
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    echo "Setting up for ARM64 architecture (Apple Silicon)..."
    export DOCKER_PLATFORM="linux/arm64"
    export BASE_IMAGE="ubuntu:20.04"
elif [ "$ARCH" = "x86_64" ]; then
    echo "Setting up for x86_64 architecture..."
    export DOCKER_PLATFORM="linux/amd64"
    export BASE_IMAGE="ubuntu:20.04"
else
    echo "Warning: Unrecognized architecture: $ARCH"
    echo "Defaulting to linux/amd64..."
    export DOCKER_PLATFORM="linux/amd64"
    export BASE_IMAGE="ubuntu:20.04"
fi

# Detect if NVIDIA GPU is available
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected."
    export HAS_NVIDIA_GPU=true
    export USE_GPU=true
    
    if [ "$ARCH" = "x86_64" ]; then
        export BASE_IMAGE="nvidia/cuda:11.7.1-cudnn8-devel-ubuntu20.04"
    else
        echo "Warning: NVIDIA GPU detected but architecture is not x86_64."
        echo "Using standard Ubuntu image instead of CUDA image."
    fi
else
    echo "No NVIDIA GPU detected."
    export HAS_NVIDIA_GPU=false
    export USE_GPU=false
fi

# Create .env file for docker-compose to use
cat > .env << EOL
DOCKER_PLATFORM=${DOCKER_PLATFORM}
BASE_IMAGE=${BASE_IMAGE}
USE_GPU=${USE_GPU}
EOL

echo "Created .env file with the following settings:"
cat .env

echo "Environment setup complete. Now run:"
echo "  docker-compose down"
echo "  docker-compose build --no-cache photogrammetry"
echo "  docker-compose up -d" 