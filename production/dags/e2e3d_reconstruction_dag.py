"""
E2E3D Reconstruction Pipeline DAG

This DAG orchestrates the 3D reconstruction process:
1. Checks for input images in a specified directory
2. Runs the reconstruction process
3. Uploads the resulting 3D mesh to MinIO storage
"""

from datetime import datetime, timedelta
import os
import logging
import json
import subprocess
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.sensors.filesystem import FileSensor
from airflow.models import Variable
from airflow.utils.dates import days_ago

# Setup logging
logger = logging.getLogger("e2e3d_reconstruction_dag")

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Get configuration from environment variables with defaults
DEFAULT_INPUT_DIR = "/opt/airflow/data/input"
DEFAULT_OUTPUT_DIR = "/opt/airflow/data/output"
DEFAULT_QUALITY = "medium"
DEFAULT_USE_GPU = "false"

# Try to get configuration from Airflow Variables if set
try:
    INPUT_DIR = Variable.get("e2e3d_input_dir", DEFAULT_INPUT_DIR)
    OUTPUT_DIR = Variable.get("e2e3d_output_dir", DEFAULT_OUTPUT_DIR)
    QUALITY = Variable.get("e2e3d_quality", DEFAULT_QUALITY)
    USE_GPU = Variable.get("e2e3d_use_gpu", DEFAULT_USE_GPU).lower() == "true"
    MINIO_ENDPOINT = Variable.get("e2e3d_minio_endpoint", "minio:9000")
    MINIO_ACCESS_KEY = Variable.get("e2e3d_minio_access_key", "minioadmin")
    MINIO_SECRET_KEY = Variable.get("e2e3d_minio_secret_key", "minioadmin")
except Exception as e:
    logger.warning(f"Failed to get configuration from Airflow Variables: {e}")
    # Fall back to defaults
    INPUT_DIR = DEFAULT_INPUT_DIR
    OUTPUT_DIR = DEFAULT_OUTPUT_DIR
    QUALITY = DEFAULT_QUALITY
    USE_GPU = DEFAULT_USE_GPU.lower() == "true"
    MINIO_ENDPOINT = "minio:9000"
    MINIO_ACCESS_KEY = "minioadmin"
    MINIO_SECRET_KEY = "minioadmin"

# Define functions for the DAG
def check_input_files(input_dir, **kwargs):
    """Check if there are any image files in the input directory."""
    import glob
    
    # Common image extensions
    image_extensions = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff')
    
    input_files = []
    for ext in image_extensions:
        input_files.extend(glob.glob(os.path.join(input_dir, ext)))
        # Also check in subdirectories
        input_files.extend(glob.glob(os.path.join(input_dir, '**', ext), recursive=True))
    
    num_files = len(input_files)
    if num_files == 0:
        raise ValueError(f"No input images found in {input_dir}")
    
    logger.info(f"Found {num_files} image files in {input_dir}")
    return input_files

def run_reconstruction(input_dir, output_dir, quality, use_gpu, **kwargs):
    """Run the reconstruction process."""
    import subprocess
    import time
    
    logger.info(f"Starting reconstruction with: input={input_dir}, output={output_dir}, quality={quality}, use_gpu={use_gpu}")
    
    cmd = [
        "python3", "/opt/airflow/scripts/reconstruct.py",
        "--input", input_dir,
        "--output", output_dir,
        "--quality", quality
    ]
    
    if use_gpu:
        cmd.append("--gpu")
    
    start_time = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    end_time = time.time()
    
    if proc.returncode != 0:
        logger.error(f"Reconstruction failed: {proc.stderr}")
        raise Exception(f"Reconstruction failed: {proc.stderr}")
    
    logger.info(f"Reconstruction completed in {end_time - start_time:.2f} seconds")
    
    # Check if the mesh was created
    mesh_file = os.path.join(output_dir, "mesh", "reconstructed_mesh.obj")
    if not os.path.exists(mesh_file):
        raise FileNotFoundError(f"Reconstruction completed but mesh file not found at {mesh_file}")
    
    return mesh_file

def upload_to_minio(mesh_file, minio_endpoint, minio_access_key, minio_secret_key, **kwargs):
    """Upload the mesh file to MinIO."""
    import subprocess
    
    logger.info(f"Uploading mesh file to MinIO: {mesh_file}")
    
    cmd = [
        "python3", "/opt/airflow/scripts/upload_to_minio.py",
        mesh_file,
        "--endpoint", minio_endpoint,
        "--access-key", minio_access_key,
        "--secret-key", minio_secret_key
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True)
    
    if proc.returncode != 0:
        logger.error(f"Upload failed: {proc.stderr}")
        raise Exception(f"Upload failed: {proc.stderr}")
    
    # Try to parse the output as JSON to get the URL
    try:
        output = json.loads(proc.stdout)
        mesh_url = output.get("download_url", "Unknown")
        logger.info(f"Mesh uploaded successfully, available at: {mesh_url}")
        return mesh_url
    except json.JSONDecodeError:
        logger.warning("Could not parse upload output as JSON")
        return proc.stdout

# Create the DAG
with DAG(
    'e2e3d_reconstruction',
    default_args=default_args,
    description='E2E3D 3D Reconstruction Pipeline',
    schedule_interval=None,
    start_date=days_ago(1),
    tags=['e2e3d', 'reconstruction', '3d'],
    catchup=False,
) as dag:
    
    # Task 1: Check for input files
    check_inputs = PythonOperator(
        task_id='check_input_files',
        python_callable=check_input_files,
        op_kwargs={'input_dir': INPUT_DIR},
        dag=dag,
    )
    
    # Task 2: Create output directory if it doesn't exist
    create_output_dir = BashOperator(
        task_id='create_output_dir',
        bash_command=f'mkdir -p {OUTPUT_DIR} {OUTPUT_DIR}/mesh',
        dag=dag,
    )
    
    # Task 3: Run the reconstruction process
    reconstruct = PythonOperator(
        task_id='run_reconstruction',
        python_callable=run_reconstruction,
        op_kwargs={
            'input_dir': INPUT_DIR,
            'output_dir': OUTPUT_DIR,
            'quality': QUALITY,
            'use_gpu': USE_GPU
        },
        dag=dag,
    )
    
    # Task 4: Upload the mesh to MinIO
    upload_mesh = PythonOperator(
        task_id='upload_to_minio',
        python_callable=upload_to_minio,
        op_kwargs={
            'mesh_file': "{{ ti.xcom_pull(task_ids='run_reconstruction') }}",
            'minio_endpoint': MINIO_ENDPOINT,
            'minio_access_key': MINIO_ACCESS_KEY,
            'minio_secret_key': MINIO_SECRET_KEY
        },
        dag=dag,
    )
    
    # Define the task dependencies
    check_inputs >> create_output_dir >> reconstruct >> upload_mesh 