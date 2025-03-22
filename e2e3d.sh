#!/bin/bash

# E2E3D Production Environment Launcher

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}E2E3D - 3D Reconstruction Pipeline${NC}"
echo -e "${GREEN}=======================================${NC}"
echo -e "${YELLOW}This script is a convenience launcher for the E2E3D production environment.${NC}"
echo -e "${BLUE}Starting E2E3D Production Environment...${NC}"
echo ""

# Navigate to production directory and run the production environment
cd production
./scripts/run_production.sh $@

# Print helpful message on exit
echo ""
echo -e "${GREEN}=======================================${NC}"
echo -e "${YELLOW}To stop the E2E3D environment, run:${NC}"
echo -e "${BLUE}cd production && ./scripts/run_production.sh stop${NC}"
echo -e "${GREEN}=======================================${NC}" 