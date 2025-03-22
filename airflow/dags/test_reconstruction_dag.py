"""
E2E3D Test Reconstruction DAG

This DAG implements a simplified test for the E2E3D reconstruction pipeline.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
import os
import json
import platform
import socket
import subprocess

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Create the DAG
with DAG(
    'test_reconstruction_pipeline',
    default_args=default_args,
    description='Test the E2E3D reconstruction pipeline',
    schedule_interval=None,
    start_date=datetime(2022, 1, 1),
    catchup=False,
    tags=['e2e3d', 'test', 'reconstruction']
) as dag:

    # Start task
    start = DummyOperator(
        task_id='start'
    )

    # Check if Docker is available
    check_docker = BashOperator(
        task_id='check_docker',
        bash_command='if ! command -v docker &> /dev/null; then echo "Docker not found"; exit 1; else echo "Docker is available"; fi'
    )

    # Create necessary directories
    create_directories = BashOperator(
        task_id='create_directories',
        bash_command='''
            mkdir -p ${AIRFLOW_HOME}/data/input
            mkdir -p ${AIRFLOW_HOME}/data/output
            mkdir -p ${AIRFLOW_HOME}/data/reports
            echo "Directories created successfully"
        '''
    )

    # Download Sample Data - using a simplified Docker approach
    download_sample_data = BashOperator(
        task_id='download_sample_data',
        bash_command='''
            DATASET="{{ dag_run.conf.get('dataset', 'CognacStJacquesDoor') }}"
            
            docker run --rm \
                -v ${AIRFLOW_HOME}/data:/app/data \
                -v ${AIRFLOW_HOME}/scripts:/app/scripts \
                -w /app \
                python:3.7.9-slim \
                bash -c "
                    echo 'Testing E2E3D with Python 3.7.9'
                    apt-get update && 
                    apt-get install -y --no-install-recommends wget unzip git &&
                    pip install tqdm requests numpy Pillow &&
                    mkdir -p /app/data/input/${DATASET} &&
                    if [ ! -d /app/data/input/${DATASET} ] || [ -z \"$(ls -A /app/data/input/${DATASET})\" ]; then
                        echo 'Downloading sample data...'
                        python /app/scripts/download_sample_data.py ${DATASET} /app/data/input
                    fi &&
                    echo 'Sample data check:' &&
                    IMG_COUNT=$(find /app/data/input/${DATASET} -type f -name '*.jpg' -o -name '*.png' | wc -l) &&
                    echo 'Found ${IMG_COUNT} images in dataset ${DATASET}'
                "
            
            if [ $? -eq 0 ]; then
                echo "Sample data download completed successfully"
            else
                echo "Sample data download failed"
                exit 1
            fi
        '''
    )

    # Function to generate a test report
    def generate_test_report(**kwargs):
        dataset = kwargs['dag_run'].conf.get('dataset', 'CognacStJacquesDoor')
        airflow_home = os.environ.get('AIRFLOW_HOME', '/opt/airflow')
        
        # Create report directory if it doesn't exist
        report_dir = f"{airflow_home}/data/reports"
        os.makedirs(report_dir, exist_ok=True)
        
        # Get system information
        system_info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Count images in the input directory
        input_dir = f"{airflow_home}/data/input/{dataset}"
        image_count = 0
        if os.path.exists(input_dir):
            image_files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
            image_count = len(image_files)
        
        # Create the report
        report = {
            "system_info": system_info,
            "dataset": dataset,
            "test_results": {
                "images_found": image_count,
                "status": "success" if image_count > 0 else "failure",
                "message": f"Found {image_count} images in dataset {dataset}"
            }
        }
        
        # Write the report to a file
        report_file = f"{report_dir}/test_report_{dataset}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Test report generated: {report_file}")
        print(f"Test status: {report['test_results']['status']}")
        print(f"Images found: {report['test_results']['images_found']}")
        
        return report_file

    # Generate test report
    generate_report = PythonOperator(
        task_id='generate_report',
        python_callable=generate_test_report,
        provide_context=True
    )

    # End task
    end = DummyOperator(
        task_id='end'
    )

    # Define task dependencies
    start >> check_docker >> create_directories >> download_sample_data >> generate_report >> end 