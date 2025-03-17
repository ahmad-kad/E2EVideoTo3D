#!/bin/bash
# Setup and run the complete ETL pipeline
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the root project directory
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Print colored messages
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# Checking prerequisites
print_info "Checking prerequisites..."

# Check Docker installation
if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    print_info "Visit https://docs.docker.com/get-docker/ for installation instructions."
    exit 1
fi

# Check Docker Compose
if command_exists docker-compose; then
    COMPOSE_CMD="docker-compose"
    print_info "Using Docker Compose V1"
elif command_exists "docker" && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    print_info "Using Docker Compose V2"
else
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    print_info "Visit https://docs.docker.com/compose/install/ for installation instructions."
    exit 1
fi

# Check architecture
ARCH=$(uname -m)
print_info "Detected architecture: $ARCH"
if [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
    print_info "Running on ARM64 architecture (e.g., Apple Silicon Mac)"
    # Update .env file for ARM64
    sed -i.bak 's/DOCKER_PLATFORM=.*/DOCKER_PLATFORM=linux\/arm64/' "$PROJECT_DIR/.env" || true
else
    print_info "Running on x86_64 architecture"
    # Update .env file for x86_64
    sed -i.bak 's/DOCKER_PLATFORM=.*/DOCKER_PLATFORM=linux\/amd64/' "$PROJECT_DIR/.env" || true
fi

# Check and create directory structure
print_info "Setting up directory structure..."
mkdir -p "$PROJECT_DIR/data/input"
mkdir -p "$PROJECT_DIR/data/output"
mkdir -p "$PROJECT_DIR/airflow/logs"
mkdir -p "$PROJECT_DIR/airflow/dags"
mkdir -p "$PROJECT_DIR/airflow/plugins"
mkdir -p "$PROJECT_DIR/airflow/jobs"
mkdir -p "$PROJECT_DIR/spark-jobs"

# Check for sample data
print_info "Checking for sample data..."
if [ -d "$PROJECT_DIR/data/input/CognacStJacquesDoor" ] || [ -d "$PROJECT_DIR/data/input/FrameSequence" ]; then
    print_info "Sample data found."
else
    print_warning "No sample data found in data/input directory."
    print_info "You need image sets to process. You can download sample data."
    
    read -p "Do you want to download sample data? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Downloading sample data (this may take a while)..."
        if [ -f "$PROJECT_DIR/scripts/download_sample_data.py" ]; then
            python "$PROJECT_DIR/scripts/download_sample_data.py"
        else
            print_error "Sample data download script not found."
            print_info "Please manually add image sets to the data/input directory."
        fi
    else
        print_info "Skipping sample data download. Please add your own image sets to data/input directory."
    fi
fi

# Build reconstruction image if not exists
print_info "Checking for e2e3d-reconstruction Docker image..."
if ! docker image inspect e2e3d-reconstruction >/dev/null 2>&1; then
    print_warning "e2e3d-reconstruction Docker image not found."
    print_info "Building the reconstruction image (this may take a while)..."
    bash "$PROJECT_DIR/scripts/build_reconstruction_image.sh"
else
    print_info "e2e3d-reconstruction Docker image found."
fi

# Stop any running containers
print_info "Stopping any running services..."
cd "$PROJECT_DIR"
$COMPOSE_CMD -f docker-compose-airflow.yml down

# Start services
print_info "Starting ETL pipeline services..."
cd "$PROJECT_DIR"
$COMPOSE_CMD -f docker-compose-airflow.yml up -d

# Wait for the webserver to be ready
print_info "Waiting for Airflow webserver to start..."
MAX_RETRIES=60
RETRY_INTERVAL=5
retries=0

while ! curl -s "http://localhost:8080/health" >/dev/null 2>&1; do
    ((retries++))
    if [ $retries -ge $MAX_RETRIES ]; then
        print_error "Airflow webserver failed to start after $((MAX_RETRIES * RETRY_INTERVAL)) seconds"
        print_info "Showing logs for troubleshooting:"
        $COMPOSE_CMD -f docker-compose-airflow.yml logs airflow-webserver | tail -n 50
        exit 1
    fi
    echo "Waiting... ($retries/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

# Set up Spark connection in Airflow
print_info "Setting up Spark connection in Airflow..."
$COMPOSE_CMD -f docker-compose-airflow.yml exec airflow-webserver airflow connections add 'spark_default' \
    --conn-type 'spark' \
    --conn-host 'spark://spark-master' \
    --conn-port '7077' \
    --conn-extra '{"queue": "default"}' || true

print_info "Checking if DAG file exists..."
if [ ! -f "$PROJECT_DIR/airflow/dags/multi_reconstruction_dag.py" ]; then
    print_warning "DAG file not found, creating symbolic link..."
    ln -sf "$PROJECT_DIR/airflow/dags/multi_reconstruction_dag.py" "$PROJECT_DIR/airflow/dags/"
fi

# Final instructions
print_success "ETL Pipeline is Ready!"
echo ""
echo "======================= ETL Pipeline Setup Complete ======================="
echo "Web UIs:"
echo "  Airflow:  http://localhost:8080  (Username: airflow, Password: airflow)"
echo "  MinIO:    http://localhost:9001  (Username: minioadmin, Password: minioadmin)"
echo "  Spark:    http://localhost:8090"
echo ""
echo "To trigger the ETL pipeline manually, run:"
echo "$COMPOSE_CMD -f docker-compose-airflow.yml exec airflow-webserver airflow dags trigger e2e3d_etl_pipeline"
echo ""
echo "To monitor the pipeline execution:"
echo "1. Go to Airflow web UI: http://localhost:8080"
echo "2. Login with username 'airflow' and password 'airflow'"
echo "3. Click on the 'e2e3d_etl_pipeline' DAG"
echo "4. Click on 'Graph View' to visualize the pipeline execution"
echo ""
echo "To stop all services, run:"
echo "$COMPOSE_CMD -f docker-compose-airflow.yml down"
echo "========================================================================"

# Ask user if they want to trigger the pipeline
read -p "Do you want to trigger the ETL pipeline now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Triggering ETL pipeline..."
    $COMPOSE_CMD -f docker-compose-airflow.yml exec airflow-webserver airflow dags trigger e2e3d_etl_pipeline
    print_success "Pipeline triggered! Monitor progress in the Airflow UI: http://localhost:8080"
else
    print_info "Pipeline not triggered. You can manually trigger it when ready."
fi 