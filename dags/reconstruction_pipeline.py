from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import timedelta

import os
import sys
import logging
import subprocess
import glob

# Configure paths
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
INPUT_PATH = os.path.join(PROJECT_PATH, 'input')
OUTPUT_PATH = os.path.join(PROJECT_PATH, 'output')
COLMAP_PATH = os.environ.get('COLMAP_PATH', 'colmap')  # Path to COLMAP executable

# Ensure output directory exists
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(INPUT_PATH, exist_ok=True)

# Function to check if GPU is available
def is_gpu_available():
    try:
        # Try to run nvidia-smi to check for GPU
        subprocess.check_output(['nvidia-smi'], stderr=subprocess.STDOUT)
        logging.info("NVIDIA GPU detected. Using GPU acceleration.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.info("No NVIDIA GPU detected or nvidia-smi not available. Using CPU mode.")
        return False

# Default arguments for the DAG
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
    'reconstruction_pipeline',
    default_args=default_args,
    description='3D reconstruction pipeline using COLMAP',
    schedule_interval=None,
    start_date=days_ago(1),
    tags=['3d', 'reconstruction', 'colmap'],
)

# Check for video files and extract frames if needed
def check_and_extract_video(**kwargs):
    video_dir = os.path.join(PROJECT_PATH, 'videos')
    frames_dir = INPUT_PATH
    
    # Check if there are already frames in the input directory
    existing_frames = glob.glob(os.path.join(frames_dir, '*.jpg')) + glob.glob(os.path.join(frames_dir, '*.png'))
    if existing_frames:
        logging.info(f"Found {len(existing_frames)} existing frames in {frames_dir}. Skipping video extraction.")
        return True
    
    # Look for video files
    video_files = glob.glob(os.path.join(video_dir, '*.mp4')) + glob.glob(os.path.join(video_dir, '*.mov'))
    if not video_files:
        logging.warning(f"No video files found in {video_dir}. Please add a video file or frames directly to the input directory.")
        return False
    
    # Use the first video file found
    video_file = video_files[0]
    logging.info(f"Found video file: {video_file}")
    
    # Extract frames using the extract_video.sh script
    extract_script = os.path.join(os.path.dirname(PROJECT_PATH), 'scripts', 'extract_video.sh')
    if os.path.exists(extract_script):
        cmd = f"bash {extract_script} {video_file}"
        logging.info(f"Running command: {cmd}")
        return_code = os.system(cmd)
        
        if return_code != 0:
            raise Exception("Video extraction failed")
        
        # Verify frames were extracted
        extracted_frames = glob.glob(os.path.join(frames_dir, '*.jpg')) + glob.glob(os.path.join(frames_dir, '*.png'))
        if not extracted_frames:
            raise Exception(f"No frames were extracted to {frames_dir}")
        
        logging.info(f"Successfully extracted {len(extracted_frames)} frames from {video_file}")
        return True
    else:
        logging.error(f"Extract video script not found at {extract_script}")
        return False

# Create working directories
def create_workspace(**kwargs):
    workspace_dir = os.path.join(OUTPUT_PATH, 'colmap_workspace')
    database_dir = os.path.join(workspace_dir, 'database')
    sparse_dir = os.path.join(workspace_dir, 'sparse')
    dense_dir = os.path.join(workspace_dir, 'dense')
    
    os.makedirs(workspace_dir, exist_ok=True)
    os.makedirs(database_dir, exist_ok=True)
    os.makedirs(sparse_dir, exist_ok=True)
    os.makedirs(os.path.join(sparse_dir, '0'), exist_ok=True)
    os.makedirs(dense_dir, exist_ok=True)
    
    return {
        'workspace_dir': workspace_dir,
        'database_dir': database_dir,
        'sparse_dir': sparse_dir,
        'dense_dir': dense_dir,
        'use_gpu': is_gpu_available()
    }

# COLMAP Feature Extraction
def feature_extraction(**kwargs):
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    use_gpu = workspace_info.get('use_gpu', False)
    
    database_path = os.path.join(workspace_info['database_dir'], 'database.db')
    
    # Check if input directory has images
    image_files = glob.glob(os.path.join(INPUT_PATH, '*.jpg')) + glob.glob(os.path.join(INPUT_PATH, '*.png'))
    if not image_files:
        raise Exception(f"No image files found in {INPUT_PATH}")
    
    logging.info(f"Found {len(image_files)} images for processing")
    
    # COLMAP feature extraction command
    cmd = f"{COLMAP_PATH} feature_extractor \
        --database_path {database_path} \
        --image_path {INPUT_PATH} \
        --ImageReader.camera_model SIMPLE_RADIAL \
        --SiftExtraction.use_gpu {'1' if use_gpu else '0'}"
    
    logging.info(f"Running command: {cmd}")
    return_code = os.system(cmd)
    
    if return_code != 0:
        raise Exception("Feature extraction failed")
    
    return database_path

