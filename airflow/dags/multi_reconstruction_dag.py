#!/usr/bin/env python3
"""
Airflow DAG for the complete ETL pipeline:
1. Extract - Find image sets and prepare for reconstruction
2. Transform - Run 3D reconstruction on image sets using Docker
3. Load - Store models in MinIO and process data with Spark
"""
import os
import json
import boto3
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from botocore.client import Config

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.utils.dates import days_ago

# Default arguments for DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# MinIO configuration from environment variables
MINIO_HOST = os.environ.get('MINIO_HOST', 'minio')
MINIO_PORT = int(os.environ.get('MINIO_PORT', 9000))
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'models')
INPUT_BUCKET = 'input'
OUTPUT_BUCKET = 'output'

# Spark configuration
SPARK_MASTER = os.environ.get('SPARK_MASTER', 'spark://spark-master:7077')

# Define the DAG
with DAG(
    'e2e3d_etl_pipeline',
    default_args=default_args,
    description='ETL Pipeline for 3D reconstruction and processing',
    schedule_interval=None,
    start_date=days_ago(1),
    catchup=False,
    tags=['reconstruction', '3d', 'etl', 'spark', 'minio'],
) as dag:

    # Initialize MinIO client
    def init_minio_client():
        """Initialize and return a MinIO S3 client"""
        return boto3.client(
            's3',
            endpoint_url=f'http://{MINIO_HOST}:{MINIO_PORT}',
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
    
    # Task: Check if MinIO is accessible
    def check_minio_connection(**kwargs):
        """Check if MinIO is accessible and buckets exist"""
        try:
            s3_client = init_minio_client()
            
            # Check if we can list buckets
            buckets = s3_client.list_buckets()
            bucket_names = [bucket['Name'] for bucket in buckets['Buckets']]
            
            print(f"Connected to MinIO. Available buckets: {', '.join(bucket_names)}")
            
            # Check if our required buckets exist
            missing_buckets = []
            for bucket in [MINIO_BUCKET, INPUT_BUCKET, OUTPUT_BUCKET]:
                if bucket not in bucket_names:
                    missing_buckets.append(bucket)
            
            if missing_buckets:
                print(f"Warning: These buckets are missing: {', '.join(missing_buckets)}")
                print("Attempting to create missing buckets...")
                for bucket in missing_buckets:
                    s3_client.create_bucket(Bucket=bucket)
                print("Buckets created successfully")
            
            return True
        except Exception as e:
            print(f"Error connecting to MinIO: {str(e)}")
            raise

    # Task: Find image sets and upload to MinIO if needed
    def find_and_upload_image_sets(**kwargs):
        """Find all image sets in the input directory and upload to MinIO if needed"""
        s3_client = init_minio_client()
        input_path = Path('/opt/airflow/data/input')
        image_sets = []
        
        # Look for all valid directories that might contain image sets
        for item in input_path.glob('*'):
            if item.is_dir() and not item.name.startswith('.'):
                image_set_name = item.name
                image_sets.append(image_set_name)
                
                # Check if this image set is already in MinIO
                try:
                    s3_client.head_object(Bucket=INPUT_BUCKET, Key=f"{image_set_name}/")
                    print(f"Image set {image_set_name} already exists in MinIO")
                except:
                    print(f"Uploading image set {image_set_name} to MinIO...")
                    
                    # Upload all images in the directory
                    for image_file in item.glob('*.*'):
                        if image_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                            s3_client.upload_file(
                                str(image_file),
                                INPUT_BUCKET,
                                f"{image_set_name}/{image_file.name}"
                            )
                    
                    print(f"Uploaded image set {image_set_name} to MinIO")
        
        if not image_sets:
            raise Exception("No image sets found in input directory")
        
        # Log the found image sets
        print(f"Found {len(image_sets)} image sets: {', '.join(image_sets)}")
        
        # Return the image sets for downstream tasks
        return image_sets

    # Generate dynamic tasks for each image set
    def generate_reconstruction_tasks(**kwargs):
        """Generate reconstruction tasks for each image set."""
        ti = kwargs['ti']
        image_sets = ti.xcom_pull(task_ids='find_and_upload_image_sets')
        
        reconstruction_results = []
        for image_set in image_sets:
            task_id = f'reconstruct_{image_set}'
            
            # Create a BashOperator for each image set
            reconstruct_task = BashOperator(
                task_id=task_id,
                bash_command=f'''
                # Create output directories if they don't exist
                mkdir -p /opt/airflow/data/output/models/{image_set}/mesh
                
                # Run reconstruction using Docker
                docker run --rm \
                -v /opt/airflow/data/input:/app/data/input \
                -v /opt/airflow/data/output:/app/data/output \
                -e QUALITY_PRESET=medium \
                e2e3d-reconstruction \
                /app/data/input/{image_set} \
                --output /app/data/output/models/{image_set} \
                --quality medium \
                --verbose
                
                # Capture exit status
                status=$?
                
                # Create a result JSON entry for this image set
                echo '{{"image_set": "{image_set}", "status": "'${{status}}' == 0 ? "success" : "failure"'", "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'", "model_path": "/opt/airflow/data/output/models/{image_set}/mesh/reconstructed_mesh.obj"}}' > /tmp/{image_set}_result.json
                
                # Return success only if Docker command succeeded
                exit $status
                ''',
            )
            
            # Ensure the task depends on finding image sets
            check_minio_task >> find_upload_task >> reconstruct_task
            reconstruction_results.append(task_id)
        
        # Return the list of task IDs for the upload models task
        return reconstruction_results

    # Task: Upload reconstructed models to MinIO
    def upload_models_to_minio(**kwargs):
        """Upload the reconstructed 3D models to MinIO"""
        ti = kwargs['ti']
        task_ids = ti.xcom_pull(task_ids='generate_reconstruction_tasks')
        
        s3_client = init_minio_client()
        results = []
        
        for task_id in task_ids:
            image_set = task_id.replace('reconstruct_', '')
            
            try:
                # Read the result JSON
                with open(f'/tmp/{image_set}_result.json', 'r') as f:
                    result = json.load(f)
                
                # Only upload if reconstruction was successful
                if result['status'] == 'success':
                    model_path = f"/opt/airflow/data/output/models/{image_set}/mesh/reconstructed_mesh.obj"
                    
                    if os.path.exists(model_path):
                        # Upload the model to MinIO
                        s3_key = f"models/{image_set}/mesh/reconstructed_mesh.obj"
                        s3_client.upload_file(model_path, MINIO_BUCKET, s3_key)
                        
                        # Update the result with MinIO path
                        result['minio_path'] = f"s3://{MINIO_BUCKET}/{s3_key}"
                        print(f"Uploaded model for {image_set} to MinIO: {result['minio_path']}")
                    else:
                        result['status'] = 'warning'
                        result['message'] = f"Model file not found at {model_path}"
                        print(f"Warning: Model file for {image_set} not found")
                
                results.append(result)
            except Exception as e:
                print(f"Error processing result for {image_set}: {str(e)}")
                results.append({
                    'image_set': image_set,
                    'status': 'error',
                    'message': str(e)
                })
        
        # Write metadata for Spark job
        model_metadata = []
        for result in results:
            if result.get('status') == 'success' and result.get('minio_path'):
                model_metadata.append({
                    'model_id': f"model_{result['image_set']}",
                    'image_set': result['image_set'],
                    'reconstruction_date': result.get('timestamp', datetime.utcnow().isoformat()),
                    'file_path': result['minio_path']
                })
        
        # Write metadata to temp file and upload to MinIO
        if model_metadata:
            metadata_file = '/tmp/model_metadata.json'
            with open(metadata_file, 'w') as f:
                json.dump(model_metadata, f, indent=2)
            
            s3_client.upload_file(metadata_file, MINIO_BUCKET, 'metadata/model_metadata.json')
            print("Uploaded model metadata to MinIO")
        
        return results

    # Task: Generate summary report
    def generate_summary_report(**kwargs):
        """Generate a summary report of all reconstruction and storage tasks."""
        ti = kwargs['ti']
        upload_results = ti.xcom_pull(task_ids='upload_models_to_minio')
        
        success_count = sum(1 for r in upload_results if r.get('status') == 'success')
        warning_count = sum(1 for r in upload_results if r.get('status') == 'warning')
        error_count = sum(1 for r in upload_results if r.get('status') in ['error', 'failure'])
        
        # Create the summary report
        summary = {
            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'image_sets_processed': len(upload_results),
            'successes': success_count,
            'warnings': warning_count,
            'errors': error_count,
            'details': upload_results
        }
        
        # Write the summary report to a local file
        summary_path = '/opt/airflow/data/output/reconstruction_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Upload summary to MinIO
        s3_client = init_minio_client()
        s3_client.upload_file(summary_path, OUTPUT_BUCKET, 'reconstruction_summary.json')
        
        print(f"Summary report generated: {success_count} successes, {warning_count} warnings, {error_count} errors")
        return summary

    # Task definitions
    check_minio_task = PythonOperator(
        task_id='check_minio_connection',
        python_callable=check_minio_connection,
        provide_context=True,
    )
    
    find_upload_task = PythonOperator(
        task_id='find_and_upload_image_sets',
        python_callable=find_and_upload_image_sets,
        provide_context=True,
    )
    
    generate_tasks = PythonOperator(
        task_id='generate_reconstruction_tasks',
        python_callable=generate_reconstruction_tasks,
        provide_context=True,
    )
    
    upload_models_task = PythonOperator(
        task_id='upload_models_to_minio',
        python_callable=upload_models_to_minio,
        provide_context=True,
    )
    
    spark_process_task = SparkSubmitOperator(
        task_id='process_models_with_spark',
        application='/opt/airflow/jobs/process_models.py',
        name='3D_Model_Processing',
        conn_id='spark_default',
        verbose=True,
        conf={
            'spark.master': SPARK_MASTER,
            'spark.executor.memory': '2g',
            'spark.driver.memory': '1g',
            'spark.executor.cores': '2',
            'spark.python.profile': 'false',
            'spark.submit.deployMode': 'client',
        },
        application_args=[
            '--minio-host', MINIO_HOST,
            '--minio-port', str(MINIO_PORT),
            '--minio-access-key', MINIO_ACCESS_KEY,
            '--minio-secret-key', MINIO_SECRET_KEY,
            '--minio-bucket', MINIO_BUCKET
        ],
        env_vars={
            'MINIO_HOST': MINIO_HOST,
            'MINIO_PORT': str(MINIO_PORT),
            'MINIO_ACCESS_KEY': MINIO_ACCESS_KEY,
            'MINIO_SECRET_KEY': MINIO_SECRET_KEY,
            'MINIO_BUCKET': MINIO_BUCKET
        }
    )
    
    summary_task = PythonOperator(
        task_id='generate_summary_report',
        python_callable=generate_summary_report,
        provide_context=True,
    )
    
    # Set up task dependencies for the ETL pipeline
    check_minio_task >> find_upload_task >> generate_tasks
    generate_tasks >> upload_models_task >> spark_process_task >> summary_task 