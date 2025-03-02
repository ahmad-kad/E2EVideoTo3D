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

# Verify Meshroom is available and fix symbolic links if needed
echo "Checking Meshroom installation..."

# Always recreate Meshroom symlinks to ensure they're correct
echo "Setting up Meshroom symbolic links..."
# Find Meshroom installation directory
MESHROOM_DIR=$(find /opt/meshroom -type d -name "Meshroom*" | head -n 1)

if [ -n "$MESHROOM_DIR" ]; then
    echo "Found Meshroom directory: $MESHROOM_DIR"
    
    # Check if meshroom_batch exists
    if [ -f "${MESHROOM_DIR}/meshroom_batch" ]; then
        echo "Creating symbolic links for Meshroom executables..."
        ln -sf "${MESHROOM_DIR}/meshroom_batch" /usr/local/bin/meshroom_batch
        ln -sf "${MESHROOM_DIR}/meshroom_batch" /usr/local/bin/meshroom_batch_cpu
        echo "Meshroom symbolic links created:"
        ls -la /usr/local/bin/meshroom_batch*
        
        # Test Meshroom availability
        echo "Testing Meshroom installation:"
        if /usr/local/bin/meshroom_batch --help > /dev/null; then
            echo "✅ Meshroom is properly installed and working"
        else
            echo "⚠️ Meshroom installation check failed. Please check the logs."
        fi
    else
        echo "❌ ERROR: meshroom_batch not found in ${MESHROOM_DIR}"
        echo "Searching for meshroom_batch in entire /opt directory..."
        MESHROOM_PATH=$(find /opt -name "meshroom_batch" -type f | head -n 1)
        
        if [ -n "$MESHROOM_PATH" ]; then
            echo "Found alternative Meshroom location: $MESHROOM_PATH"
            ln -sf "$MESHROOM_PATH" /usr/local/bin/meshroom_batch
            ln -sf "$MESHROOM_PATH" /usr/local/bin/meshroom_batch_cpu
            echo "Created alternative symbolic links"
        else
            echo "❌ ERROR: Could not find meshroom_batch executable anywhere in /opt"
        fi
    fi
else
    echo "❌ ERROR: Meshroom directory not found in /opt/meshroom"
    echo "Available content in /opt/meshroom:"
    ls -la /opt/meshroom || echo "Directory doesn't exist"
fi

# Create necessary directories
mkdir -p /app/logs

# Execute the provided command or default command
echo "Environment setup complete. Starting application..."
exec "$@"