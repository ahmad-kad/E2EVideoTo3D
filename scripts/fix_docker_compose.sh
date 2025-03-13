#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Docker Compose Volume Fix Script   ${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml file not found in current directory!${NC}"
    echo "Please run this script from the root directory of your project."
    exit 1
fi

# Create backup
echo -e "\n${BLUE}Creating backup of docker-compose.yml...${NC}"
cp docker-compose.yml docker-compose.yml.backup
echo -e "${GREEN}Backup created: docker-compose.yml.backup${NC}"

# Function to add volume mappings to a service
add_volumes_to_service() {
    local service=$1
    local has_volumes=$(grep -A 20 "services:.*$service:" docker-compose.yml | grep -c "volumes:")
    
    if [ "$has_volumes" -eq 0 ]; then
        echo -e "${YELLOW}Service $service doesn't have volumes section. Adding...${NC}"
        # Complex sed operation to add volumes to service
        sed -i.tmp "/services:.*$service:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1volumes:\n\1  - \.\/data:\/opt\/airflow\/data\n\1  - \.\/airflow\/dags:\/opt\/airflow\/dags\n\1  - \.\/airflow\/logs:\/opt\/airflow\/logs\n\1  - \.\/airflow\/plugins:\/opt\/airflow\/plugins\n&/" docker-compose.yml
        rm -f docker-compose.yml.tmp
    else
        echo -e "${GREEN}Service $service already has volumes section.${NC}"
        
        # Check if specific volume mappings exist and add if missing
        if ! grep -A 30 "services:.*$service:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "./data:/opt/airflow/data"; then
            echo -e "${YELLOW}Adding data volume mapping to $service...${NC}"
            sed -i.tmp "/services:.*$service:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/data:\/opt\/airflow\/data/" docker-compose.yml
            rm -f docker-compose.yml.tmp
        fi
        
        if ! grep -A 30 "services:.*$service:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "./airflow/dags:/opt/airflow/dags"; then
            echo -e "${YELLOW}Adding dags volume mapping to $service...${NC}"
            sed -i.tmp "/services:.*$service:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/airflow\/dags:\/opt\/airflow\/dags/" docker-compose.yml
            rm -f docker-compose.yml.tmp
        fi
        
        if ! grep -A 30 "services:.*$service:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "./airflow/logs:/opt/airflow/logs"; then
            echo -e "${YELLOW}Adding logs volume mapping to $service...${NC}"
            sed -i.tmp "/services:.*$service:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/airflow\/logs:\/opt\/airflow\/logs/" docker-compose.yml
            rm -f docker-compose.yml.tmp
        fi
        
        if ! grep -A 30 "services:.*$service:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "./airflow/plugins:/opt/airflow/plugins"; then
            echo -e "${YELLOW}Adding plugins volume mapping to $service...${NC}"
            sed -i.tmp "/services:.*$service:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/airflow\/plugins:\/opt\/airflow\/plugins/" docker-compose.yml
            rm -f docker-compose.yml.tmp
        fi
    fi
}

