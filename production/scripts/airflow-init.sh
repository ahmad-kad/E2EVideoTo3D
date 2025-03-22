#!/bin/bash
set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function info() {
    echo -e "${GREEN}INFO: $1${NC}"
}

function warn() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

function error() {
    echo -e "${RED}ERROR: $1${NC}"
}

info "Starting Airflow initialization..."
info "Checking database connection..."

# Wait for database to be ready
while ! airflow db check > /dev/null 2>&1; do
    warn "Waiting for database to be ready..."
    sleep 5
done

info "Database connection successful!"

# Initialize the database if not already done
if ! airflow db check; then
    info "Initializing Airflow database..."
    airflow db init
else
    info "Airflow database already initialized"
fi

# Create default user if it doesn't exist
if ! airflow users list | grep -q "${_AIRFLOW_WWW_USER_USERNAME:-admin}"; then
    info "Creating admin user..."
    airflow users create \
        --username "${_AIRFLOW_WWW_USER_USERNAME:-admin}" \
        --password "${_AIRFLOW_WWW_USER_PASSWORD:-admin}" \
        --firstname "Admin" \
        --lastname "User" \
        --role "Admin" \
        --email "admin@example.com"
else
    info "Admin user already exists"
fi

# Create default Airflow Variables for e2e3d
if ! airflow variables get e2e3d_input_dir >/dev/null 2>&1; then
    info "Creating Airflow Variables for E2E3D..."
    airflow variables set e2e3d_input_dir "/opt/airflow/data/input"
    airflow variables set e2e3d_output_dir "/opt/airflow/data/output"
    airflow variables set e2e3d_quality "medium"
    airflow variables set e2e3d_use_gpu "false"
    airflow variables set e2e3d_minio_endpoint "minio:9000"
    airflow variables set e2e3d_minio_access_key "minioadmin"
    airflow variables set e2e3d_minio_secret_key "minioadmin"
else
    info "E2E3D Variables already set"
fi

# Create default connections
if ! airflow connections get minio >/dev/null 2>&1; then
    info "Creating Airflow Connection for MinIO..."
    airflow connections add minio \
        --conn-type 'aws' \
        --conn-host 'minio' \
        --conn-port '9000' \
        --conn-login 'minioadmin' \
        --conn-password 'minioadmin' \
        --conn-extra '{"endpoint_url": "http://minio:9000", "region_name": "us-east-1"}'
else
    info "MinIO connection already exists"
fi

if ! airflow connections get reconstruction_api >/dev/null 2>&1; then
    info "Creating Airflow Connection for Reconstruction API..."
    airflow connections add reconstruction_api \
        --conn-type 'http' \
        --conn-host 'reconstruction-service' \
        --conn-port '5000' \
        --conn-schema 'http'
else
    info "Reconstruction API connection already exists"
fi

# Create example DAG if it doesn't exist
if [ ! -f "/opt/airflow/dags/example_dag.py" ]; then
    info "Creating example DAG..."
    cat > /opt/airflow/dags/example_dag.py <<EOL
"""
Example DAG for testing Airflow

This DAG simply prints the current date and sleeps for 5 seconds.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'example_dag',
    default_args=default_args,
    description='Example DAG for testing',
    schedule_interval=None,
    start_date=days_ago(1),
    tags=['example'],
) as dag:
    t1 = BashOperator(
        task_id='print_date',
        bash_command='date',
    )
    
    t2 = BashOperator(
        task_id='sleep',
        bash_command='sleep 5',
    )
    
    t1 >> t2
EOL
else
    info "Example DAG already exists"
fi

info "Airflow initialization completed!"

# Now execute the CMD
exec "$@" 