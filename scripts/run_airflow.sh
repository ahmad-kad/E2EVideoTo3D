#!/bin/bash
# Script to run Airflow for testing the ETL pipeline with MinIO and Spark

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the root project directory
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Starting ETL pipeline services..."

# Create required directories
mkdir -p "$PROJECT_DIR/airflow/logs"
mkdir -p "$PROJECT_DIR/airflow/plugins"
mkdir -p "$PROJECT_DIR/airflow/jobs"
mkdir -p "$PROJECT_DIR/spark-jobs"

# Copy Spark job to Airflow jobs directory
cp -f "$PROJECT_DIR/spark-jobs/process_models.py" "$PROJECT_DIR/airflow/jobs/"
chmod +x "$PROJECT_DIR/airflow/jobs/process_models.py"

# Check if Docker Compose file exists
if [ ! -f "$PROJECT_DIR/docker-compose-airflow.yml" ]; then
    echo "Error: docker-compose-airflow.yml not found!"
    exit 1
fi

# Check Docker version and compatibility
DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
echo "Using Docker version: $DOCKER_VERSION"

# Check if Docker Compose V2 is being used
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
    echo "Using Docker Compose V2"
else
    COMPOSE_CMD="docker-compose"
    echo "Using Docker Compose V1"
fi

# Check if the e2e3d-reconstruction Docker image exists
if ! docker image inspect e2e3d-reconstruction >/dev/null 2>&1; then
    echo "Warning: e2e3d-reconstruction Docker image not found."
    echo "You need to build it first using scripts/build_reconstruction_image.sh"
    read -p "Do you want to build it now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        "$PROJECT_DIR/scripts/build_reconstruction_image.sh"
    else
        echo "Please build the e2e3d-reconstruction image before running Airflow."
        exit 1
    fi
fi

# Detect architecture for potential troubleshooting
ARCH=$(uname -m)
echo "Running on architecture: $ARCH"

# Stop any existing services
echo "Stopping any existing services..."
cd "$PROJECT_DIR"
$COMPOSE_CMD -f docker-compose-airflow.yml down

# Set AIRFLOW_UID environment variable if not already set
# This is important for file permissions in mounted volumes
export AIRFLOW_UID=${AIRFLOW_UID:-$(id -u)}
export AIRFLOW_GID=${AIRFLOW_GID:-$(id -g)}
echo "Using AIRFLOW_UID=$AIRFLOW_UID, AIRFLOW_GID=$AIRFLOW_GID"

# Start services
echo "Starting services..."
$COMPOSE_CMD -f docker-compose-airflow.yml up -d

# Wait for the webserver to be ready
echo "Waiting for Airflow webserver to start..."
MAX_RETRIES=60
RETRY_INTERVAL=5
retries=0

while ! curl -s "http://localhost:8080/health" >/dev/null; do
    ((retries++))
    if [ $retries -ge $MAX_RETRIES ]; then
        echo "Error: Airflow webserver failed to start after $((MAX_RETRIES * RETRY_INTERVAL)) seconds"
        echo "Showing logs for troubleshooting:"
        $COMPOSE_CMD -f docker-compose-airflow.yml logs airflow-webserver | tail -n 50
        exit 1
    fi
    echo "Waiting for Airflow webserver to start... ($retries/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

echo "Airflow webserver is running!"

# Set up Spark connection in Airflow
echo "Setting up Spark connection in Airflow..."
$COMPOSE_CMD -f docker-compose-airflow.yml exec airflow-webserver airflow connections add 'spark_default' \
    --conn-type 'spark' \
    --conn-host 'spark://spark-master' \
    --conn-port '7077' \
    --conn-extra '{"queue": "default"}'

# Final instructions
echo ""
echo "===================== ETL Pipeline is Ready! ====================="
echo "Web UIs:"
echo "  Airflow:  http://localhost:8080  (Username: airflow, Password: airflow)"
echo "  MinIO:    http://localhost:9001  (Username: minioadmin, Password: minioadmin)"
echo "  Spark:    http://localhost:8090"
echo ""
echo "To trigger the ETL pipeline manually, run:"
echo "$COMPOSE_CMD -f docker-compose-airflow.yml exec airflow-webserver airflow dags trigger e2e3d_etl_pipeline"
echo ""
echo "To stop all services, run:"
echo "$COMPOSE_CMD -f docker-compose-airflow.yml down"
echo "==================================================================" 