# COLMAP Feature Matching
def feature_matching(**kwargs):
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    use_gpu = workspace_info.get('use_gpu', False)
    database_path = ti.xcom_pull(task_ids='feature_extraction')
    
    # COLMAP matching command
    cmd = f"{COLMAP_PATH} exhaustive_matcher \
        --database_path {database_path} \
        --SiftMatching.use_gpu {'1' if use_gpu else '0'}"
    
    logging.info(f"Running command: {cmd}")
    return_code = os.system(cmd)
    
    if return_code != 0:
        raise Exception("Feature matching failed")

# COLMAP Sparse Reconstruction
def sparse_reconstruction(**kwargs):
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    database_path = ti.xcom_pull(task_ids='feature_extraction')
    
    # COLMAP reconstruction command
    cmd = f"{COLMAP_PATH} mapper \
        --database_path {database_path} \
        --image_path {INPUT_PATH} \
        --output_path {workspace_info['sparse_dir']}"
    
    logging.info(f"Running command: {cmd}")
    return_code = os.system(cmd)
    
    if return_code != 0:
        raise Exception("Sparse reconstruction failed")

# COLMAP Dense Reconstruction (optional)
def dense_reconstruction(**kwargs):
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    use_gpu = workspace_info.get('use_gpu', False)
    
    # COLMAP image undistortion
    cmd1 = f"{COLMAP_PATH} image_undistorter \
        --image_path {INPUT_PATH} \
        --input_path {workspace_info['sparse_dir']}/0 \
        --output_path {workspace_info['dense_dir']} \
        --output_type COLMAP"
    
    logging.info(f"Running command: {cmd1}")
    return_code1 = os.system(cmd1)
    
    if return_code1 != 0:
        raise Exception("Image undistortion failed")
    
    # COLMAP dense reconstruction (patch matching and stereo fusion)
    gpu_index = "0" if use_gpu else "-1"
    cmd2 = f"{COLMAP_PATH} patch_match_stereo \
        --workspace_path {workspace_info['dense_dir']} \
        --workspace_format COLMAP \
        --PatchMatchStereo.gpu_index {gpu_index}"
    
    logging.info(f"Running command: {cmd2}")
    return_code2 = os.system(cmd2)
    
    if return_code2 != 0:
        raise Exception("Patch match stereo failed")
    
    # COLMAP stereo fusion
    cmd3 = f"{COLMAP_PATH} stereo_fusion \
        --workspace_path {workspace_info['dense_dir']} \
        --workspace_format COLMAP \
        --input_type geometric \
        --output_path {workspace_info['dense_dir']}/fused.ply"
    
    logging.info(f"Running command: {cmd3}")
    return_code3 = os.system(cmd3)
    
    if return_code3 != 0:
        raise Exception("Stereo fusion failed")
    
    # Copy the final model to a more accessible location
    final_model_path = os.path.join(OUTPUT_PATH, 'final_model.ply')
    cmd4 = f"cp {workspace_info['dense_dir']}/fused.ply {final_model_path}"
    os.system(cmd4)
    logging.info(f"Final 3D model saved to {final_model_path}")

# Define the tasks
check_video_task = PythonOperator(
    task_id='check_and_extract_video',
    python_callable=check_and_extract_video,
    dag=dag,
)

create_workspace_task = PythonOperator(
    task_id='create_workspace',
    python_callable=create_workspace,
    dag=dag,
)

feature_extraction_task = PythonOperator(
    task_id='feature_extraction',
    python_callable=feature_extraction,
    dag=dag,
)

feature_matching_task = PythonOperator(
    task_id='feature_matching',
    python_callable=feature_matching,
    dag=dag,
)

sparse_reconstruction_task = PythonOperator(
    task_id='sparse_reconstruction',
    python_callable=sparse_reconstruction,
    dag=dag,
)

dense_reconstruction_task = PythonOperator(
    task_id='dense_reconstruction',
    python_callable=dense_reconstruction,
    dag=dag,
)

# Define task dependencies
check_video_task >> create_workspace_task >> feature_extraction_task >> feature_matching_task >> sparse_reconstruction_task >> dense_reconstruction_task 