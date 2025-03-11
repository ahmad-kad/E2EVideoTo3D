#!/bin/bash
set -e

echo "==== Diagnosing Airflow Connection Issues ===="

# Check if containers are running
echo "Checking container status..."
CONTAINER_STATUS=$(docker-compose ps)
echo "$CONTAINER_STATUS"

# Check if Airflow webserver container is running
if ! echo "$CONTAINER_STATUS" | grep -q "airflow-webserver.*Up"; then
    echo "Error: Airflow webserver container is not running."
    echo "Attempting to restart..."
    docker-compose restart airflow-webserver
    sleep 10
fi

# Check Airflow logs for errors
echo "Checking Airflow webserver logs for errors..."
docker-compose logs --tail=50 airflow-webserver

# Check if port 8080 is already in use by another process
echo "Checking if port 8080 is already in use..."
if command -v lsof &> /dev/null; then
    PROCESSES_ON_8080=$(lsof -i :8080 | grep LISTEN)
    if [ -n "$PROCESSES_ON_8080" ]; then
        echo "Warning: Port 8080 is already in use by another process:"
        echo "$PROCESSES_ON_8080"
        echo "Please stop that process or change the Airflow port in docker-compose.yml"
    else
        echo "Port 8080 is available."
    fi
else
    echo "lsof command not found, skipping port check..."
fi

# Check network connectivity to the container
echo "Checking network connectivity to Airflow webserver..."
if docker-compose exec airflow-webserver curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health; then
    echo "Airflow webserver is responding to health checks within the container."
else
    echo "Error: Airflow webserver is not responding to health checks."
    echo "Attempting to restart..."
    docker-compose restart airflow-webserver
    sleep 10
fi

# Create Airflow user if it doesn't exist
echo "Checking if Airflow user exists..."
USER_EXISTS=$(docker-compose exec airflow-webserver airflow users list | grep -c "admin")
if [ "$USER_EXISTS" -eq 0 ]; then
    echo "Creating admin user for Airflow..."
    docker-compose exec airflow-webserver airflow users create \
        --username admin \
        --password admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com
    echo "Admin user created with username 'admin' and password 'admin'"
fi

echo ""
echo "==== Airflow Connection Diagnostics Complete ===="
echo ""
echo "If you're still having issues connecting to Airflow:"
echo "1. Try accessing Airflow using a different browser or incognito mode"
echo "2. Make sure your firewall isn't blocking port 8080"
echo "3. Try using the IP address instead of localhost: http://127.0.0.1:8080"
echo "4. If all else fails, try restarting Docker completely"
echo ""
echo "You can restart the entire stack with:"
echo "  docker-compose down"
echo "  docker-compose up -d" 