# Check if MinIO service exists
if grep -q "services:.*minio:" docker-compose.yml; then
    echo -e "\n${BLUE}Checking MinIO service configuration...${NC}"
    
    # Check if MinIO has the right ports
    if ! grep -A 20 "services:.*minio:" docker-compose.yml | grep -q "9001:9001"; then
        echo -e "${YELLOW}Adding port 9001 mapping to MinIO...${NC}"
        sed -i.tmp "/services:.*minio:/,/ports:/ s/\([ ]*\)ports:/\1ports:\n\1  - \"9001:9001\"/" docker-compose.yml
        rm -f docker-compose.yml.tmp
    else
        echo -e "${GREEN}MinIO already has port 9001 mapping.${NC}"
    fi
    
    # Check if MinIO has correct environment variables
    if ! grep -A 30 "services:.*minio:" docker-compose.yml | grep -q "MINIO_CONSOLE_ADDRESS"; then
        echo -e "${YELLOW}Adding console address configuration to MinIO...${NC}"
        sed -i.tmp "/services:.*minio:/,/environment:/ s/\([ ]*\)environment:/\1environment:\n\1  - MINIO_CONSOLE_ADDRESS=:9001/" docker-compose.yml
        rm -f docker-compose.yml.tmp
    fi
    
    # Check for MinIO volume mappings
    if ! grep -A 30 "services:.*minio:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "data"; then
        echo -e "${YELLOW}Adding data volume mapping to MinIO...${NC}"
        
        # Check if MinIO has volumes section
        if ! grep -A 30 "services:.*minio:" docker-compose.yml | grep -q "volumes:"; then
            echo -e "${YELLOW}Adding volumes section to MinIO...${NC}"
            sed -i.tmp "/services:.*minio:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1volumes:\n\1  - \.\/data:\/data\n&/" docker-compose.yml
        else
            echo -e "${YELLOW}Adding to existing volumes section in MinIO...${NC}"
            sed -i.tmp "/services:.*minio:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/data:\/data/" docker-compose.yml
        fi
        rm -f docker-compose.yml.tmp
    fi
else
    echo -e "${RED}MinIO service not found in docker-compose.yml${NC}"
    echo "This is unusual. Your docker-compose.yml might be incomplete."
fi

# Fix volume mappings for Airflow services
echo -e "\n${BLUE}Checking Airflow services configuration...${NC}"

# Check if airflow-webserver service exists
if grep -q "services:.*airflow-webserver:" docker-compose.yml; then
    echo -e "${BLUE}Processing airflow-webserver service...${NC}"
    add_volumes_to_service "airflow-webserver"
fi

# Check if airflow-scheduler service exists
if grep -q "services:.*airflow-scheduler:" docker-compose.yml; then
    echo -e "\n${BLUE}Processing airflow-scheduler service...${NC}"
    add_volumes_to_service "airflow-scheduler"
fi

# Check if airflow-worker service exists (for Celery executor)
if grep -q "services:.*airflow-worker:" docker-compose.yml; then
    echo -e "\n${BLUE}Processing airflow-worker service...${NC}"
    add_volumes_to_service "airflow-worker"
fi

# Fix photogrammetry (COLMAP) service if it exists
if grep -q "services:.*photogrammetry:" docker-compose.yml; then
    echo -e "\n${BLUE}Processing photogrammetry service...${NC}"
    
    if ! grep -A 30 "services:.*photogrammetry:" docker-compose.yml | grep -A 30 "volumes:" | grep -q "data"; then
        if ! grep -A 30 "services:.*photogrammetry:" docker-compose.yml | grep -q "volumes:"; then
            echo -e "${YELLOW}Adding volumes section to photogrammetry...${NC}"
            sed -i.tmp "/services:.*photogrammetry:/,/[a-z]/ s/\([ ]*\)[a-z][a-z]*:.*/\1volumes:\n\1  - \.\/data:\/data\n&/" docker-compose.yml
        else
            echo -e "${YELLOW}Adding data volume mapping to photogrammetry...${NC}"
            sed -i.tmp "/services:.*photogrammetry:/,/volumes:/ s/\([ ]*\)volumes:/\1volumes:\n\1  - \.\/data:\/data/" docker-compose.yml
        fi
        rm -f docker-compose.yml.tmp
    fi
fi

echo -e "\n${GREEN}Docker Compose file updates completed!${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "To apply these changes:"
echo -e "1. Run: ${YELLOW}docker-compose down${NC}"
echo -e "2. Run: ${YELLOW}docker-compose up -d${NC}"
echo -e "3. Verify with: ${YELLOW}./scripts/check_video_path.sh${NC}"
echo -e "\nIf you encounter any issues, you can restore the backup with:"
echo -e "${YELLOW}cp docker-compose.yml.backup docker-compose.yml${NC}" 