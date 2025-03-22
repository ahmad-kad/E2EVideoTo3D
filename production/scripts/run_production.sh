#!/bin/bash
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Functions
function info() {
    echo -e "${GREEN}INFO: $1${NC}"
}

function warn() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

function error() {
    echo -e "${RED}ERROR: $1${NC}"
    exit 1
}

# Change to the script directory
cd "$(dirname "$0")/../"
PRODUCTION_DIR="$(pwd)"
BASE_DIR="$(dirname "$PRODUCTION_DIR")"

# Welcome message
info "E2E3D Production Environment Setup"
info "============================================"

# Check command
ACTION="${1:-start}"
case "$ACTION" in
    build|start|stop|clean|help)
        info "Action: $ACTION"
        ;;
    *)
        warn "Unknown action: $ACTION. Using default: start"
        ACTION="start"
        ;;
esac

# Help message
if [ "$ACTION" == "help" ]; then
    echo "Usage: $0 [build|start|stop|clean|help]"
    echo ""
    echo "Commands:"
    echo "  build  - Build and start the production environment"
    echo "  start  - Start the production environment without rebuilding"
    echo "  stop   - Stop all production services"
    echo "  clean  - Stop all production services and remove containers"
    echo "  help   - Show this help message"
    echo ""
    echo "Environment:"
    echo "  The production environment is configured using the .env file"
    echo "  in the production directory. If this file doesn't exist, it will"
    echo "  be created from the .env.template file."
    exit 0
fi

# Check if docker is installed and running
if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker and try again."
fi

if ! docker info &> /dev/null; then
    error "Docker is not running. Please start Docker and try again."
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose is not installed. Please install Docker Compose and try again."
fi

# Create directories
info "Setting up directories..."
mkdir -p "$BASE_DIR/data/input" "$BASE_DIR/data/output" "$PRODUCTION_DIR/logs" "$PRODUCTION_DIR/dags"

# Load environment variables
info "Loading environment variables..."
if [ ! -f "$PRODUCTION_DIR/.env" ]; then
    if [ -f "$PRODUCTION_DIR/.env.template" ]; then
        info "Creating .env file from template..."
        cp "$PRODUCTION_DIR/.env.template" "$PRODUCTION_DIR/.env"
        warn "Please review and update the .env file with your settings."
    else
        warn "No .env.template file found. Creating default .env file..."
        cat > "$PRODUCTION_DIR/.env" << EOF
# E2E3D Production Environment Configuration
DOCKER_REGISTRY=localhost
IMAGE_TAG=latest
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=airflow
AIRFLOW_FERNET_KEY=
AIRFLOW_SECRET_KEY=temporary_key
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
USE_GPU=false
MAX_WORKERS=4
LOG_LEVEL=INFO
ENABLE_METRICS=true
EOF
        warn "Please review and update the .env file with your settings."
    fi
fi

# Source the environment variables
set -a
source "$PRODUCTION_DIR/.env"
set +a

# Create configuration files if they don't exist
info "Setting up configuration files..."

# Create HTML directory
mkdir -p "$PRODUCTION_DIR/config/nginx/html"
if [ ! -f "$PRODUCTION_DIR/config/nginx/html/index.html" ]; then
    info "Creating default index.html..."
    if [ -f "$PRODUCTION_DIR/config/nginx/html/index.html" ]; then
        cp "$PRODUCTION_DIR/config/nginx/html/index.html" "$PRODUCTION_DIR/config/nginx/html/index.html"
    else
        warn "Default index.html not found. Please create it manually."
    fi
fi

# Create Prometheus configuration if it doesn't exist
mkdir -p "$PRODUCTION_DIR/config/prometheus"
if [ ! -f "$PRODUCTION_DIR/config/prometheus.yml" ]; then
    info "Creating default Prometheus configuration..."
    if [ -f "$PRODUCTION_DIR/config/prometheus.yml" ]; then
        mkdir -p "$(dirname "$PRODUCTION_DIR/config/prometheus.yml")"
        cp "$PRODUCTION_DIR/config/prometheus.yml" "$PRODUCTION_DIR/config/prometheus.yml"
    else
        warn "Default prometheus.yml not found. Please create it manually."
    fi
fi

# Create Grafana provisioning directories
mkdir -p "$PRODUCTION_DIR/config/grafana/provisioning/datasources"
mkdir -p "$PRODUCTION_DIR/config/grafana/provisioning/dashboards"

# Create default datasource if it doesn't exist
if [ ! -f "$PRODUCTION_DIR/config/grafana/provisioning/datasources/prometheus.yml" ]; then
    info "Creating default Grafana datasource..."
    cat > "$PRODUCTION_DIR/config/grafana/provisioning/datasources/prometheus.yml" << EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    version: 1
    editable: false
EOF
fi

# Create default dashboard configuration if it doesn't exist
if [ ! -f "$PRODUCTION_DIR/config/grafana/provisioning/dashboards/dashboard.yml" ]; then
    info "Creating default Grafana dashboard configuration..."
    cat > "$PRODUCTION_DIR/config/grafana/provisioning/dashboards/dashboard.yml" << EOF
apiVersion: 1

providers:
  - name: 'E2E3D Dashboards'
    orgId: 1
    folder: 'E2E3D'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
EOF
fi

# Create NGINX configuration directories
mkdir -p "$PRODUCTION_DIR/config/nginx/conf.d"

