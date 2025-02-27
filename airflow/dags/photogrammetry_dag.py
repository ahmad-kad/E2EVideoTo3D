from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.dates import days_ago
from datetime import timedelta
import os
import logging

# Import custom modules (assuming they're in the Python path)
from src.ingestion.frame_extractor import extract_frames
from src.utils.validators import validate_video
from src.processing.spark_processor import create_spark_session, process_frames
from src.storage.minio_client import MinioClient

# Default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'sla': timedelta(minutes=30)
}

# DAG definition
dag = DAG(
    'photogrammetry_pipeline',
    default_args=default_args,
    description='Process videos into 3D models using photogrammetry',
    schedule_interval=timedelta(hours=1),
    catchup=False,
    tags=['photogrammetry', '3d-models']
)

# GPU resource configuration for Meshroom tasks
gpu_resources = {
    "limit": {"nvidia.com/gpu": 1},
    "requests": {"memory": "8Gi", "cpu": "2"}
}

# Task definitions
def _validate_video(video_path, **kwargs):
    validation_result = validate_video(video_path)
    if not validation_result['validation_passed']:
        raise ValueError(f"Video validation failed: {validation_result['validation_results']}")
    return validation_result

def _extract_frames(video_path, output_dir, **kwargs):
    return extract_frames(video_path, output_dir)

def _process_frames(input_dir, output_dir, **kwargs):
    spark = create_spark_session()
    process_frames(spark, input_dir, output_dir)
    return output_dir

def _run_meshroom(input_dir, output_dir, **kwargs):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Run Meshroom (simplified version)
    cmd = f"meshroom_batch --input {input_dir} --output {output_dir}"
    exit_code = os.system(cmd)
    
    if exit_code != 0:
        raise Exception(f"Meshroom failed with exit code {exit_code}")
    
    return output_dir

# DAG tasks
with dag:
    # Watch for new videos in MinIO
    watch_new_video = S3KeySensor(
        task_id='watch_new_video',
        bucket_name='raw-videos',
        bucket_key='*.mp4',
        aws_conn_id='minio_conn',
        mode='poke',
        poke_interval=300,  # 5 minutes
        timeout=60 * 60 * 2  # 2 hours
    )
    
    # Validate video
    validate_video_task = PythonOperator(
        task_id='validate_video',
        python_callable=_validate_video,
        op_kwargs={
            'video_path': "{{ ti.xcom_pull(task_ids='watch_new_video') }}"
        }
    )
    
    # Extract frames
    extract_frames_task = PythonOperator(
        task_id='extract_frames',
        python_callable=_extract_frames,
        op_kwargs={
            'video_path': "{{ ti.xcom_pull(task_ids='watch_new_video') }}",
            'output_dir': '/tmp/frames/{{ dag_run.id }}'
        }
    )
    
    # Process frames with Spark
    process_frames_task = PythonOperator(
        task_id='process_frames',
        python_callable=_process_frames,
        op_kwargs={
            'input_dir': '/tmp/frames/{{ dag_run.id }}',
            'output_dir': '/tmp/processed_frames/{{ dag_run.id }}'
        }
    )
    
    # Run Meshroom
    run_meshroom_task = PythonOperator(
        task_id='run_meshroom',
        python_callable=_run_meshroom,
        op_kwargs={
            'input_dir': '/tmp/processed_frames/{{ dag_run.id }}',
            'output_dir': '/tmp/models/{{ dag_run.id }}'
        },
        executor_config={"resources": gpu_resources}
    )
    
    # Task dependencies
    watch_new_video >> validate_video_task >> extract_frames_task >> process_frames_task >> run_meshroom_task 