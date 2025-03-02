from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.sensors.s3 import S3KeySensor
from airflow.utils.dates import days_ago
from airflow.models import Connection
from airflow.settings import Session
from datetime import timedelta
import os
import logging
import sys

# Add the project root to the Python path
sys.path.append('/app')

# Import custom modules (ensuring they're in the Python path)
try:
    from src.ingestion.frame_extractor import extract_frames
    from src.utils.validators import validate_video
    from src.processing.spark_processor import create_spark_session, process_frames
    from src.storage.minio_client import MinioClient
except ImportError as e:
    logging.error(f"Module import error: {e}")
    logging.error(f"Python path: {sys.path}")
    raise

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

# MinIO connection information
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ROOT_USER', 'minioadmin') 
MINIO_SECRET_KEY = os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')

# Function to create or update Airflow connection for MinIO
def create_minio_connection():
    session = Session()
    conn = session.query(Connection).filter(Connection.conn_id == 'minio_conn').first()
    
    if not conn:
        conn = Connection(
            conn_id='minio_conn',
            conn_type='aws',
            host=MINIO_ENDPOINT.replace('http://', '').replace('https://', ''),
            login=MINIO_ACCESS_KEY,
            password=MINIO_SECRET_KEY,
            extra='{"endpoint_url": "' + MINIO_ENDPOINT + '"}'
        )
        session.add(conn)
        session.commit()
        logging.info(f"Created MinIO connection: {conn.conn_id}")
    else:
        logging.info(f"MinIO connection already exists: {conn.conn_id}")
    
    session.close()

# Ensure MinIO connection exists
try:
    create_minio_connection()
except Exception as e:
    logging.error(f"Failed to create MinIO connection: {e}")

# Paths for data processing
DATA_PATH = '/data'
FRAMES_PATH = f'{DATA_PATH}/frames'
PROCESSED_FRAMES_PATH = f'{DATA_PATH}/processed_frames'
MODELS_PATH = f'{DATA_PATH}/models'

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
    """Validate the input video file."""
    logging.info(f"Validating video: {video_path}")
    validation_result = validate_video(video_path)
    if not validation_result['validation_passed']:
        raise ValueError(f"Video validation failed: {validation_result['validation_results']}")
    return validation_result

def _extract_frames(video_path, output_dir, **kwargs):
    """Extract frames from the input video."""
    logging.info(f"Extracting frames from {video_path} to {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    return extract_frames(video_path, output_dir)

def _process_frames(input_dir, output_dir, **kwargs):
    """Process frames using PySpark."""
    logging.info(f"Processing frames from {input_dir} to {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    spark = create_spark_session()
    process_frames(spark, input_dir, output_dir)
    return output_dir

def _run_meshroom(input_dir, output_dir, **kwargs):
    """Run Meshroom photogrammetry on processed frames."""
    logging.info(f"Running Meshroom on {input_dir}, output to {output_dir}")
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Use the correct Meshroom executable path
    meshroom_cmd = "meshroom_batch"
    if os.path.exists("/usr/local/bin/meshroom_batch"):
        meshroom_cmd = "/usr/local/bin/meshroom_batch"
    
    # Run Meshroom with correct parameters
    cmd = f"{meshroom_cmd} --input {input_dir} --output {output_dir} --cache {output_dir}/cache"
    logging.info(f"Executing command: {cmd}")
    
    exit_code = os.system(cmd)
    
    if exit_code != 0:
        raise Exception(f"Meshroom failed with exit code {exit_code}")
    
    logging.info(f"Meshroom completed successfully. Results in {output_dir}")
    return output_dir

def _upload_model_to_minio(model_dir, **kwargs):
    """Upload the generated 3D model to MinIO."""
    logging.info(f"Uploading model from {model_dir} to MinIO")
    client = MinioClient(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY
    )
    
    # Upload model files
    for root, _, files in os.walk(model_dir):
        for file in files:
            if file.endswith(('.obj', '.mtl', '.png', '.jpg')):
                local_path = os.path.join(root, file)
                s3_path = os.path.relpath(local_path, model_dir)
                bucket_name = 'models'
                client.upload_file(local_path, bucket_name, s3_path)
                logging.info(f"Uploaded {local_path} to s3://{bucket_name}/{s3_path}")
    
    return model_dir

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
            'output_dir': f"{FRAMES_PATH}/{{{{ dag_run.id }}}}"
        }
    )
    
    # Process frames with Spark
    process_frames_task = PythonOperator(
        task_id='process_frames',
        python_callable=_process_frames,
        op_kwargs={
            'input_dir': f"{FRAMES_PATH}/{{{{ dag_run.id }}}}",
            'output_dir': f"{PROCESSED_FRAMES_PATH}/{{{{ dag_run.id }}}}"
        }
    )
    
    # Run Meshroom
    run_meshroom_task = PythonOperator(
        task_id='run_meshroom',
        python_callable=_run_meshroom,
        op_kwargs={
            'input_dir': f"{PROCESSED_FRAMES_PATH}/{{{{ dag_run.id }}}}",
            'output_dir': f"{MODELS_PATH}/{{{{ dag_run.id }}}}"
        },
        executor_config={"resources": gpu_resources}
    )
    
    # Upload model to MinIO
    upload_model_task = PythonOperator(
        task_id='upload_model',
        python_callable=_upload_model_to_minio,
        op_kwargs={
            'model_dir': f"{MODELS_PATH}/{{{{ dag_run.id }}}}"
        }
    )
    
    # Task dependencies
    watch_new_video >> validate_video_task >> extract_frames_task >> process_frames_task >> run_meshroom_task >> upload_model_task 