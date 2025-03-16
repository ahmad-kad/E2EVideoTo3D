#!/bin/bash
# troubleshoot_airflow.sh
# This script helps diagnose and fix common Airflow connection issues

# Enable error handling
set -e

# Define color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}E2E3D Airflow Troubleshooting${NC}"
echo -e "${BLUE}======================================${NC}"

# Determine Docker Compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

# Check if Airflow webserver container is running
echo -e "${BLUE}Checking Airflow webserver container...${NC}"
WEBSERVER_CONTAINER=$($DOCKER_COMPOSE ps -q airflow-webserver 2>/dev/null)

if [ -z "$WEBSERVER_CONTAINER" ]; then
    echo -e "${RED}Error: Airflow webserver container is not running${NC}"
    echo -e "${YELLOW}Attempting to start services...${NC}"
    $DOCKER_COMPOSE up -d
    sleep 10
    WEBSERVER_CONTAINER=$($DOCKER_COMPOSE ps -q airflow-webserver 2>/dev/null)
    
    if [ -z "$WEBSERVER_CONTAINER" ]; then
        echo -e "${RED}Failed to start Airflow webserver container${NC}"
        echo -e "${YELLOW}Checking docker-compose.yml for issues...${NC}"
        
        # Check if docker-compose.yml exists
        if [ ! -f "docker-compose.yml" ]; then
            echo -e "${RED}docker-compose.yml not found!${NC}"
            exit 1
        fi
        
        # Check if airflow-webserver service is defined
        if ! grep -q "airflow-webserver" docker-compose.yml; then
            echo -e "${RED}airflow-webserver service not found in docker-compose.yml${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}Please check docker-compose.yml and try again${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Airflow webserver container is running: $WEBSERVER_CONTAINER${NC}"

# Check container logs for errors
echo -e "${BLUE}Checking Airflow webserver logs for errors...${NC}"
ERROR_COUNT=$(docker logs $WEBSERVER_CONTAINER 2>&1 | grep -c -E "ERROR|Error|error" || true)

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Found $ERROR_COUNT errors in logs. Last 5 errors:${NC}"
    docker logs $WEBSERVER_CONTAINER 2>&1 | grep -E "ERROR|Error|error" | tail -5
fi

# Check if database initialization is needed
if docker logs $WEBSERVER_CONTAINER 2>&1 | grep -q "Database is not initialized"; then
    echo -e "${YELLOW}Database initialization needed. Running airflow db init...${NC}"
    $DOCKER_COMPOSE run --rm airflow-webserver airflow db init
    $DOCKER_COMPOSE restart airflow-webserver
    sleep 10
fi

# Check if Airflow webserver is responding on port 8080
echo -e "${BLUE}Checking connection to Airflow webserver...${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 | grep -q "200\|302"; then
    echo -e "${GREEN}Airflow webserver is responding on http://localhost:8080${NC}"
    WEBSERVER_UP=true
else
    echo -e "${RED}Cannot connect to Airflow webserver on http://localhost:8080${NC}"
    WEBSERVER_UP=false
    
    # Check if port 8080 is in use
    echo -e "${BLUE}Checking if port 8080 is already in use...${NC}"
    if lsof -i :8080 | grep -q LISTEN; then
        echo -e "${RED}Port 8080 is already in use by another process:${NC}"
        lsof -i :8080 | grep LISTEN
        echo -e "${YELLOW}Consider changing the port in docker-compose.yml or stopping the conflicting process${NC}"
    else
        echo -e "${GREEN}Port 8080 is available${NC}"
    fi
    
    # Check network connectivity to the container
    echo -e "${BLUE}Checking network connectivity to the container...${NC}"
    CONTAINER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $WEBSERVER_CONTAINER)
    
    if [ -n "$CONTAINER_IP" ]; then
        echo -e "${GREEN}Container IP: $CONTAINER_IP${NC}"
        if docker exec $WEBSERVER_CONTAINER curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 | grep -q "200\|302"; then
            echo -e "${GREEN}Airflow webserver is accessible from inside the container${NC}"
            echo -e "${YELLOW}Issue appears to be with Docker networking${NC}"
        else
            echo -e "${RED}Airflow webserver is not accessible from inside the container${NC}"
            echo -e "${YELLOW}Issue may be with the Airflow webserver configuration${NC}"
        fi
    else
        echo -e "${RED}Could not determine container IP address${NC}"
    fi
fi

# Verify Airflow user exists
echo -e "${BLUE}Checking if Airflow admin user exists...${NC}"
USER_CHECK=$($DOCKER_COMPOSE exec -T airflow-webserver airflow users list 2>/dev/null | grep admin || echo "")

if [ -z "$USER_CHECK" ]; then
    echo -e "${YELLOW}Airflow admin user does not exist. Creating...${NC}"
    $DOCKER_COMPOSE exec -T airflow-webserver airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com \
        --password admin
fi

# Provide connection details and troubleshooting steps
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Troubleshooting Summary${NC}"
echo -e "${BLUE}======================================${NC}"

if [ "$WEBSERVER_UP" = true ]; then
    echo -e "${GREEN}Airflow webserver is running and accessible.${NC}"
    echo -e "Access URL: http://localhost:8080"
    echo -e "Username: admin"
    echo -e "Password: admin"
else
    echo -e "${YELLOW}Airflow webserver is running but not accessible from host.${NC}"
    echo -e "Try the following steps:"
    echo -e "1. Restart Docker Desktop"
    echo -e "2. Run: $DOCKER_COMPOSE down && $DOCKER_COMPOSE up -d"
    echo -e "3. Check if another service is using port 8080"
    echo -e "4. Inspect container logs with: $DOCKER_COMPOSE logs airflow-webserver"
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${YELLOW}Additional Commands:${NC}"
echo -e "- Restart all services: $DOCKER_COMPOSE restart"
echo -e "- Restart just Airflow: $DOCKER_COMPOSE restart airflow-webserver"
echo -e "- View detailed logs: $DOCKER_COMPOSE logs -f airflow-webserver"
echo -e "- Recreate everything: $DOCKER_COMPOSE down && $DOCKER_COMPOSE up -d"
echo -e "${BLUE}======================================${NC}"

exit 0 