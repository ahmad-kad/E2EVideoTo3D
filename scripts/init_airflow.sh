#!/bin/bash
set -e

echo "==== Initializing Airflow Database ===="

# Stop any running Airflow containers
echo "Stopping Airflow containers..."
docker-compose stop airflow-webserver airflow-scheduler

# Reset Airflow database
echo "Initializing Airflow database..."
docker-compose run --rm airflow-webserver airflow db init

# Create default connections
echo "Creating default connections..."
docker-compose run --rm airflow-webserver airflow connections add 'fs_default' \
    --conn-type 'fs' \
    --conn-extra '{"path": "/"}' 

# Create admin user
echo "Creating admin user..."
docker-compose run --rm airflow-webserver airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com

# Start Airflow services
echo "Starting Airflow services..."
docker-compose start airflow-webserver airflow-scheduler

echo "==== Airflow Initialization Complete ===="
echo ""
echo "You can now access Airflow at: http://localhost:8080"
echo "Username: admin"
echo "Password: admin" 