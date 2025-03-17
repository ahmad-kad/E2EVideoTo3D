"""
Real Reconstruction DAG for processing videos
This DAG processes input videos without any dummy data generation.
"""

import os
import glob
import logging
import subprocess
import shutil
from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from airflow.models import Variable

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("real_reconstruction")

# Configure paths
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
INPUT_PATH = os.environ.get('INPUT_PATH', os.path.join(PROJECT_PATH, 'input'))
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', os.path.join(PROJECT_PATH, 'output'))
VIDEO_PATH = os.environ.get('VIDEO_PATH', os.path.join(PROJECT_PATH, 'videos'))
COLMAP_PATH = os.environ.get('COLMAP_PATH', 'colmap')

# Quality settings
QUALITY_PRESET = os.environ.get('QUALITY_PRESET', 'medium')
if QUALITY_PRESET == 'low':
    EXTRACT_FPS = 1
    COLMAP_QUALITY_OPTS = '--ImageReader.single_camera 1 --SiftExtraction.max_image_size 1600'
elif QUALITY_PRESET == 'high':
    EXTRACT_FPS = 4
    COLMAP_QUALITY_OPTS = '--SiftExtraction.max_image_size 3200'
else:  # medium (default)
    EXTRACT_FPS = 2
    COLMAP_QUALITY_OPTS = '--SiftExtraction.max_image_size 2400'

# Ensure directories exist
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(INPUT_PATH, exist_ok=True)
os.makedirs(VIDEO_PATH, exist_ok=True)

# DAG functions
def extract_frames_from_video(video_filename=None, **kwargs):
    """Extract frames from the specified video"""
    if not video_filename:
        # Check for video in context or dag parameters
        ti = kwargs.get('ti')
        if ti:
            video_filename = ti.xcom_pull(key='video_filename')
        
        # If still no video, try to get from DAG run configuration
        if not video_filename:
            dag_run = kwargs.get('dag_run')
            if dag_run and dag_run.conf and 'video_filename' in dag_run.conf:
                video_filename = dag_run.conf['video_filename']
        
        # If still no video, list available videos and use the most recent
        if not video_filename:
            videos = glob.glob(os.path.join(VIDEO_PATH, "*.mp4"))
            videos.extend(glob.glob(os.path.join(VIDEO_PATH, "*.avi")))
            videos.extend(glob.glob(os.path.join(VIDEO_PATH, "*.mov")))
            
            if not videos:
                error_msg = f"No video files found in {VIDEO_PATH}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Sort by modification time, newest first
            videos.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            video_filename = os.path.basename(videos[0])
            logger.info(f"No video specified, using most recent: {video_filename}")
    
    # Validate extension
    if not video_filename.lower().endswith(('.mp4', '.avi', '.mov')):
        error_msg = f"Unsupported video format: {video_filename}. Must be mp4, avi, or mov."
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    video_file = os.path.join(VIDEO_PATH, video_filename)
    video_name = os.path.splitext(video_filename)[0]
    
    # Check if video exists
    if not os.path.exists(video_file):
        error_msg = f"Video file not found: {video_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Create unique output directory for frames
    import time
    timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
    frames_dir = os.path.join(INPUT_PATH, f"{video_name}_{timestamp}")
    os.makedirs(frames_dir, exist_ok=True)
    
    # Extract frames using ffmpeg
    cmd = [
        "ffmpeg", "-i", video_file,
        "-vf", f"fps={EXTRACT_FPS}",
        "-q:v", "1",
        f"{frames_dir}/frame_%04d.jpg"
    ]
    
    logger.info(f"Extracting frames from {video_file} to {frames_dir}")
    subprocess.run(cmd, check=True)
    
    # Count extracted frames
    frames = glob.glob(os.path.join(frames_dir, "*.jpg"))
    logger.info(f"Extracted {len(frames)} frames to {frames_dir}")
    
    # Store video name for subsequent tasks
    kwargs['ti'].xcom_push(key='video_name', value=video_name)
    
    return frames_dir

