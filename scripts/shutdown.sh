#!/bin/bash

# E2E3D Complete Shutdown Script
# This script safely shuts down all components of the E2E3D pipeline

# Define text formatting
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BOLD}${BLUE}"
echo "╔═══════════════════════════════════════════╗"
echo "║ E2E3D Pipeline - Complete Shutdown Script ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# Check if script is run with sudo/root and warn if it is
if [ "$EUID" -eq 0 ]; then
  echo -e "${YELLOW}Warning: This script is running with root privileges.${NC}"
  echo -e "This is generally ${RED}not recommended${NC} unless specifically needed."
  echo
  read -p "Continue with root privileges? (y/n): " choice
  if [[ ! "$choice" =~ ^[Yy]$ ]]; then
    echo "Exiting script. Please run without sudo."
    exit 1
  fi
fi

# Function to get user confirmation
confirm() {
    read -p "$1 (y/n): " choice
    case "$choice" in
        y|Y ) return 0;;
        * ) return 1;;
    esac
}

# Function to check if docker-compose exists
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        return 0
    elif command -v docker compose &> /dev/null; then
        echo -e "${YELLOW}Using 'docker compose' instead of 'docker-compose'${NC}"
        alias docker-compose='docker compose'
        return 0
    else
        echo -e "${RED}Error: docker-compose is not installed or not in PATH${NC}"
        echo "Please install docker-compose or make sure it's in your PATH"
        return 1
    fi
}

# Check if docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running or you don't have permission to use it.${NC}"
    echo "Please start Docker service or use appropriate permissions."
    exit 1
fi

# Check if docker-compose is available
check_docker_compose || exit 1

echo -e "${BOLD}Step 1: Checking for running containers${NC}"
RUNNING_CONTAINERS=$(docker ps --filter name=e2e3d -q)
if [ -z "$RUNNING_CONTAINERS" ]; then
    echo -e "No e2e3d containers are currently running."
else
    CONTAINER_COUNT=$(echo "$RUNNING_CONTAINERS" | wc -l)
    echo -e "Found ${GREEN}$CONTAINER_COUNT${NC} running e2e3d containers."
fi

echo -e "\n${BOLD}Step 2: Stopping Airflow pipelines${NC}"
if docker ps | grep -q "airflow-webserver"; then
    echo "Attempting to gracefully stop any running Airflow DAGs..."
    # Try to stop any running DAGs through Airflow CLI
    docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') airflow dags pause video_to_3d_reconstruction 2>/dev/null || true
    sleep 2
    
    # Get list of running DAGs
    RUNNING_DAGS=$(docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') airflow dags list-runs -s running 2>/dev/null | grep -v "No dags" || true)
    
    if [ ! -z "$RUNNING_DAGS" ]; then
        echo -e "${YELLOW}Some DAGs are still running:${NC}"
        echo "$RUNNING_DAGS"
        if confirm "Do you want to force stop all running DAGs?"; then
            echo "Force stopping all DAGs (this may take a moment)..."
            docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') airflow dags list-runs -s running | grep -v DAGS | awk '{print $1, $2}' | while read dag_id run_id; do
                docker exec $(docker ps | grep airflow-webserver | awk '{print $1}') airflow dags delete-dag-run "$dag_id" "$run_id" -y 2>/dev/null || true
            done
            sleep 3
        fi
    else
        echo "No running Airflow DAGs found."
    fi
else
    echo "Airflow webserver is not running."
fi

echo -e "\n${BOLD}Step 3: Stopping Docker containers${NC}"
if [ -f "docker-compose.yml" ]; then
    echo "Stopping containers using docker-compose..."
    docker-compose down || { echo -e "${RED}Failed to stop containers with docker-compose${NC}"; }
else
    echo -e "${YELLOW}docker-compose.yml not found in current directory.${NC}"
    
    if [ ! -z "$RUNNING_CONTAINERS" ]; then
        if confirm "Stop all e2e3d-related containers manually?"; then
            echo "Stopping e2e3d containers..."
            docker stop $(docker ps --filter name=e2e3d -q)
            echo -e "${GREEN}Containers stopped.${NC}"
        else
            echo "Skipping container shutdown."
        fi
    fi
fi

# Offer option to remove all containers
if docker ps -a --filter name=e2e3d -q | grep -q .; then
    echo -e "\n${BOLD}Step 4: Managing stopped containers${NC}"
    if confirm "Remove all stopped e2e3d containers?"; then
        docker rm $(docker ps -a --filter name=e2e3d -q)
        echo -e "${GREEN}Containers removed.${NC}"
    else
        echo "Keeping stopped containers."
    fi
fi

# Offer data cleanup options
echo -e "\n${BOLD}Step 5: Data management${NC}"
DATA_OPTION=""
PS3="Select data cleanup option (1-4): "
options=("Keep all data" "Remove temporary files only" "Remove all generated data" "Remove EVERYTHING (including input videos)")

select opt in "${options[@]}"
do
    case $opt in
        "Keep all data")
            echo "Keeping all data intact."
            DATA_OPTION="keep"
            break
            ;;
        "Remove temporary files only")
            echo "Will remove temporary files but keep original videos and final models."
            DATA_OPTION="temp"
            break
            ;;
        "Remove all generated data")
            echo "Will remove all generated data but keep original videos."
            DATA_OPTION="generated"
            break
            ;;
        "Remove EVERYTHING (including input videos)")
            echo -e "${RED}WARNING: This will delete ALL data including your input videos!${NC}"
            if confirm "Are you absolutely sure?"; then
                if confirm "Really? This cannot be undone!"; then
                    DATA_OPTION="all"
                    break
                else
                    echo "Operation cancelled."
                    DATA_OPTION="keep"
                    break
                fi
            else
                echo "Operation cancelled."
                DATA_OPTION="keep"
                break
            fi
            ;;
        *) echo "Invalid option $REPLY";;
    esac
