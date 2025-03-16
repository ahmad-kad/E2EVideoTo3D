import os
import glob
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.trigger_rule import TriggerRule
from airflow.utils.dates import days_ago

import sys
import logging
import subprocess

# Configure paths - Use environment variables or set defaults
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
INPUT_PATH = os.path.join(PROJECT_PATH, 'input')
OUTPUT_PATH = os.path.join(PROJECT_PATH, 'output')
VIDEO_PATH = os.path.join(PROJECT_PATH, 'videos')
COLMAP_PATH = os.environ.get('COLMAP_PATH', 'colmap')

# Ensure output directory exists
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(INPUT_PATH, exist_ok=True)
os.makedirs(VIDEO_PATH, exist_ok=True)

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
    'start_date': days_ago(1),
}

# Create the DAG
dag = DAG(
    'reconstruction_pipeline',
    default_args=default_args,
    description='3D reconstruction pipeline using COLMAP',
    schedule_interval=None,  # Only triggered manually
    catchup=False,
    tags=['3d', 'reconstruction', 'colmap'],
    params={
        'video_path': {
            'type': 'string',
            'default': '',
            'description': 'Optional: Directly specify the path to the video file if automatic detection fails'
        },
    },
)

# Define directories
VIDEO_DIR = '/opt/airflow/data/videos'
FRAMES_DIR = '/opt/airflow/data/input'
OUTPUT_DIR = '/opt/airflow/data/output'
COLMAP_WORKSPACE = f'{OUTPUT_DIR}/colmap_workspace'

# Check for video files and extract frames if needed
def check_and_extract_video(**kwargs):
    """
    This function checks for video files and extracts frames as needed.
    It has the following behavior:
    1. If there are already frames in the input directory, it skips extraction
    2. Otherwise, it looks for video files in the videos directory
    3. If a video is found, it extracts frames using ffmpeg
    """
    video_dir = VIDEO_PATH
    frames_dir = INPUT_PATH
    
    # Check if there are already frames in the input directory
    existing_frames = glob.glob(os.path.join(frames_dir, '*.jpg')) + glob.glob(os.path.join(frames_dir, '*.png'))
    if existing_frames:
        logging.info(f"Found {len(existing_frames)} existing frames in {frames_dir}. Skipping video extraction.")
        # Create a dummy file to satisfy the FileSensor
        dummy_file = os.path.join(VIDEO_PATH, '.video_processed')
        with open(dummy_file, 'w') as f:
            f.write('Frames already exist. This file is a placeholder for the FileSensor.')
        return dummy_file
    
    # Look for video files
    video_files = glob.glob(os.path.join(video_dir, '*.mp4')) + glob.glob(os.path.join(video_dir, '*.mov')) + glob.glob(os.path.join(video_dir, '*.avi'))
    if not video_files:
        logging.warning(f"No video files found in {video_dir}. Please add a video file or frames directly to the input directory.")
        raise FileNotFoundError(f"No video files found in {video_dir}")
    
    # Use the most recent video file
    video_file = max(video_files, key=os.path.getmtime)
    logging.info(f"Found video file: {video_file}")
    
    # Extract frames using ffmpeg
    try:
        # Try using local ffmpeg
        fps = 2  # Extract 2 frames per second by default
        logging.info(f"Extracting frames at {fps} fps from {video_file} to {frames_dir}...")
        
        if os.path.exists('/usr/bin/ffmpeg') or os.path.exists('/usr/local/bin/ffmpeg') or os.path.exists('/opt/homebrew/bin/ffmpeg'):
            # Use local ffmpeg
            cmd = f"ffmpeg -i {video_file} -vf \"fps={fps}\" -q:v 1 {os.path.join(frames_dir, 'frame_%04d.jpg')}"
            logging.info(f"Running command: {cmd}")
            result = subprocess.run(cmd, shell=True, check=True)
        else:
            # Try using docker
            cmd = f"docker run --rm -v {os.path.dirname(video_file)}:/tmp/video -v {frames_dir}:/tmp/frames jrottenberg/ffmpeg -i /tmp/video/{os.path.basename(video_file)} -vf \"fps={fps}\" -q:v 1 /tmp/frames/frame_%04d.jpg"
            logging.info(f"Running command: {cmd}")
            result = subprocess.run(cmd, shell=True, check=True)
        
        # Verify frames were extracted
        extracted_frames = glob.glob(os.path.join(frames_dir, '*.jpg')) + glob.glob(os.path.join(frames_dir, '*.png'))
        if not extracted_frames:
            raise Exception(f"No frames were extracted to {frames_dir}")
        
        logging.info(f"Successfully extracted {len(extracted_frames)} frames from {video_file}")
        
        # Save video info for later tasks
        with open(os.path.join(OUTPUT_PATH, 'video_info.txt'), 'w') as f:
            f.write(f"Video file: {video_file}\n")
            f.write(f"Frames extracted: {len(extracted_frames)}\n")
            f.write(f"FPS: {fps}\n")
        
        # Return the video file path for FileSensor
        return video_file
    except Exception as e:
        logging.error(f"Failed to extract frames: {str(e)}")
        raise e