def run_colmap_feature_extraction(**kwargs):
    """Run COLMAP feature extraction on the frames"""
    ti = kwargs['ti']
    frames_dir = ti.xcom_pull(task_ids='extract_frames')
    video_name = ti.xcom_pull(key='video_name')
    
    # Create workspace directory for this specific video
    colmap_workspace = os.path.join(OUTPUT_PATH, f'colmap_workspace_{video_name}')
    os.makedirs(colmap_workspace, exist_ok=True)
    
    # Store workspace path for subsequent tasks
    ti.xcom_push(key='colmap_workspace', value=colmap_workspace)
    
    database_path = os.path.join(colmap_workspace, "database.db")
    
    # Build command
    cmd = [
        COLMAP_PATH, "feature_extractor",
        "--database_path", database_path,
        "--image_path", frames_dir
    ] + COLMAP_QUALITY_OPTS.split()
    
    logger.info(f"Running COLMAP feature extraction: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    return database_path

def run_colmap_feature_matching(**kwargs):
    """Run COLMAP feature matching"""
    ti = kwargs['ti']
    database_path = ti.xcom_pull(task_ids='run_feature_extraction')
    
    # Build command
    cmd = [
        COLMAP_PATH, "exhaustive_matcher",
        "--database_path", database_path
    ]
    
    logger.info(f"Running COLMAP feature matching: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    return database_path

def run_colmap_mapper(**kwargs):
    """Run COLMAP sparse reconstruction"""
    ti = kwargs['ti']
    database_path = ti.xcom_pull(task_ids='run_feature_matching')
    frames_dir = ti.xcom_pull(task_ids='extract_frames')
    colmap_workspace = ti.xcom_pull(key='colmap_workspace')
    
    sparse_dir = os.path.join(colmap_workspace, "sparse")
    os.makedirs(sparse_dir, exist_ok=True)
    
    # Build command
    cmd = [
        COLMAP_PATH, "mapper",
        "--database_path", database_path,
        "--image_path", frames_dir,
        "--output_path", sparse_dir
    ]
    
    logger.info(f"Running COLMAP mapper: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    return sparse_dir

def convert_to_ply(**kwargs):
    """Convert sparse reconstruction to PLY format"""
    ti = kwargs['ti']
    sparse_dir = ti.xcom_pull(task_ids='run_mapper')
    colmap_workspace = ti.xcom_pull(key='colmap_workspace')
    
    # Check for reconstruction output (typically in a numbered directory like 0, 1, etc.)
    reconstruction_dirs = glob.glob(os.path.join(sparse_dir, "*"))
    reconstruction_dirs = [d for d in reconstruction_dirs if os.path.isdir(d)]
    
    if not reconstruction_dirs:
        error_msg = f"No reconstruction directories found in {sparse_dir}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Use the first reconstruction (usually the best one)
    model_dir = reconstruction_dirs[0]
    ply_path = os.path.join(colmap_workspace, "sparse.ply")
    
    # Build command
    cmd = [
        COLMAP_PATH, "model_converter",
        "--input_path", model_dir,
        "--output_path", ply_path,
        "--output_type", "PLY"
    ]
    
    logger.info(f"Converting model to PLY: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    return ply_path

# Define DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'real_reconstruction_pipeline',
    default_args=default_args,
    description='Process videos for 3D reconstruction without dummy data',
    schedule_interval=None,
    catchup=False
)

# Define tasks
extract_frames = PythonOperator(
    task_id='extract_frames',
    python_callable=extract_frames_from_video,
    dag=dag
)

run_feature_extraction = PythonOperator(
    task_id='run_feature_extraction',
    python_callable=run_colmap_feature_extraction,
    dag=dag
)

run_feature_matching = PythonOperator(
    task_id='run_feature_matching',
    python_callable=run_colmap_feature_matching,
    dag=dag
)

run_mapper = PythonOperator(
    task_id='run_mapper',
    python_callable=run_colmap_mapper,
    dag=dag
)

convert_model = PythonOperator(
    task_id='convert_model',
    python_callable=convert_to_ply,
    dag=dag
)

# Define task dependencies
extract_frames >> run_feature_extraction >> run_feature_matching >> run_mapper >> convert_model 