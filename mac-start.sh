#!/bin/bash
set -e

echo "=== E2E3D Mac Startup Helper ==="
echo "Setting up Docker environment for macOS..."

# Set the Docker build platform to linux/amd64 for better compatibility
export BUILDPLATFORM=linux/amd64
export COMPOSE_DOCKER_CLI_BUILD_PLATFORM=linux/amd64

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker not found. Please install Docker Desktop for Mac."
    echo "Visit: https://docs.docker.com/desktop/install/mac-install/"
    exit 1
fi

echo "✅ Docker installation found"

# Check Docker is running
if ! docker info &> /dev/null; then
    echo "❌ ERROR: Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Ensure proper file permissions
chmod +x setup_environment.sh

# Build containers with platform specifics
echo "Building containers (this may take some time)..."
docker-compose build --build-arg BUILDPLATFORM=linux/amd64

# Start the services
echo "Starting services..."
docker-compose up -d

echo "✅ Services started. You can access the following endpoints:"
echo "- Airflow Webserver: http://localhost:8080"
echo "- MinIO Console: http://localhost:9001 (login: minioadmin/minioadmin)"
echo "- Spark Master UI: http://localhost:8001"

echo ""
echo "To view container logs:"
echo "docker-compose logs -f <service_name>"
echo ""
echo "To stop all services:"
echo "docker-compose down"

exit 0 