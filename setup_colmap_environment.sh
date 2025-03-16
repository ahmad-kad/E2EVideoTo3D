#!/bin/bash
# Setup script for configuring the environment to use the COLMAP Docker image

# Stop script if any command fails
set -e

echo "Setting up COLMAP Docker environment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    touch .env
fi

# Update or add USE_COLMAP_DOCKER setting in .env
if grep -q "USE_COLMAP_DOCKER" .env; then
    # Replace existing setting
    sed -i '' 's/USE_COLMAP_DOCKER=.*/USE_COLMAP_DOCKER=true/g' .env || \
    sed -i 's/USE_COLMAP_DOCKER=.*/USE_COLMAP_DOCKER=true/g' .env
else
    # Add new setting
    echo "USE_COLMAP_DOCKER=true" >> .env
fi

# Update or add COLMAP_DOCKER_SERVICE setting in .env
if grep -q "COLMAP_DOCKER_SERVICE" .env; then
    # Replace existing setting
    sed -i '' 's/COLMAP_DOCKER_SERVICE=.*/COLMAP_DOCKER_SERVICE=colmap/g' .env || \
    sed -i 's/COLMAP_DOCKER_SERVICE=.*/COLMAP_DOCKER_SERVICE=colmap/g' .env
else
    # Add new setting
    echo "COLMAP_DOCKER_SERVICE=colmap" >> .env
fi

# Update COLMAP_PATH to the path in the Docker container
if grep -q "COLMAP_PATH" .env; then
    # Replace existing setting
    sed -i '' 's|COLMAP_PATH=.*|COLMAP_PATH=/usr/bin/colmap|g' .env || \
    sed -i 's|COLMAP_PATH=.*|COLMAP_PATH=/usr/bin/colmap|g' .env
else
    # Add new setting
    echo "COLMAP_PATH=/usr/bin/colmap" >> .env
fi

# Set AIRFLOW_TEST_MODE to false
if grep -q "AIRFLOW_TEST_MODE" .env; then
    # Replace existing setting
    sed -i '' 's/AIRFLOW_TEST_MODE=.*/AIRFLOW_TEST_MODE=false/g' .env || \
    sed -i 's/AIRFLOW_TEST_MODE=.*/AIRFLOW_TEST_MODE=false/g' .env
else
    # Add new setting
    echo "AIRFLOW_TEST_MODE=false" >> .env
fi

# Pull the COLMAP Docker image
echo "Pulling COLMAP Docker image..."
docker pull colmap/colmap:latest

# Create necessary directories
echo "Creating required directories..."
mkdir -p data/input
mkdir -p data/output
mkdir -p data/videos

# Set correct permissions
echo "Setting permissions on data directories..."
chmod -R 755 data

echo "COLMAP environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Place videos in the 'data/videos' directory"
echo "2. Run 'docker-compose up -d' to start Airflow"
echo "3. Access the Airflow UI at http://localhost:8080"
echo "4. Trigger the 'reconstruction_pipeline' DAG to start processing"
echo ""
echo "The pipeline will now use the COLMAP Docker image for all COLMAP operations." 