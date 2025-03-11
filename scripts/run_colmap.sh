#!/bin/bash
set -e

# Default paths
INPUT_PATH=${INPUT_PATH:-/app/data/input}
OUTPUT_PATH=${OUTPUT_PATH:-/app/data/output}
WORKSPACE_PATH=${OUTPUT_PATH}/colmap_workspace

# Check if GPU should be used
USE_GPU=${USE_GPU:-false}

# Auto-detect NVIDIA GPU if not explicitly set
if [ "$USE_GPU" = "auto" ]; then
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        USE_GPU=true
        echo "NVIDIA GPU detected. Using GPU acceleration."
    else
        USE_GPU=false
        echo "No NVIDIA GPU detected. Using CPU mode."
    fi
fi

# Set GPU flags based on USE_GPU value
if [ "$USE_GPU" = "true" ]; then
    GPU_EXTRACTION_FLAG="1"
    GPU_MATCHING_FLAG="1"
    GPU_INDEX="0"
    echo "Running COLMAP with GPU acceleration"
else
    GPU_EXTRACTION_FLAG="0"
    GPU_MATCHING_FLAG="0"
    GPU_INDEX="-1"
    echo "Running COLMAP with CPU only"
fi

# Create workspace directories
mkdir -p "${WORKSPACE_PATH}"
mkdir -p "${WORKSPACE_PATH}/database"
mkdir -p "${WORKSPACE_PATH}/sparse"
mkdir -p "${WORKSPACE_PATH}/dense"

# Define paths
DATABASE_PATH="${WORKSPACE_PATH}/database/database.db"
SPARSE_PATH="${WORKSPACE_PATH}/sparse"
DENSE_PATH="${WORKSPACE_PATH}/dense"

echo "Starting COLMAP processing pipeline..."
echo "Input path: ${INPUT_PATH}"
echo "Output path: ${OUTPUT_PATH}"

# Feature extraction
echo "Step 1: Feature extraction..."
colmap feature_extractor \
    --database_path "${DATABASE_PATH}" \
    --image_path "${INPUT_PATH}" \
    --ImageReader.camera_model SIMPLE_RADIAL \
    --SiftExtraction.use_gpu ${GPU_EXTRACTION_FLAG}

# Feature matching
echo "Step 2: Feature matching..."
colmap exhaustive_matcher \
    --database_path "${DATABASE_PATH}" \
    --SiftMatching.use_gpu ${GPU_MATCHING_FLAG}

# Sparse reconstruction (Structure from Motion)
echo "Step 3: Sparse reconstruction..."
mkdir -p "${SPARSE_PATH}/0"
colmap mapper \
    --database_path "${DATABASE_PATH}" \
    --image_path "${INPUT_PATH}" \
    --output_path "${SPARSE_PATH}"

# Check if sparse reconstruction succeeded
if [ ! -f "${SPARSE_PATH}/0/cameras.bin" ]; then
    echo "Sparse reconstruction failed. Exiting."
    exit 1
fi

# Image undistortion for dense reconstruction
echo "Step 4: Image undistortion..."
colmap image_undistorter \
    --image_path "${INPUT_PATH}" \
    --input_path "${SPARSE_PATH}/0" \
    --output_path "${DENSE_PATH}" \
    --output_type COLMAP

# Dense reconstruction (patch matching and stereo fusion)
echo "Step 5: Patch match stereo..."
colmap patch_match_stereo \
    --workspace_path "${DENSE_PATH}" \
    --workspace_format COLMAP \
    --PatchMatchStereo.gpu_index ${GPU_INDEX}

# Stereo fusion
echo "Step 6: Stereo fusion..."
colmap stereo_fusion \
    --workspace_path "${DENSE_PATH}" \
    --workspace_format COLMAP \
    --input_type geometric \
    --output_path "${DENSE_PATH}/fused.ply"

# Meshing (optional)
echo "Step 7: Meshing..."
colmap poisson_mesher \
    --input_path "${DENSE_PATH}/fused.ply" \
    --output_path "${DENSE_PATH}/meshed.ply"

# Texture mapping (optional)
echo "Step 8: Texture mapping..."
colmap model_converter \
    --input_path "${SPARSE_PATH}/0" \
    --output_path "${SPARSE_PATH}/0" \
    --output_type TXT

colmap model_converter \
    --input_path "${SPARSE_PATH}/0" \
    --output_path "${WORKSPACE_PATH}/model-normalized.ply" \
    --output_type PLY

echo "COLMAP processing completed!"
echo "Output files are in ${OUTPUT_PATH}"

# Keep container running if in interactive mode
if [ "$1" = "interactive" ]; then
    echo "Running in interactive mode. Press Ctrl+C to exit."
    tail -f /dev/null
fi 