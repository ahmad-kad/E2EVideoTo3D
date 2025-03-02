#!/bin/bash
set -e

echo "Initializing environment..."

# Check if CUDA is available
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected - using GPU acceleration."
    export CUDA_VISIBLE_DEVICES=0
    
    # Install CUDA packages if needed
    if ! pip3 list | grep -q "torch"; then
        echo "Installing PyTorch with CUDA support..."
        pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    fi
else
    echo "No NVIDIA GPU detected - using CPU mode."
    export CUDA_VISIBLE_DEVICES=""
fi

# Configure MinIO client
if [ ! -f "/root/.mc/config.json" ]; then
    echo "Configuring MinIO client..."
    mc config host add myminio http://minio:9000 minioadmin minioadmin
fi

# Verify Meshroom is available
if command -v meshroom_batch &> /dev/null; then
    echo "Meshroom found at: $(which meshroom_batch)"
else
    echo "WARNING: Meshroom not found in PATH. Checking installation..."
    
    # Try to locate Meshroom executable
    MESHROOM_PATH=$(find /opt/meshroom -name "meshroom_batch" -type f | head -n 1)
    
    if [ -n "$MESHROOM_PATH" ]; then
        echo "Found Meshroom at: $MESHROOM_PATH"
        echo "Creating symlink..."
        ln -sf "$MESHROOM_PATH" /usr/local/bin/meshroom_batch
        ln -sf "$MESHROOM_PATH" /usr/local/bin/meshroom_batch_cpu
    else
        echo "ERROR: Meshroom executable not found. Please check installation."
    fi
fi

# Create necessary directories
mkdir -p /app/logs

# Execute the provided command or default command
exec "$@"