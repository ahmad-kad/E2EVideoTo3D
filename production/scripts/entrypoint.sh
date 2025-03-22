#!/bin/bash
set -e

# Output colorization
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[E2E3D] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[E2E3D] $1${NC}"
}

error() {
    echo -e "${RED}[E2E3D] $1${NC}"
}

# Display welcome banner
info "Initializing environment..."
info "Running on platform: $(uname -sm)"

# Detect GPU availability
if [ -f "/usr/local/bin/detect_gpu.sh" ]; then
    source /usr/local/bin/detect_gpu.sh
elif [ -x "$(command -v nvidia-smi)" ]; then
    info "NVIDIA GPU detected"
    export USE_GPU=true
    export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
else
    warn "No GPU detected - using CPU mode"
    export USE_GPU=false
fi

# Ensure directories exist
info "Ensuring standard directories exist..."
mkdir -p /app/data/input
mkdir -p /app/data/output
mkdir -p /app/logs

# Set up logs
LOGDIR="/app/logs"
mkdir -p $LOGDIR

# Check for Python dependencies
info "Checking reconstruction dependencies..."
if ! python -c "import numpy" &>/dev/null; then
    error "Numpy is not installed"
    exit 1
fi

if ! python -c "import PIL" &>/dev/null; then
    warn "PIL is not installed but will be needed for image processing"
fi

if ! python -c "import open3d" &>/dev/null; then
    warn "Open3D is not installed but will be needed for mesh generation"
fi

# Set up environment variables
export PYTHONPATH="${PYTHONPATH}:/app"
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export MAX_WORKERS=${MAX_WORKERS:-4}

# Set up metrics if enabled
if [ "$ENABLE_METRICS" = "true" ]; then
    # Check if port is already in use
    if ! nc -z localhost 9101 2>/dev/null; then
        info "Enabling Prometheus metrics on port 9101"
        python -m prometheus_client.exposition > $LOGDIR/metrics.log 2>&1 &
        METRICS_PID=$!
        info "Metrics server started with PID $METRICS_PID"
        # Export variable to signal that metrics server is started
        export METRICS_SERVER_STARTED=true
    else
        info "Metrics server already running on port 9101"
        export METRICS_SERVER_STARTED=true
    fi
else
    export METRICS_SERVER_STARTED=false
fi

# Print environment summary
echo "========================================"
echo "E2E3D Environment Summary"
echo "========================================"
echo "Platform: $(uname -sm)"
echo "GPU support: $USE_GPU"
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Metrics enabled: ${ENABLE_METRICS:-false}"
echo "Log level: $LOG_LEVEL"
echo "Max workers: $MAX_WORKERS"
echo "========================================"

# Execute the provided command
info "Starting application..."
exec "$@" 