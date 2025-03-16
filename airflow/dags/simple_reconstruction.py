import os
import glob
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

import logging
import subprocess

# Configure paths
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
INPUT_PATH = os.path.join(PROJECT_PATH, 'input')
OUTPUT_PATH = os.path.join(PROJECT_PATH, 'output')
COLMAP_PATH = os.environ.get('COLMAP_PATH', 'colmap')

# Ensure directories exist
os.makedirs(INPUT_PATH, exist_ok=True)
os.makedirs(OUTPUT_PATH, exist_ok=True)

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
dag = DAG(
    'simple_reconstruction',
    default_args=default_args,
    description='Simple 3D reconstruction pipeline',
    schedule_interval=None,
    start_date=days_ago(1),
    tags=['3d', 'reconstruction', 'colmap'],
)

# Check if input frames exist
def check_input_frames(**kwargs):
    frames = glob.glob(os.path.join(INPUT_PATH, '*.jpg')) + glob.glob(os.path.join(INPUT_PATH, '*.png'))
    if not frames:
        raise Exception(f"No image frames found in {INPUT_PATH}")
    
    logging.info(f"Found {len(frames)} frames in {INPUT_PATH}")
    return len(frames)

# Create workspace directories
def create_workspace(**kwargs):
    workspace_dir = os.path.join(OUTPUT_PATH, 'colmap_workspace')
    database_dir = os.path.join(workspace_dir, 'database')
    sparse_dir = os.path.join(workspace_dir, 'sparse')
    
    os.makedirs(workspace_dir, exist_ok=True)
    os.makedirs(database_dir, exist_ok=True)
    os.makedirs(sparse_dir, exist_ok=True)
    
    logging.info(f"Created workspace directories in {workspace_dir}")
    return {
        'workspace_dir': workspace_dir,
        'database_dir': database_dir,
        'sparse_dir': sparse_dir
    }

# Run COLMAP feature extraction
def run_feature_extraction(**kwargs):
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    database_path = os.path.join(workspace_info['database_dir'], 'database.db')
    
    cmd = f"{COLMAP_PATH} feature_extractor --database_path {database_path} --image_path {INPUT_PATH}"
    logging.info(f"Running command: {cmd}")
    
    try:
        subprocess.run(cmd, shell=True, check=True)
        logging.info("Feature extraction completed successfully")
        return database_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Feature extraction failed: {str(e)}")
        raise

# Define tasks
check_frames_task = PythonOperator(
    task_id='check_input_frames',
    python_callable=check_input_frames,
    dag=dag,
)

create_workspace_task = PythonOperator(
    task_id='create_workspace',
    python_callable=create_workspace,
    dag=dag,
)

feature_extraction_task = PythonOperator(
    task_id='run_feature_extraction',
    python_callable=run_feature_extraction,
    dag=dag,
)

# Define task dependencies
check_frames_task >> create_workspace_task >> feature_extraction_task 