done

# Handle data cleanup based on selection
if [ "$DATA_OPTION" = "temp" ]; then
    echo -e "\n${BOLD}Cleaning up temporary files...${NC}"
    if [ -d "data/output/colmap_workspace" ]; then
        rm -rf data/output/colmap_workspace
        echo "Removed COLMAP workspace"
    fi
    # More temp files can be added here
elif [ "$DATA_OPTION" = "generated" ]; then
    echo -e "\n${BOLD}Removing all generated data...${NC}"
    if [ -d "data/input" ]; then
        rm -rf data/input/*
        echo "Cleared input frames"
    fi
    if [ -d "data/output" ]; then
        rm -rf data/output/*
        echo "Cleared output data"
    fi
    if [ -d "airflow/logs" ]; then
        rm -rf airflow/logs/*
        echo "Cleared Airflow logs"
    fi
elif [ "$DATA_OPTION" = "all" ]; then
    echo -e "\n${BOLD}${RED}Removing ALL data...${NC}"
    if [ -d "data" ]; then
        rm -rf data/*
        echo "Cleared all data directories"
    fi
    if [ -d "airflow/logs" ]; then
        rm -rf airflow/logs/*
        echo "Cleared Airflow logs"
    fi
fi

# Offer to remove Docker volumes
echo -e "\n${BOLD}Step 6: Docker volume management${NC}"
if confirm "List Docker volumes related to e2e3d?"; then
    VOLUMES=$(docker volume ls --filter name=e2e3d -q)
    if [ -z "$VOLUMES" ]; then
        echo "No e2e3d volumes found."
    else
        echo -e "Found the following e2e3d volumes:\n$VOLUMES"
        if confirm "Remove these volumes? (WARNING: All data in these volumes will be lost)"; then
            docker volume rm $VOLUMES
            echo -e "${GREEN}Volumes removed.${NC}"
        else
            echo "Keeping volumes."
        fi
    fi
fi

# Offer to clean Docker cache
echo -e "\n${BOLD}Step 7: Docker system cleanup${NC}"
if confirm "Would you like to clean up unused Docker resources (cache, etc)?"; then
    echo "Cleaning up Docker system..."
    docker system prune -f
    echo -e "${GREEN}Docker system cleaned.${NC}"
fi

echo -e "\n${BOLD}${GREEN}Shutdown complete!${NC}"
echo -e "The E2E3D pipeline has been successfully shut down and cleaned up according to your preferences."
echo -e "To restart the pipeline, use: ${BOLD}docker-compose up -d${NC}"
echo

exit 0 