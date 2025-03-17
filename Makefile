# Makefile for e2e3d

# Variables
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker-compose
PYTEST := pytest
FLAKE8 := flake8
BLACK := black

.PHONY: help setup clean test lint format docs docker-build docker-run docker-stop

# Default target
all: help

# Help target
help:
	@echo "Available targets:"
	@echo "  setup         - Install dependencies"
	@echo "  clean         - Clean up temporary files"
	@echo "  test          - Run tests"
	@echo "  lint          - Check code style with flake8"
	@echo "  format        - Format code with black"
	@echo "  docs          - Generate documentation"
	@echo "  docker-build  - Build Docker images"
	@echo "  docker-run    - Run Docker services"
	@echo "  docker-stop   - Stop Docker services"
	@echo "  reconstruct   - Run reconstruction on an image set"

# Setup target
setup:
	$(PIP) install -r requirements-common.txt -r requirements-reconstruction.txt
	chmod +x scripts/*.sh scripts/*.py
	chmod +x run.sh reconstruct.py
	./install_mesh_tools.sh

# Clean target
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".tox" -exec rm -rf {} +
	find . -type f -name "*.log" -exec rm -f {} +

# Test target
test:
	$(PYTEST) tests/

# Lint target
lint:
	$(FLAKE8) src/ tests/

# Format target
format:
	$(BLACK) src/ tests/

# Documentation target
docs:
	mkdir -p docs/api
	$(PYTHON) scripts/generate_docs.py src

# Docker targets
docker-build:
	./run.sh build

docker-run:
	./run.sh

docker-stop:
	$(DOCKER_COMPOSE) down

# Reconstruct target
reconstruct:
	@if [ -z "$(IMAGE_SET)" ]; then \
		echo "Error: IMAGE_SET is required. Usage: make reconstruct IMAGE_SET=YourImageSet"; \
		exit 1; \
	fi
	./scripts/run_reconstruction.sh $(IMAGE_SET) 