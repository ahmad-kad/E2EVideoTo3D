import os
import glob
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.trigger_rule import TriggerRule

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2023, 1, 1),
}

# Create the DAG
dag = DAG(
    'video_to_3d_reconstruction',
    default_args=default_args,
    description='End-to-end pipeline from video to 3D reconstruction',
    schedule_interval=None,  # Only triggered manually
    catchup=False,
    tags=['reconstruction', 'colmap', 'video'],
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

# Define Python function to find the latest video
def find_latest_video(**kwargs):
    # Check if a video path was provided directly in the DAG run configuration
    dag_run = kwargs.get('dag_run')
    if dag_run and dag_run.conf and 'video_path' in dag_run.conf and dag_run.conf['video_path']:
        manual_path = dag_run.conf['video_path']
        if os.path.exists(manual_path):
            print(f"Using manually specified video path: {manual_path}")
            return manual_path
        else:
            print(f"WARNING: Manually specified path does not exist: {manual_path}")
    
    # Primary location
    video_files = glob.glob(f'{VIDEO_DIR}/*.mp4') + glob.glob(f'{VIDEO_DIR}/*.mov') + glob.glob(f'{VIDEO_DIR}/*.avi')
    
    # Add debug info
    print(f"Looking for videos in: {VIDEO_DIR}")
    print(f"Files found: {video_files}")
    
    # Try alternative locations if no files found
    if not video_files:
        alternative_dirs = [
            '/opt/airflow/data/videos',
            '/data/videos',
            '/usr/local/airflow/data/videos',
            './data/videos'
        ]
        
        for alt_dir in alternative_dirs:
            print(f"Trying alternative directory: {alt_dir}")
            alt_files = glob.glob(f'{alt_dir}/*.mp4') + glob.glob(f'{alt_dir}/*.mov') + glob.glob(f'{alt_dir}/*.avi')
            
            if alt_files:
                print(f"Found files in alternative directory: {alt_files}")
                video_files = alt_files
                break
    
    # If still no files, try recursive search
    if not video_files:
        print("Trying recursive search in parent directories...")
        for i in range(3):  # Look up to 3 levels up
            search_dir = '/'.join(VIDEO_DIR.split('/')[:-i-1]) if i > 0 else VIDEO_DIR
            if not search_dir:
                search_dir = '/'
            print(f"Searching in: {search_dir}")
            
            # Use find command for recursive search
            import subprocess
            try:
                result = subprocess.run(
                    ['find', search_dir, '-type', 'f', '-name', '*.mp4', '-o', '-name', '*.mov', '-o', '-name', '*.avi'],
                    capture_output=True, text=True, timeout=30
                )
                if result.stdout:
                    recursive_files = result.stdout.strip().split('\n')
                    print(f"Found files recursively: {recursive_files}")
                    if recursive_files and recursive_files[0]:  # Check if list is not empty
                        video_files = recursive_files
                        break
            except Exception as e:
                print(f"Error during recursive search: {e}")
    
    # If still no files found, check if the directory even exists
    if not video_files:
        if os.path.exists(VIDEO_DIR):
            print(f"Directory {VIDEO_DIR} exists but contains no video files")
            # List all files in the directory
            print(f"All files in directory: {os.listdir(VIDEO_DIR)}")
        else:
            print(f"Directory {VIDEO_DIR} does not exist!")
            # Check parent directory
            parent_dir = os.path.dirname(VIDEO_DIR)
            if os.path.exists(parent_dir):
                print(f"Parent directory {parent_dir} exists. Contents: {os.listdir(parent_dir)}")
        
        raise FileNotFoundError(f"No video files found in {VIDEO_DIR} or alternative locations")
    
    # Sort by modification time, newest first
    latest_video = max(video_files, key=os.path.getmtime)
    print(f"Latest video file: {latest_video}")
    return latest_video

# Task 1: Find the latest video
find_video_task = PythonOperator(
    task_id='find_latest_video',
    python_callable=find_latest_video,
    provide_context=True,
    dag=dag,
)

# Task 2: Check if video exists
check_video_task = FileSensor(
    task_id='check_video_exists',
    filepath="{{ ti.xcom_pull(task_ids='find_latest_video') }}",
    poke_interval=30,  # Check every 30 seconds
    timeout=60 * 10,   # Timeout after 10 minutes
    mode='poke',
    dag=dag,
)

# Task 3: Extract frames from video
extract_frames_task = BashOperator(
    task_id='extract_frames',
    bash_command="""
    VIDEO_PATH="{{ ti.xcom_pull(task_ids='find_latest_video') }}"
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
    FRAMES_DIR=$(cat /tmp/frames_path.txt)
    FRAME_COUNT=$(ls -1 "$FRAMES_DIR"/*.jpg 2>/dev/null | wc -l)
    
    if [ "$FRAME_COUNT" -eq 0 ]; then
        echo "No frames were extracted. Exiting."
        exit 1
    fi
    
    echo "Found $FRAME_COUNT frames in $FRAMES_DIR"
    """,
    dag=dag,
)

# Task 5: Create COLMAP workspace directories
create_workspace_task = BashOperator(
    task_id='create_colmap_workspace',
    bash_command=f"""
    mkdir -p {COLMAP_WORKSPACE}/sparse
    mkdir -p {COLMAP_WORKSPACE}/dense
    mkdir -p {OUTPUT_DIR}/models
    echo "Created COLMAP workspace at {COLMAP_WORKSPACE}"
    """,
    dag=dag,
)

# Task 6: Run COLMAP feature extraction
feature_extraction_task = BashOperator(
    task_id='colmap_feature_extraction',
    bash_command="""
    FRAMES_DIR=$(cat /tmp/frames_path.txt)
    colmap feature_extractor \
        --database_path {{ params.workspace }}/database.db \
        --image_path "$FRAMES_DIR" \
        --ImageReader.camera_model SIMPLE_RADIAL \
        --ImageReader.single_camera 1 \
        --SiftExtraction.use_gpu {{ params.use_gpu }}
    """,
    params={
        'workspace': COLMAP_WORKSPACE,
        'use_gpu': 1,  # Set to 0 for CPU-only mode
    },
    dag=dag,
)

# Task 7: Run COLMAP feature matching
feature_matching_task = BashOperator(
    task_id='colmap_feature_matching',
    bash_command="""
    colmap exhaustive_matcher \
        --database_path {{ params.workspace }}/database.db \
        --SiftMatching.use_gpu {{ params.use_gpu }}
    """,
    params={
        'workspace': COLMAP_WORKSPACE,
        'use_gpu': 1,  # Set to 0 for CPU-only mode
    },
    dag=dag,
)

# Task 8: Run COLMAP sparse reconstruction
sparse_reconstruction_task = BashOperator(
    task_id='colmap_sparse_reconstruction',
    bash_command="""
    FRAMES_DIR=$(cat /tmp/frames_path.txt)
    colmap mapper \
        --database_path {{ params.workspace }}/database.db \
        --image_path "$FRAMES_DIR" \
        --output_path {{ params.workspace }}/sparse
    """,
    params={
        'workspace': COLMAP_WORKSPACE,
    },
    dag=dag,
)

# Task 9: Run COLMAP dense reconstruction
dense_reconstruction_task = BashOperator(
    task_id='colmap_dense_reconstruction',
    bash_command="""
    FRAMES_DIR=$(cat /tmp/frames_path.txt)
    
    # Convert sparse reconstruction to dense format
    colmap image_undistorter \
        --image_path "$FRAMES_DIR" \
        --input_path {{ params.workspace }}/sparse/0 \
        --output_path {{ params.workspace }}/dense \
        --output_type COLMAP
        
    # Perform dense stereo
    colmap patch_match_stereo \
        --workspace_path {{ params.workspace }}/dense \
        --workspace_format COLMAP \
        --PatchMatchStereo.geom_consistency true
        
    # Perform stereo fusion
    colmap stereo_fusion \
        --workspace_path {{ params.workspace }}/dense \
        --workspace_format COLMAP \
        --input_type geometric \
        --output_path {{ params.workspace }}/dense/fused.ply
    """,
    params={
        'workspace': COLMAP_WORKSPACE,
    },
    dag=dag,
)

# Task 10: Generate mesh from point cloud
meshing_task = BashOperator(
    task_id='generate_mesh',
    bash_command="""
    # Meshing with Poisson surface reconstruction
    colmap poisson_mesher \
        --input_path {{ params.workspace }}/dense/fused.ply \
        --output_path {{ params.workspace }}/dense/meshed.ply
    """,
    params={
        'workspace': COLMAP_WORKSPACE,
    },
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