# Check if default.conf exists
if [ ! -f "$PRODUCTION_DIR/config/nginx/conf.d/default.conf" ]; then
    info "Creating default NGINX site configuration..."
    if [ -f "$PRODUCTION_DIR/config/nginx/conf.d/default.conf" ]; then
        cp "$PRODUCTION_DIR/config/nginx/conf.d/default.conf" "$PRODUCTION_DIR/config/nginx/conf.d/default.conf"
    else
        warn "Default NGINX configuration not found. Please create it manually."
    fi
fi

# Check if nginx.conf exists
if [ ! -f "$PRODUCTION_DIR/config/nginx/nginx.conf" ]; then
    info "Creating default NGINX configuration..."
    if [ -f "$PRODUCTION_DIR/config/nginx/nginx.conf" ]; then
        cp "$PRODUCTION_DIR/config/nginx/nginx.conf" "$PRODUCTION_DIR/config/nginx/nginx.conf"
    else
        warn "Default NGINX configuration not found. Please create it manually."
    fi
fi

# Create an example DAG if dags directory is empty
if [ -z "$(ls -A "$PRODUCTION_DIR/dags" 2>/dev/null)" ]; then
    info "Creating example DAG..."
    if [ -f "$PRODUCTION_DIR/dags/e2e3d_reconstruction_dag.py" ]; then
        cp "$PRODUCTION_DIR/dags/e2e3d_reconstruction_dag.py" "$PRODUCTION_DIR/dags/e2e3d_reconstruction_dag.py"
    else
        warn "Example DAG file not found. Please create it manually."
    fi
fi

# Check for Docker images
info "Checking for Docker images..."

# Check if reconstruction image exists
REBUILD_RECONSTRUCTION=false
if [ "$ACTION" == "build" ] || ! docker image inspect ${DOCKER_REGISTRY:-localhost}/e2e3d-reconstruction:${IMAGE_TAG:-latest} &> /dev/null; then
    info "Building E2E3D Reconstruction image..."
    REBUILD_RECONSTRUCTION=true
fi

# Check if airflow image exists
REBUILD_AIRFLOW=false
if [ "$ACTION" == "build" ] || ! docker image inspect ${DOCKER_REGISTRY:-localhost}/e2e3d-airflow:${IMAGE_TAG:-latest} &> /dev/null; then
    info "Building E2E3D Airflow image..."
    REBUILD_AIRFLOW=true
fi

# Stop any existing containers
if [ "$ACTION" == "stop" ] || [ "$ACTION" == "clean" ]; then
    info "Stopping existing containers..."
    docker-compose -f "$PRODUCTION_DIR/docker-compose.yml" down
    
    if [ "$ACTION" == "clean" ]; then
        info "Removing volumes..."
        docker-compose -f "$PRODUCTION_DIR/docker-compose.yml" down -v
    fi
    
    if [ "$ACTION" == "stop" ]; then
        info "Containers stopped successfully."
        exit 0
    elif [ "$ACTION" == "clean" ]; then
        info "Environment cleaned successfully."
        exit 0
    fi
fi

# Build the images if needed
if [ "$REBUILD_RECONSTRUCTION" == "true" ]; then
    info "Building E2E3D Reconstruction image..."
    docker build -t ${DOCKER_REGISTRY:-localhost}/e2e3d-reconstruction:${IMAGE_TAG:-latest} \
        -f "$PRODUCTION_DIR/Dockerfile.reconstruction" "$BASE_DIR"
    
    if [ $? -ne 0 ]; then
        error "Failed to build E2E3D Reconstruction image."
    fi
fi

if [ "$REBUILD_AIRFLOW" == "true" ]; then
    info "Building E2E3D Airflow image..."
    docker build -t ${DOCKER_REGISTRY:-localhost}/e2e3d-airflow:${IMAGE_TAG:-latest} \
        -f "$PRODUCTION_DIR/Dockerfile.airflow" "$BASE_DIR"
    
    if [ $? -ne 0 ]; then
        error "Failed to build E2E3D Airflow image."
    fi
fi

# Start the services
info "Starting E2E3D Production environment..."
docker-compose -f "$PRODUCTION_DIR/docker-compose.yml" up -d

if [ $? -ne 0 ]; then
    error "Failed to start E2E3D Production environment."
fi

# Wait for services to initialize
info "Waiting for services to initialize..."
sleep 5

# Check service health
info "Checking service health..."

# Function to check if a service is healthy
check_service() {
    local service="$1"
    local port="$2"
    local endpoint="$3"
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:$port$endpoint" &> /dev/null; then
            info "$service is available."
            return 0
        fi
        
        info "Waiting for $service to be available (attempt $attempt/$max_attempts)..."
        sleep 5
        ((attempt++))
    done
    
    warn "$service is not available after $max_attempts attempts."
    return 1
}

check_service "MinIO" "9001" "/"
check_service "Airflow" "8080" "/health"

# Final success message
info "E2E3D Production environment is ready!"
info "============================================"
info "Access the services at:"
info "  - Main Dashboard:   http://localhost:80"
info "  - MinIO Console:    http://localhost:9001 (user: $MINIO_ROOT_USER, password: $MINIO_ROOT_PASSWORD)"
info "  - Airflow UI:       http://localhost:8080 (user: $AIRFLOW_ADMIN_USER, password: $AIRFLOW_ADMIN_PASSWORD)"
info "  - Grafana:          http://localhost:3000 (user: $GRAFANA_ADMIN_USER, password: $GRAFANA_ADMIN_PASSWORD)"
info "  - Prometheus:       http://localhost:9090"
info "  - API:              http://localhost:80/api"
info "============================================" 