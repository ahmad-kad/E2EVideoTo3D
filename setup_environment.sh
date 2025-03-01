#!/bin/bash
set -e

MESHROOM_VERSION="2021.1.0"

# Check if NVIDIA GPU is available
if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected, setting up GPU environment..."
    
    # Check if the GPU version of Meshroom is already downloaded
    if [ ! -f "/usr/local/bin/meshroom_batch_gpu" ]; then
        echo "Downloading GPU version of Meshroom..."
        cd /opt/meshroom
        # Try to download CUDA version if available
        if wget -q --spider "https://github.com/alicevision/meshroom/releases/download/v${MESHROOM_VERSION}/Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz"; then
            wget -q "https://github.com/alicevision/meshroom/releases/download/v${MESHROOM_VERSION}/Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz"
            tar -xzf Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz
            rm Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz
            ln -s /opt/meshroom/Meshroom-${MESHROOM_VERSION}-cuda10/meshroom_batch /usr/local/bin/meshroom_batch_gpu
        else
            echo "GPU version not found, falling back to CPU version for GPU operations"
            ln -s /usr/local/bin/meshroom_batch_cpu /usr/local/bin/meshroom_batch_gpu
        fi
    fi
    
    # Set GPU environment variables
    export USE_GPU=1
    export MESHROOM_BINARY="meshroom_batch_gpu"
else
    echo "No NVIDIA GPU detected, using CPU mode..."
    export USE_GPU=0
    export MESHROOM_BINARY="meshroom_batch_cpu"
fi

echo "Environment setup complete"
exec "$@"