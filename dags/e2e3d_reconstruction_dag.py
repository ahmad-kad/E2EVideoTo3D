"""
E2E3D Reconstruction Airflow DAG

This DAG orchestrates the 3D reconstruction pipeline using Airflow.
It processes input images, runs the reconstruction, and uploads the result to MinIO.
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
import json

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.utils.trigger_rule import TriggerRule

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define environment variables
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
INPUT_PATH = os.environ.get('INPUT_PATH', os.path.join(PROJECT_PATH, 'input'))
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', os.path.join(PROJECT_PATH, 'output'))
QUALITY_PRESET = os.environ.get('QUALITY_PRESET', 'medium')
USE_GPU = os.environ.get('USE_GPU', 'auto')

# MinIO configuration
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', 'http://minio:9000')
S3_BUCKET = os.environ.get('S3_BUCKET', 'models')
S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY', 'minioadmin')
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY', 'minioadmin')

def get_image_sets():
    """Get list of available image sets."""
    image_sets = []
    for entry in os.listdir(INPUT_PATH):
        if os.path.isdir(os.path.join(INPUT_PATH, entry)):
            image_sets.append(entry)
    return image_sets

def upload_to_minio(mesh_file, **kwargs):
    """Upload the mesh file to MinIO."""
    import logging
    from minio import Minio
    from minio.error import S3Error
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('upload_to_minio')
    
    try:
        client = Minio(
            S3_ENDPOINT.replace('http://', '').replace('https://', ''),
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
            secure=S3_ENDPOINT.startswith('https')
        )
        
        # Check if bucket exists, create if not
        if not client.bucket_exists(S3_BUCKET):
            logger.info(f"Creating bucket: {S3_BUCKET}")
            client.make_bucket(S3_BUCKET)
            # Set bucket policy to allow downloads
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{S3_BUCKET}/*"]
                    }
                ]
            }
            client.set_bucket_policy(S3_BUCKET, json.dumps(policy))
        
        # Upload file
        filename = os.path.basename(mesh_file)
        logger.info(f"Uploading {mesh_file} to bucket '{S3_BUCKET}' as {filename}")
        
        client.fput_object(
            S3_BUCKET, 
            filename, 
            mesh_file,
            content_type="application/octet-stream"
        )
        
        # Get download URL
        download_url = f"{S3_ENDPOINT}/{S3_BUCKET}/{filename}"
        logger.info(f"Upload successful. Download URL: {download_url}")
        
        # Store the URL in XCom for downstream tasks
        kwargs['ti'].xcom_push(key='mesh_url', value=download_url)
        
        return download_url
        
    except Exception as err:
        logger.error(f"Error in upload_to_minio: {err}")
        raise

# Create the DAG
with DAG(
    'e2e3d_reconstruction',
    default_args=default_args,
    description='3D Reconstruction Pipeline',
    schedule_interval=None,
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['e2e3d', '3d', 'reconstruction'],
) as dag:
    
    # Task to check directories and environment
    check_env = BashOperator(
        task_id='check_environment',
        bash_command=f"""
            echo "Checking environment..."
            mkdir -p {OUTPUT_PATH}
            echo "Quality preset: {QUALITY_PRESET}"
            echo "Use GPU: {USE_GPU}"
            echo "Input path: {INPUT_PATH}"
            echo "Output path: {OUTPUT_PATH}"
            ls -la {INPUT_PATH}
        """,
    )
    
    # Dynamic tasks for each image set
    image_sets = get_image_sets()
    
    if not image_sets:
        empty_check = BashOperator(
            task_id='no_image_sets_found',
            bash_command='echo "No image sets found in the input directory."',
        )
        check_env >> empty_check
    else:
        for image_set in image_sets:
            input_dir = os.path.join(INPUT_PATH, image_set)
            output_dir = os.path.join(OUTPUT_PATH, image_set)
            mesh_path = os.path.join(output_dir, 'mesh', 'reconstructed_mesh.obj')
            
            # Create output directory
            create_output_dir = BashOperator(
                task_id=f'create_output_dir_{image_set}',
                bash_command=f'mkdir -p {output_dir}/mesh',
            )
            
            # Run reconstruction
            run_reconstruction = BashOperator(
                task_id=f'reconstruction_{image_set}',
                bash_command=f"""
                    echo "Running reconstruction for {image_set}..."
                    python3 /opt/airflow/reconstruct.py {input_dir} --output {output_dir} --quality {QUALITY_PRESET} --use-gpu {USE_GPU}
                """,
            )
            
            # Upload mesh to MinIO
            upload_mesh = PythonOperator(
                task_id=f'upload_mesh_{image_set}',
                python_callable=upload_to_minio,
                op_kwargs={'mesh_file': mesh_path},
                trigger_rule=TriggerRule.ALL_SUCCESS,
            )
            
            # Log completion
            log_completion = BashOperator(
                task_id=f'log_completion_{image_set}',
                bash_command=f"""
                    echo "Reconstruction completed for {image_set}"
                    echo "Mesh saved to: {mesh_path}"
                    echo "Download URL: {{ task_instance.xcom_pull(task_ids='upload_mesh_{image_set}', key='mesh_url') }}"
                """,
            )
            
            # Define task dependencies
            check_env >> create_output_dir >> run_reconstruction >> upload_mesh >> log_completion 