#!/bin/bash
set -e

# Print environment summary
echo "========================================"
echo "E2E3D Airflow Environment"
echo "========================================"
echo "Airflow home: $AIRFLOW_HOME"
echo "Airflow version: $(airflow version)"
echo "========================================"

# Create required directories
mkdir -p "$AIRFLOW_HOME/data/input"
mkdir -p "$AIRFLOW_HOME/data/output"
mkdir -p "$AIRFLOW_HOME/data/videos"

# Make sure DAGs directory is accessible
chmod -R 775 "$AIRFLOW_HOME/dags" || true

# Pass control to the Airflow entrypoint
exec /entrypoint "$@" 