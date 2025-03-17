#!/bin/bash
# Test script to verify all ETL services are running correctly

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Get the root project directory
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Function to print header
print_header() {
    echo -e "\n${BLUE}========== $1 ==========${NC}\n"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check service status
check_service() {
    local service_name=$1
    local container_name=$2
    local port=${3:-}
    local endpoint=${4:-}
    
    echo -e "${YELLOW}Checking $service_name...${NC}"
    
    # Check if container is running
    if docker ps | grep -q "$container_name"; then
        echo -e "  ${GREEN}✓ Container is running${NC}"
        
        # Check if port is accessible (if provided)
        if [ -n "$port" ]; then
            if nc -z localhost "$port" >/dev/null 2>&1; then
                echo -e "  ${GREEN}✓ Port $port is accessible${NC}"
            else
                echo -e "  ${RED}✗ Port $port is not accessible${NC}"
                return 1
            fi
        fi
        
        # Check endpoint health (if provided)
        if [ -n "$endpoint" ]; then
            if curl -s "$endpoint" >/dev/null 2>&1; then
                echo -e "  ${GREEN}✓ Endpoint $endpoint is healthy${NC}"
            else
                echo -e "  ${RED}✗ Endpoint $endpoint is not accessible${NC}"
                return 1
            fi
        fi
        
        return 0
    else
        echo -e "  ${RED}✗ Container is not running${NC}"
        return 1
    fi
}

# Check Docker and Docker Compose
print_header "CHECKING PREREQUISITES"

# Check Docker
if command_exists docker; then
    echo -e "${GREEN}✓ Docker is installed${NC}"
    docker --version
else
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi

# Check Docker Compose
if command_exists docker-compose; then
    COMPOSE_CMD="docker-compose"
    echo -e "${GREEN}✓ Docker Compose V1 is installed${NC}"
    docker-compose --version
elif command_exists "docker" && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    echo -e "${GREEN}✓ Docker Compose V2 is installed${NC}"
    docker compose version
else
    echo -e "${RED}✗ Docker Compose is not installed${NC}"
    exit 1
fi

# Check if Docker Compose file exists
if [ -f "$PROJECT_DIR/docker-compose-airflow.yml" ]; then
    echo -e "${GREEN}✓ docker-compose-airflow.yml exists${NC}"
else
    echo -e "${RED}✗ docker-compose-airflow.yml not found!${NC}"
    exit 1
fi

# Check if e2e3d-reconstruction image exists
if docker image inspect e2e3d-reconstruction >/dev/null 2>&1; then
    echo -e "${GREEN}✓ e2e3d-reconstruction Docker image exists${NC}"
else
    echo -e "${YELLOW}! e2e3d-reconstruction Docker image not found${NC}"
    echo -e "${BLUE}Building the reconstruction image...${NC}"
    "$PROJECT_DIR/scripts/build_reconstruction_image.sh"
fi

# Check containers are running
print_header "CHECKING CONTAINER STATUS"

cd "$PROJECT_DIR"

# Function to get Docker container ID and status
get_container_status() {
    local service_name=$1
    local compose_file=$2
    
    # Check if the service exists in the compose file
    if ! grep -q "^ *$service_name:" "$compose_file"; then
        echo "not-found"
        return
    fi
    
    # Get container ID
    local container_id=$($COMPOSE_CMD -f "$compose_file" ps -q "$service_name" 2>/dev/null)
    
    # If container ID is empty, the service might not be running
    if [ -z "$container_id" ]; then
        echo "not-running"
        return
    fi
    
    # Get container status
    local status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null)
    
    if [ -z "$status" ]; then
        echo "unknown"
    else
        echo "$status"
    fi
}

# Check if services are running
all_services_running=true

# List of services to check
declare -a services
services=("airflow-webserver" "airflow-scheduler" "postgres" "minio" "spark-master" "spark-worker-1")

for service in "${services[@]}"; do
    status=$(get_container_status "$service" "docker-compose-airflow.yml")
    
    if [ "$status" != "running" ]; then
        all_services_running=false
    fi
    
    case "$status" in
        "running")
            echo -e "${GREEN}✓ $service is running${NC}"
            ;;
        "not-found")
            echo -e "${RED}✗ $service not found in docker-compose file${NC}"
            ;;
        "not-running")
            echo -e "${RED}✗ $service is not running${NC}"
            ;;
        "unknown")
            echo -e "${RED}✗ $service status unknown${NC}"
            ;;
        *)
            echo -e "${RED}✗ $service is $status${NC}"
            ;;
    esac
done

