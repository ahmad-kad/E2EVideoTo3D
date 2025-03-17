#!/bin/bash
# Script to build the reconstruction Docker image

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the root project directory
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Building e2e3d-reconstruction Docker image..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in your PATH"
    exit 1
fi

# Make sure Dockerfile exists
mkdir -p "$PROJECT_DIR/docker/e2e3d-reconstruction"
DOCKERFILE="$PROJECT_DIR/docker/e2e3d-reconstruction/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
    echo "Error: Dockerfile not found at $DOCKERFILE"
    exit 1
fi

# Detect platform and set appropriate flags
PLATFORM=$(uname -m)
PLATFORM_FLAGS=""

# Check if we're on ARM architecture
if [[ "$PLATFORM" == "arm64" || "$PLATFORM" == "aarch64" ]]; then
    echo "Detected ARM64 architecture, building with platform compatibility..."
    read -p "Build for native ARM64 only (y) or build for multi-platform x86_64/ARM64 (n)? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Build for native ARM64 only
        PLATFORM_FLAGS="--platform=linux/arm64"
        echo "Building for ARM64 platform only"
    else
        # For multi-platform, we'll use the buildx plugin
        echo "Building for multi-platform compatibility..."
        
        # Check if buildx plugin is available
        if ! docker buildx version &> /dev/null; then
            echo "Docker buildx not available. Please install it first."
            echo "See: https://docs.docker.com/buildx/working-with-buildx/"
            exit 1
        fi
        
        # Ensure we have a builder that supports multi-platform builds
        docker buildx create --name multiplatform-builder --use || true
        
        # Build and push to local Docker daemon
        echo "Building multi-platform image (this may take longer)..."
        docker buildx build \
            --platform linux/amd64,linux/arm64 \
            --tag e2e3d-reconstruction \
            --load \
            -f "$DOCKERFILE" \
            "$PROJECT_DIR"
        
        echo "Multi-platform image built successfully!"
        exit 0
    fi
else
    echo "Detected x86_64 architecture, using default build process"
fi

# Standard build process
echo "Building Docker image with tag: e2e3d-reconstruction"
docker build $PLATFORM_FLAGS \
    -t e2e3d-reconstruction \
    -f "$DOCKERFILE" \
    "$PROJECT_DIR"

# Check if the build was successful
if [ $? -eq 0 ]; then
    echo "Docker image built successfully!"
else
    echo "Error: Failed to build Docker image"
    exit 1
fi 