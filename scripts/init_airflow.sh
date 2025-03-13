#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Initializing Airflow...${NC}"

# Create directory for Airflow logs if it doesn't exist
mkdir -p airflow/logs

echo -e "${BLUE}==== Initializing Airflow Database ====${NC}"

# Stop existing containers first to avoid port conflicts
echo "Stopping Airflow containers..."
docker-compose stop airflow-webserver airflow-scheduler

# Initialize the database
echo "Initializing Airflow database..."
docker-compose up -d postgres
sleep 5  # Give PostgreSQL time to start

echo -e "${BLUE}Running database initialization...${NC}"
docker-compose run --rm airflow-webserver airflow db init

# Check if fs_default connection exists before creating it
echo -e "${BLUE}Checking existing connections...${NC}"
CONNECTION_EXISTS=$(docker-compose run --rm airflow-webserver airflow connections get fs_default 2>&1 | grep -c "Connection not found")

if [ "$CONNECTION_EXISTS" -eq 1 ]; then
    echo -e "${GREEN}Creating fs_default connection...${NC}"
    docker-compose run --rm airflow-webserver airflow connections add 'fs_default' \
        --conn-type 'fs' \
        --conn-extra '{"path": "/"}'
else
    echo -e "${YELLOW}Connection fs_default already exists - skipping creation${NC}"
fi

# Check if admin user exists
echo -e "${BLUE}Checking if admin user exists...${NC}"
ADMIN_EXISTS=$(docker-compose run --rm airflow-webserver airflow users list | grep -c admin)

if [ "$ADMIN_EXISTS" -eq 0 ]; then
    echo -e "${GREEN}Creating admin user...${NC}"
    docker-compose run --rm airflow-webserver airflow users create \
        --username admin \
        --password admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com
else
    echo -e "${YELLOW}Admin user already exists - skipping creation${NC}"
fi

# Start Airflow services
echo -e "${BLUE}Starting Airflow services...${NC}"
docker-compose up -d airflow-webserver airflow-scheduler

echo -e "${GREEN}Airflow initialization complete!${NC}"
echo "You can access the Airflow web interface at: http://localhost:8080"
echo "Username: admin"
echo "Password: admin" 