# Function to create COLMAP workspace directories
def create_workspace(**kwargs):
    """
    Creates the COLMAP workspace directories needed for reconstruction
    """
    logging.info(f"Creating COLMAP workspace at {COLMAP_WORKSPACE}")
    
    # Create main workspace dir
    os.makedirs(COLMAP_WORKSPACE, exist_ok=True)
    
    # Create required subdirectories
    database_dir = os.path.join(COLMAP_WORKSPACE, 'database')
    sparse_dir = os.path.join(COLMAP_WORKSPACE, 'sparse')
    dense_dir = os.path.join(COLMAP_WORKSPACE, 'dense')
    
    os.makedirs(database_dir, exist_ok=True)
    os.makedirs(sparse_dir, exist_ok=True)
    os.makedirs(dense_dir, exist_ok=True)
    
    # Create database file path
    database_path = os.path.join(database_dir, 'database.db')
    
    logging.info(f"Created workspace directories at {COLMAP_WORKSPACE}")
    logging.info(f"  - Database: {database_dir}")
    logging.info(f"  - Sparse: {sparse_dir}")
    logging.info(f"  - Dense: {dense_dir}")
    
    return {
        'workspace_dir': COLMAP_WORKSPACE,
        'database_dir': database_dir,
        'database_path': database_path,
        'sparse_dir': sparse_dir,
        'dense_dir': dense_dir
    }

