#!/bin/bash
# Script to detect if GPU is available for CUDA processing

# Default to false
GPU_AVAILABLE=1

# Check platform
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ]; then
    echo "Architecture is $ARCH, not x86_64. CUDA not supported."
    exit $GPU_AVAILABLE
fi

# Try NVIDIA GPU detection
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi -L &> /dev/null; then
        echo "NVIDIA GPU detected via nvidia-smi"
        GPU_AVAILABLE=0
        exit $GPU_AVAILABLE
    fi
fi

# Try to detect CUDA via py-torch
if command -v python3 &> /dev/null; then
    if python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null | grep -q "True"; then
        echo "CUDA detected via PyTorch"
        GPU_AVAILABLE=0
        exit $GPU_AVAILABLE
    fi
fi

# No GPU available
echo "No CUDA-enabled GPU detected"
exit $GPU_AVAILABLE 