# If not all services are running, offer to restart them
if [ "$all_services_running" = false ]; then
    echo -e "\n${YELLOW}Not all services are running.${NC}"
    read -p "Do you want to (re)start all services? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Stopping any existing services...${NC}"
        $COMPOSE_CMD -f docker-compose-airflow.yml down
        
        echo -e "${BLUE}Starting all services...${NC}"
        $COMPOSE_CMD -f docker-compose-airflow.yml up -d
        
        echo -e "${BLUE}Waiting for services to start...${NC}"
        sleep 30
    fi
fi

# Detailed service checks
print_header "DETAILED SERVICE CHECKS"

# Check PostgreSQL
check_service "PostgreSQL" "e2e3d-postgres-1" "5432"

# Check MinIO
check_service "MinIO" "e2e3d-minio-1" "9000" "http://localhost:9000/minio/health/live"

# Check Spark Master
check_service "Spark Master" "e2e3d-spark-master-1" "8090" "http://localhost:8090"

# Check Spark Worker
check_service "Spark Worker" "e2e3d-spark-worker-1-1"

# Check Airflow Webserver
check_service "Airflow Webserver" "e2e3d-airflow-webserver-1" "8080" "http://localhost:8080/health"

# Check Airflow Scheduler
check_service "Airflow Scheduler" "e2e3d-airflow-scheduler-1"

# Check Airflow connections
print_header "CHECKING AIRFLOW CONNECTIONS"

echo -e "${YELLOW}Checking Airflow connections...${NC}"
# Store service status
declare -A service_status
service_status=()
if docker ps | grep -q "e2e3d-airflow-webserver-1"; then
    service_status["airflow-webserver"]="running"
else
    service_status["airflow-webserver"]="not-running"
fi

if [ "${service_status["airflow-webserver"]}" = "running" ]; then
    connection_output=$($COMPOSE_CMD -f docker-compose-airflow.yml exec -T airflow-webserver airflow connections get spark_default 2>&1)

    if echo "$connection_output" | grep -q "spark://spark-master:7077"; then
        echo -e "${GREEN}✓ Spark connection is configured correctly${NC}"
    else
        echo -e "${RED}✗ Spark connection is not configured correctly${NC}"
        echo -e "${BLUE}Setting up Spark connection...${NC}"
        $COMPOSE_CMD -f docker-compose-airflow.yml exec -T airflow-webserver airflow connections add 'spark_default' \
            --conn-type 'spark' \
            --conn-host 'spark://spark-master' \
            --conn-port '7077' \
            --conn-extra '{"queue": "default"}' || true
    fi
else
    echo -e "${RED}✗ Cannot check Airflow connections because airflow-webserver is not running${NC}"
fi

# Check Airflow DAG
print_header "CHECKING AIRFLOW DAG"

echo -e "${YELLOW}Checking if DAG is loaded...${NC}"
if [ "${service_status["airflow-webserver"]}" = "running" ]; then
    dag_output=$($COMPOSE_CMD -f docker-compose-airflow.yml exec -T airflow-webserver airflow dags list 2>&1)

    if echo "$dag_output" | grep -q "e2e3d_etl_pipeline"; then
        echo -e "${GREEN}✓ ETL pipeline DAG is loaded${NC}"
    else
        echo -e "${RED}✗ ETL pipeline DAG is not loaded${NC}"
        echo -e "${YELLOW}Check that the DAG file exists in airflow/dags/ directory${NC}"
    fi
else
    echo -e "${RED}✗ Cannot check DAGs because airflow-webserver is not running${NC}"
fi

# Final summary
print_header "TEST SUMMARY"

# Re-check critical services
all_services_ok=true

if ! check_service "PostgreSQL" "e2e3d-postgres-1" >/dev/null 2>&1; then
    all_services_ok=false
fi

if ! check_service "MinIO" "e2e3d-minio-1" "9000" >/dev/null 2>&1; then
    all_services_ok=false
fi

if ! check_service "Spark Master" "e2e3d-spark-master-1" "8090" >/dev/null 2>&1; then
    all_services_ok=false
fi

if ! check_service "Airflow Webserver" "e2e3d-airflow-webserver-1" "8080" >/dev/null 2>&1; then
    all_services_ok=false
fi

if [ "$all_services_ok" = true ]; then
    echo -e "${GREEN}All services are running correctly!${NC}"
else
    echo -e "${RED}Some services are not running correctly.${NC}"
    echo -e "${YELLOW}Please check the logs for troubleshooting:${NC}"
    echo -e "$COMPOSE_CMD -f docker-compose-airflow.yml logs"
fi 