# Function to run COLMAP feature extraction
def feature_extraction(**kwargs):
    """
    Runs COLMAP feature extraction on the input images
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        logging.error("Failed to get workspace information from previous task")
        raise Exception("Workspace information not available")
    
    database_path = workspace_info.get('database_path')
    if not database_path:
        database_path = os.path.join(COLMAP_WORKSPACE, 'database', 'database.db')
    
    # Build the COLMAP command
    cmd = [
        COLMAP_PATH, 'feature_extractor',
        '--database_path', database_path,
        '--image_path', INPUT_PATH
    ]
    
    # Add GPU options if available
    if is_gpu_available():
        cmd.extend(['--SiftExtraction.use_gpu', '1'])
    
    logging.info(f"Running COLMAP feature extraction: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        logging.info("COLMAP feature extraction completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP feature extraction failed: {str(e)}")
        raise e

# Function to run COLMAP feature matching
def feature_matching(**kwargs):
    """
    Runs COLMAP feature matching on the extracted features
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        logging.error("Failed to get workspace information from previous task")
        raise Exception("Workspace information not available")
    
    database_path = workspace_info.get('database_path')
    if not database_path:
        database_path = os.path.join(COLMAP_WORKSPACE, 'database', 'database.db')
    
    # Build the COLMAP command
    cmd = [
        COLMAP_PATH, 'exhaustive_matcher',
        '--database_path', database_path
    ]
    
    # Add GPU options if available
    if is_gpu_available():
        cmd.extend(['--SiftMatching.use_gpu', '1'])
    
    logging.info(f"Running COLMAP feature matching: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        logging.info("COLMAP feature matching completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP feature matching failed: {str(e)}")
        raise e

# Function to run COLMAP sparse reconstruction
def sparse_reconstruction(**kwargs):
    """
    Runs COLMAP sparse reconstruction
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        logging.error("Failed to get workspace information from previous task")
        raise Exception("Workspace information not available")
    
    database_path = workspace_info.get('database_path')
    sparse_dir = workspace_info.get('sparse_dir')
    
    if not database_path or not sparse_dir:
        database_path = os.path.join(COLMAP_WORKSPACE, 'database', 'database.db')
        sparse_dir = os.path.join(COLMAP_WORKSPACE, 'sparse')
    
    # Build the COLMAP command
    cmd = [
        COLMAP_PATH, 'mapper',
        '--database_path', database_path,
        '--image_path', INPUT_PATH,
        '--output_path', sparse_dir
    ]
    
    logging.info(f"Running COLMAP sparse reconstruction: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        logging.info("COLMAP sparse reconstruction completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP sparse reconstruction failed: {str(e)}")
        raise e

# Function to run COLMAP dense reconstruction
def dense_reconstruction(**kwargs):
    """
    Runs COLMAP dense reconstruction
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        logging.error("Failed to get workspace information from previous task")
        raise Exception("Workspace information not available")
    
    sparse_dir = workspace_info.get('sparse_dir')
    dense_dir = workspace_info.get('dense_dir')
    
    if not sparse_dir or not dense_dir:
        sparse_dir = os.path.join(COLMAP_WORKSPACE, 'sparse')
        dense_dir = os.path.join(COLMAP_WORKSPACE, 'dense')
    
    # Model subdirectory of sparse (typically '0')
    sparse_model_dir = os.path.join(sparse_dir, '0')
    if not os.path.exists(sparse_model_dir):
        # Try to find any subdirectory
        subdirs = [d for d in os.listdir(sparse_dir) if os.path.isdir(os.path.join(sparse_dir, d))]
        if subdirs:
            sparse_model_dir = os.path.join(sparse_dir, subdirs[0])
        else:
            raise Exception(f"No sparse reconstruction model found in {sparse_dir}")
    
    # Build the COLMAP command for image undistortion
    undistort_cmd = [
        COLMAP_PATH, 'image_undistorter',
        '--image_path', INPUT_PATH,
        '--input_path', sparse_model_dir,
        '--output_path', dense_dir
    ]
    
    logging.info(f"Running COLMAP image undistortion: {' '.join(undistort_cmd)}")
    
    try:
        subprocess.run(undistort_cmd, check=True)
        logging.info("COLMAP image undistortion completed successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP image undistortion failed: {str(e)}")
        raise e
    
    # Build the COLMAP command for dense stereo
    stereo_cmd = [
        COLMAP_PATH, 'patch_match_stereo',
        '--workspace_path', dense_dir
    ]
    
    # Add GPU options if available
    if is_gpu_available():
        stereo_cmd.extend(['--PatchMatchStereo.gpu_index', '0'])
    
    logging.info(f"Running COLMAP stereo matching: {' '.join(stereo_cmd)}")
    
    try:
        subprocess.run(stereo_cmd, check=True)
        logging.info("COLMAP stereo matching completed successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP stereo matching failed: {str(e)}")
        raise e
    
    # Build the COLMAP command for stereo fusion
    fusion_cmd = [
        COLMAP_PATH, 'stereo_fusion',
        '--workspace_path', dense_dir,
        '--output_path', os.path.join(dense_dir, 'fused.ply')
    ]
    
    logging.info(f"Running COLMAP stereo fusion: {' '.join(fusion_cmd)}")
    
    try:
        subprocess.run(fusion_cmd, check=True)
        logging.info("COLMAP stereo fusion completed successfully")
        return os.path.join(dense_dir, 'fused.ply')
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP stereo fusion failed: {str(e)}")
        raise e

# Function to generate mesh from point cloud
def generate_mesh(**kwargs):
    """
    Generates a mesh from the dense point cloud using Poisson surface reconstruction
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        logging.error("Failed to get workspace information from previous task")
        raise Exception("Workspace information not available")
    
    dense_dir = workspace_info.get('dense_dir')
    if not dense_dir:
        dense_dir = os.path.join(COLMAP_WORKSPACE, 'dense')
    
    point_cloud_path = os.path.join(dense_dir, 'fused.ply')
    mesh_path = os.path.join(dense_dir, 'meshed.ply')
    
    if not os.path.exists(point_cloud_path):
        logging.error(f"Point cloud file not found at {point_cloud_path}")
        raise Exception("Point cloud file not found")
    
    # Build the COLMAP command for meshing
    cmd = [
        COLMAP_PATH, 'poisson_mesher',
        '--input_path', point_cloud_path,
        '--output_path', mesh_path
    ]
    
    logging.info(f"Running COLMAP Poisson meshing: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        logging.info(f"COLMAP Poisson meshing completed successfully. Mesh saved to {mesh_path}")
        return mesh_path
    except subprocess.CalledProcessError as e:
        logging.error(f"COLMAP Poisson meshing failed: {str(e)}")
        raise e

# Task 1: Find the latest video
find_video_task = PythonOperator(
    task_id='check_and_extract_video',
    python_callable=check_and_extract_video,
    provide_context=True,
    dag=dag,
)

# Task 2: Check if video exists
check_video_task = FileSensor(
    task_id='check_video_exists',
    filepath="{{ ti.xcom_pull(task_ids='check_and_extract_video') }}",
    poke_interval=30,  # Check every 30 seconds
    timeout=60 * 10,   # Timeout after 10 minutes
    mode='poke',
    soft_fail=True,  # Continue if timeout occurs
    dag=dag,
)

# Task 3: Extract frames from video
extract_frames_task = BashOperator(
    task_id='extract_frames',
    bash_command="""
    VIDEO_PATH="{{ ti.xcom_pull(task_ids='check_and_extract_video') }}"
    
    # Check if VIDEO_PATH is a real video file (not a dummy placeholder)
    if [[ "$VIDEO_PATH" == *".video_processed" ]]; then
        echo "Frames already exist, skipping extraction"
        FRAMES_DIR="{{ params.frames_dir }}"
        echo "$FRAMES_DIR" > /tmp/frames_path.txt
        exit 0
    fi
    
    FILENAME=$(basename "$VIDEO_PATH")
    
    # Create frames directory with video name
    FRAMES_SUBDIR="{{ params.frames_dir }}/${FILENAME%.*}"
    mkdir -p "$FRAMES_SUBDIR"
    
    # Use FFmpeg to extract frames (1 frame per second)
    ffmpeg -i "$VIDEO_PATH" -vf "fps=1" "$FRAMES_SUBDIR/frame_%04d.jpg"
    echo "Frames extracted to $FRAMES_SUBDIR"
    
    # Store the frames directory path for later tasks
    echo "$FRAMES_SUBDIR" > /tmp/frames_path.txt
    """,
    params={'frames_dir': FRAMES_DIR},
    dag=dag,
)

# Task 4: Check for extracted frames
check_frames_task = BashOperator(
    task_id='check_frames_exist',
    bash_command="""
    # If frames_path.txt doesn't exist yet, it means we're using existing frames in input directory
    if [ ! -f /tmp/frames_path.txt ]; then
        echo "Using existing frames in input directory"
        FRAMES_DIR="{{ params.frames_dir }}"
        echo "$FRAMES_DIR" > /tmp/frames_path.txt
    else
        FRAMES_DIR=$(cat /tmp/frames_path.txt)
    fi
    
    # Count frames, including subdirectories
    FRAME_COUNT=$(find "$FRAMES_DIR" -type f -name "*.jpg" -o -name "*.png" | wc -l)
    
    if [ "$FRAME_COUNT" -eq 0 ]; then
        echo "No frames were found. Exiting."
        exit 1
    fi
    
    echo "Found $FRAME_COUNT frames in $FRAMES_DIR"
    """,
    params={'frames_dir': FRAMES_DIR},
    dag=dag,
)

# Task 5: Create COLMAP workspace directories
create_workspace_task = PythonOperator(
    task_id='create_workspace',
    python_callable=create_workspace,
    dag=dag,
)

# Task 6: Run COLMAP feature extraction
feature_extraction_task = PythonOperator(
    task_id='feature_extraction',
    python_callable=feature_extraction,
    dag=dag,
)

# Task 7: Run COLMAP feature matching
feature_matching_task = PythonOperator(
    task_id='feature_matching',
    python_callable=feature_matching,
    dag=dag,
)

# Task 8: Run COLMAP sparse reconstruction
sparse_reconstruction_task = PythonOperator(
    task_id='sparse_reconstruction',
    python_callable=sparse_reconstruction,
    dag=dag,
)

# Task 9: Run COLMAP dense reconstruction
dense_reconstruction_task = PythonOperator(
    task_id='dense_reconstruction',
    python_callable=dense_reconstruction,
    dag=dag,
)

# Task 10: Generate mesh from point cloud
meshing_task = PythonOperator(
    task_id='generate_mesh',
    python_callable=generate_mesh,
    dag=dag,
)

# Task 11: Copy final outputs to output directory
copy_outputs_task = BashOperator(
    task_id='copy_outputs',
    bash_command=f"""
    # Copy point cloud
    cp {COLMAP_WORKSPACE}/dense/fused.ply {OUTPUT_DIR}/point_cloud.ply
    
    # Copy mesh
    cp {COLMAP_WORKSPACE}/dense/meshed.ply {OUTPUT_DIR}/mesh.ply
    
    # Get video name for naming the outputs
    VIDEO_PATH=$(cat /tmp/frames_path.txt)
    VIDEO_NAME=$(basename "$VIDEO_PATH")
    
    # Make model-specific output directory
    MODEL_DIR="{OUTPUT_DIR}/models/$VIDEO_NAME"
    mkdir -p "$MODEL_DIR"
    
    # Copy to model-specific directory
    cp {COLMAP_WORKSPACE}/dense/fused.ply "$MODEL_DIR/point_cloud.ply"
    cp {COLMAP_WORKSPACE}/dense/meshed.ply "$MODEL_DIR/mesh.ply"
    
    echo "Reconstruction complete. Output files:"
    echo " - Point cloud: {OUTPUT_DIR}/point_cloud.ply"
    echo " - Mesh: {OUTPUT_DIR}/mesh.ply"
    echo " - Model directory: $MODEL_DIR"
    """,
    dag=dag,
)

# Task 12: Optional - Upload to MinIO
upload_to_minio_task = BashOperator(
    task_id='upload_to_minio',
    bash_command="""
    # Get video name
    VIDEO_PATH=$(cat /tmp/frames_path.txt)
    VIDEO_NAME=$(basename "$VIDEO_PATH")
    
    # Check if AWS CLI is available
    if command -v aws &> /dev/null; then
        # Configure AWS CLI for MinIO
        export AWS_ACCESS_KEY_ID=minioadmin
        export AWS_SECRET_ACCESS_KEY=minioadmin
        export AWS_DEFAULT_REGION=us-east-1
        
        # Upload to MinIO
        aws --endpoint-url http://minio:9000 s3 cp {{ params.output_dir }}/point_cloud.ply s3://models/${VIDEO_NAME}/point_cloud.ply
        aws --endpoint-url http://minio:9000 s3 cp {{ params.output_dir }}/mesh.ply s3://models/${VIDEO_NAME}/mesh.ply
        
        echo "Uploaded results to MinIO bucket 'models/${VIDEO_NAME}'"
    else
        echo "AWS CLI not available, skipping upload to MinIO"
    fi
    """,
    params={
        'output_dir': OUTPUT_DIR,
    },
    dag=dag,
)

# Set up the task dependencies
find_video_task >> check_video_task >> extract_frames_task >> check_frames_task
check_frames_task >> create_workspace_task >> feature_extraction_task >> feature_matching_task
feature_matching_task >> sparse_reconstruction_task >> dense_reconstruction_task
dense_reconstruction_task >> meshing_task >> copy_outputs_task >> upload_to_minio_task 