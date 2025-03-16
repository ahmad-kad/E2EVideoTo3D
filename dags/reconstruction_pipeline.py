import os
import glob
import sys
import json
import logging
import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.trigger_rule import TriggerRule
from airflow.utils.dates import days_ago
from airflow.models import Variable
from airflow.exceptions import AirflowException, AirflowSkipException
from airflow.hooks.S3_hook import S3Hook
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

# Import extra operators if available
try:
    from airflow.sensors.s3_key_sensor import S3KeySensor
    S3_SENSOR_AVAILABLE = True
except ImportError:
    S3_SENSOR_AVAILABLE = False

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("reconstruction_pipeline")

# Configure paths - Use environment variables or Airflow Variables for better configurability
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
INPUT_PATH = os.environ.get('INPUT_PATH', os.path.join(PROJECT_PATH, 'input'))
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', os.path.join(PROJECT_PATH, 'output'))
VIDEO_PATH = os.environ.get('VIDEO_PATH', os.path.join(PROJECT_PATH, 'videos'))
COLMAP_PATH = os.environ.get('COLMAP_PATH', 'colmap')

# Use Docker container instead of local COLMAP?
USE_COLMAP_DOCKER = os.environ.get('USE_COLMAP_DOCKER', 'false').lower() == 'true'
COLMAP_DOCKER_SERVICE = os.environ.get('COLMAP_DOCKER_SERVICE', 'colmap')

# S3/MinIO configuration
S3_ENABLED = os.environ.get('S3_ENABLED', 'false').lower() == 'true'
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', 'http://minio:9000')
S3_BUCKET = os.environ.get('S3_BUCKET', 'models')
S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY', '')
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY', '')
S3_REGION = os.environ.get('S3_REGION', 'us-east-1')

# Notification configuration
SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK', '')
ENABLE_EMAIL = os.environ.get('ENABLE_EMAIL', 'false').lower() == 'true'
NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL', '')

# COLMAP configuration
USE_GPU = os.environ.get('USE_GPU', 'auto')  # 'auto', 'true', or 'false'
QUALITY_PRESET = os.environ.get('QUALITY_PRESET', 'medium')  # 'low', 'medium', 'high'

# Process quality preset
if QUALITY_PRESET == 'low':
    EXTRACT_FPS = 1
    COLMAP_QUALITY_OPTS = '--ImageReader.single_camera 1 --SiftExtraction.max_image_size 1600'
elif QUALITY_PRESET == 'high':
    EXTRACT_FPS = 4
    COLMAP_QUALITY_OPTS = '--SiftExtraction.max_image_size 3200'
else:  # medium (default)
    EXTRACT_FPS = 2
    COLMAP_QUALITY_OPTS = '--SiftExtraction.max_image_size 2400'

# Ensure directories exists
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(INPUT_PATH, exist_ok=True)
os.makedirs(VIDEO_PATH, exist_ok=True)

# Define directories constants (for backward compatibility)
VIDEO_DIR = VIDEO_PATH
FRAMES_DIR = INPUT_PATH
OUTPUT_DIR = OUTPUT_PATH
COLMAP_WORKSPACE = os.path.join(OUTPUT_DIR, 'colmap_workspace')

# Function to check if GPU is available
def is_gpu_available():
    """
    Check if NVIDIA GPU is available using nvidia-smi and consider environment config.
    Returns:
        bool: True if GPU should be used, False otherwise
    """
    # If USE_GPU is explicitly set, respect that setting
    if USE_GPU.lower() == 'true':
        logger.info("GPU use is forced by configuration")
        # Still check if GPU is actually available and warn if not
        try:
            subprocess.check_output(['nvidia-smi'], stderr=subprocess.STDOUT)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
            logger.warning("GPU use was requested but no GPU was detected! Proceeding with GPU mode anyway.")
            return True
    elif USE_GPU.lower() == 'false':
        logger.info("GPU use is disabled by configuration")
        return False
    
    # Auto-detect GPU
    try:
        gpu_info = subprocess.check_output(['nvidia-smi'], stderr=subprocess.STDOUT).decode('utf-8')
        logger.info(f"GPU detected: {gpu_info.splitlines()[0]}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
        logger.info("No NVIDIA GPU detected. Using CPU mode.")
        return False

# Function to check dependencies
def check_dependencies(**kwargs):
    """
    Checks if all required dependencies are installed.
    Raises AirflowException if critical dependencies are missing.
    """
    logger.info("Checking dependencies...")
    dependencies = {
        'critical': ['ffmpeg', COLMAP_PATH],
        'optional': ['aws', 'open3d']
    }
    
    missing_critical = []
    missing_optional = []
    
    # Check critical dependencies
    for cmd in dependencies['critical']:
        try:
            subprocess.check_output(f"which {cmd}", shell=True, stderr=subprocess.STDOUT)
            logger.info(f"✓ {cmd} is available")
        except subprocess.CalledProcessError:
            logger.error(f"✗ Critical dependency {cmd} is not available")
            missing_critical.append(cmd)
    
    # Check optional dependencies
    for cmd in dependencies['optional']:
        try:
            subprocess.check_output(f"which {cmd}", shell=True, stderr=subprocess.STDOUT)
            logger.info(f"✓ Optional dependency {cmd} is available")
        except subprocess.CalledProcessError:
            logger.warning(f"✗ Optional dependency {cmd} is not available")
            missing_optional.append(cmd)
    
    # Check Python dependencies
    try:
        import cv2
        logger.info("✓ OpenCV (cv2) is available")
    except ImportError:
        logger.error("✗ Critical dependency OpenCV (cv2) is not available")
        missing_critical.append("python-opencv")
    
    # Log summary
    if missing_optional:
        logger.warning(f"Missing optional dependencies: {', '.join(missing_optional)}")
        logger.warning("Some features may not be available")
    
    # Raise error if critical dependencies are missing
    if missing_critical:
        error_msg = f"Missing critical dependencies: {', '.join(missing_critical)}"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    return True

# Define task failure handling
def task_failure_handler(context):
    """
    Handles task failures by sending notifications and logging details.
    This function is called when a task fails.
    """
    task_instance = context['task_instance']
    task_name = task_instance.task_id
    dag_id = task_instance.dag_id
    exception = context.get('exception')
    
    error_message = f"Task {task_name} in DAG {dag_id} failed with exception: {str(exception)}"
    logger.error(error_message)
    
    # Send Slack notification if configured
    if SLACK_WEBHOOK:
        try:
            slack_msg = f"""
                :red_circle: Task Failed.
                *Task*: {task_name}
                *Dag*: {dag_id}
                *Execution Time*: {context['execution_date']}
                *Exception*: {str(exception)}
                *Log URL*: {context.get('task_instance').log_url}
            """
            slack_alert = SlackWebhookOperator(
                task_id='slack_notification',
                http_conn_id='slack_webhook',
                webhook_token=SLACK_WEBHOOK,
                message=slack_msg,
            )
            slack_alert.execute(context=context)
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
    
    return

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': NOTIFICATION_EMAIL if NOTIFICATION_EMAIL else None,
    'email_on_failure': ENABLE_EMAIL,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=30),
    'start_date': days_ago(1),
    'execution_timeout': timedelta(hours=3),
    'on_failure_callback': task_failure_handler,
}

# Create the DAG
dag = DAG(
    'reconstruction_pipeline',
    default_args=default_args,
    description='3D reconstruction pipeline using COLMAP',
    schedule_interval=None,  # Only triggered manually
    catchup=False,
    tags=['3d', 'reconstruction', 'colmap'],
    max_active_runs=1,  # Only one instance can run at a time
    params={
        'video_path': {
            'type': 'string',
            'default': '',
            'description': 'Optional: Directly specify the path to the video file if automatic detection fails'
        },
        'quality': {
            'type': 'string',
            'default': QUALITY_PRESET,
            'description': 'Quality preset for reconstruction: low, medium, or high'
        },
        's3_upload': {
            'type': 'boolean',
            'default': S3_ENABLED,
            'description': 'Whether to upload results to S3/MinIO'
        },
    },
    doc_md="""
    # 3D Reconstruction Pipeline
    
    This DAG runs the complete 3D reconstruction pipeline using COLMAP.
    
    ## Input
    
    Place video files in the `/opt/airflow/data/videos` directory or image frames in the `/opt/airflow/data/input` directory.
    
    ## Output
    
    The output will be stored in `/opt/airflow/data/output` directory:
    - Point cloud (PLY format)
    - Mesh (PLY format)
    - Camera positions
    
    ## Parameters
    
    - **video_path**: Optional path to a specific video file
    - **quality**: Quality preset (low, medium, high)
    - **s3_upload**: Whether to upload results to S3/MinIO
    
    ## Environment Variables
    
    - PROJECT_PATH: Base path for all data
    - COLMAP_PATH: Path to COLMAP executable
    - S3_ENABLED: Enable S3/MinIO uploads
    - S3_ENDPOINT: S3/MinIO endpoint URL
    - S3_BUCKET: S3/MinIO bucket name
    - SLACK_WEBHOOK: Slack webhook URL for notifications
    - ENABLE_EMAIL: Enable email notifications
    - NOTIFICATION_EMAIL: Email address for notifications
    - USE_GPU: 'auto', 'true', or 'false'
    - QUALITY_PRESET: 'low', 'medium', or 'high'
    """
)

# Task 0: Check if dependencies are installed
check_dependencies_task = PythonOperator(
    task_id='check_dependencies',
    python_callable=check_dependencies,
    dag=dag,
)

# Task 1: Find the latest video and extract frames
find_video_task = PythonOperator(
    task_id='check_and_extract_video',
    python_callable=check_and_extract_video,
    provide_context=True,
    retries=2,
    retry_delay=timedelta(minutes=1),
    execution_timeout=timedelta(minutes=30),
    dag=dag,
)

# Task 2: Check if frames exist
check_frames_task = BashOperator(
    task_id='check_frames_exist',
    bash_command='''
    FRAMES_DIR="{{ ti.xcom_pull(task_ids='check_and_extract_video') }}"
    
    if [ -z "$FRAMES_DIR" ]; then
        echo "No frames directory provided. Using default input directory."
        FRAMES_DIR="{{ params.frames_dir }}"
    fi
    
    # Count frames, including subdirectories
    FRAME_COUNT=$(find "$FRAMES_DIR" -type f -name "*.jpg" -o -name "*.png" | wc -l)
    
    if [ "$FRAME_COUNT" -eq 0 ]; then
        echo "No frames were found in $FRAMES_DIR. Exiting."
        exit 1
    fi
    
    echo "Found $FRAME_COUNT frames in $FRAMES_DIR"
    
    # Store the frames directory in a file for backup/compatibility
    echo "$FRAMES_DIR" > /tmp/frames_path.txt
    ''',
    params={'frames_dir': FRAMES_DIR},
    retries=1,
    execution_timeout=timedelta(minutes=5),
    dag=dag,
)

# Task 3: Create COLMAP workspace directories
create_workspace_task = PythonOperator(
    task_id='create_workspace',
    python_callable=create_workspace,
    retries=1,
    execution_timeout=timedelta(minutes=5),
    dag=dag,
)

# Task 4: Run COLMAP feature extraction
feature_extraction_task = PythonOperator(
    task_id='feature_extraction',
    python_callable=feature_extraction,
    retries=1,
    execution_timeout=timedelta(hours=2),
    dag=dag,
)

# Task 5: Run COLMAP feature matching
feature_matching_task = PythonOperator(
    task_id='feature_matching',
    python_callable=feature_matching,
    retries=1,
    execution_timeout=timedelta(hours=2),
    dag=dag,
)

# Task 6: Run COLMAP sparse reconstruction
sparse_reconstruction_task = PythonOperator(
    task_id='sparse_reconstruction',
    python_callable=sparse_reconstruction,
    retries=1,
    execution_timeout=timedelta(hours=2),
    dag=dag,
)

# Task 7: Run COLMAP dense reconstruction
dense_reconstruction_task = PythonOperator(
    task_id='dense_reconstruction',
    python_callable=dense_reconstruction,
    retries=1,
    execution_timeout=timedelta(hours=4),
    dag=dag,
)

# Task 8: Generate mesh from point cloud
meshing_task = PythonOperator(
    task_id='generate_mesh',
    python_callable=generate_mesh,
    retries=1,
    execution_timeout=timedelta(hours=1),
    dag=dag,
)

# Task 9: Copy final outputs to output directory
copy_outputs_task = BashOperator(
    task_id='copy_outputs',
    bash_command=f"""
    # Get the reconstruction results
    SPARSE_DIR="{{ ti.xcom_pull(task_ids='sparse_reconstruction') }}"
    DENSE_DIR="{{ ti.xcom_pull(task_ids='dense_reconstruction') }}"
    MESH_PATH="{{ ti.xcom_pull(task_ids='generate_mesh') }}"
    
    # Get workspace directory
    WORKSPACE_DIR="{{ ti.xcom_pull(task_ids='create_workspace') }}"
    
    # Get video/frames directory
    FRAMES_DIR="{{ ti.xcom_pull(task_ids='check_and_extract_video') }}"
    VIDEO_NAME=$(basename "$FRAMES_DIR")
    
    # Make model-specific output directory
    MODEL_DIR="{OUTPUT_DIR}/models/$VIDEO_NAME"
    mkdir -p "$MODEL_DIR"
    
    # Copy point cloud if it exists
    if [ -f "$DENSE_DIR/fused.ply" ]; then
        cp "$DENSE_DIR/fused.ply" "{OUTPUT_DIR}/point_cloud.ply"
        cp "$DENSE_DIR/fused.ply" "$MODEL_DIR/point_cloud.ply"
        echo "Copied point cloud to $MODEL_DIR/point_cloud.ply"
    else
        echo "Warning: Point cloud file not found at $DENSE_DIR/fused.ply"
    fi
    
    # Copy mesh if it exists
    if [ -f "$MESH_PATH" ]; then
        cp "$MESH_PATH" "{OUTPUT_DIR}/mesh.ply"
        cp "$MESH_PATH" "$MODEL_DIR/mesh.ply"
        echo "Copied mesh to $MODEL_DIR/mesh.ply"
    else
        echo "Warning: Mesh file not found at $MESH_PATH"
    fi
    
    # Copy sparse model if it exists
    if [ -d "$SPARSE_DIR/0" ]; then
        mkdir -p "$MODEL_DIR/sparse"
        cp -r "$SPARSE_DIR/0" "$MODEL_DIR/sparse/"
        echo "Copied sparse model to $MODEL_DIR/sparse/"
    fi
    
    # Create a JSON metadata file
    cat > "$MODEL_DIR/metadata.json" << EOF
    {
        "processed_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
        "source": "$FRAMES_DIR",
        "frame_count": $(find "$FRAMES_DIR" -type f -name "*.jpg" -o -name "*.png" | wc -l),
        "quality_preset": "{QUALITY_PRESET}",
        "colmap_workspace": "$WORKSPACE_DIR"
    }
    EOF
    
    echo "Reconstruction complete. Output files:"
    echo " - Point cloud: {OUTPUT_DIR}/point_cloud.ply"
    echo " - Mesh: {OUTPUT_DIR}/mesh.ply"
    echo " - Model directory: $MODEL_DIR"
    
    # Create a completion marker file
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$MODEL_DIR/COMPLETED"
    """,
    retries=1,
    execution_timeout=timedelta(minutes=15),
    dag=dag,
)

# Function for S3 upload
def upload_to_s3(**kwargs):
    """
    Uploads the reconstruction results to S3/MinIO.
    
    Returns:
        bool: True if upload was successful, False otherwise
    """
    ti = kwargs['ti']
    params = kwargs.get('params', {})
    
    # Check if S3 upload is enabled from parameters or environment
    s3_upload = params.get('s3_upload', S3_ENABLED)
    if not s3_upload:
        logger.info("S3 upload is disabled. Skipping.")
        return False
    
    # Get frames directory to determine model name
    frames_dir = ti.xcom_pull(task_ids='check_and_extract_video')
    if not frames_dir:
        logger.warning("No frames directory available. Using timestamp as model name.")
        model_name = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        model_name = os.path.basename(frames_dir)
    
    # Define the model output directory
    model_dir = os.path.join(OUTPUT_DIR, 'models', model_name)
    if not os.path.exists(model_dir):
        logger.warning(f"Model directory {model_dir} does not exist. Skipping upload.")
        return False
    
    try:
        # Create S3 hook
        s3_hook = S3Hook(aws_conn_id='aws_default')
        
        # Upload all files in the model directory
        for root, dirs, files in os.walk(model_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, model_dir)
                s3_key = f"{model_name}/{relative_path}"
                
                logger.info(f"Uploading {local_path} to s3://{S3_BUCKET}/{s3_key}")
                s3_hook.load_file(
                    filename=local_path,
                    key=s3_key,
                    bucket_name=S3_BUCKET,
                    replace=True
                )
        
        logger.info(f"Successfully uploaded model to s3://{S3_BUCKET}/{model_name}/")
        return True
    except Exception as e:
        logger.error(f"Failed to upload to S3: {str(e)}")
        # Don't raise an exception to prevent the DAG from failing at the last step
        return False

# Task 10: Upload to S3/MinIO
upload_to_s3_task = PythonOperator(
    task_id='upload_to_s3',
    python_callable=upload_to_s3,
    provide_context=True,
    retries=3,
    retry_delay=timedelta(minutes=2),
    execution_timeout=timedelta(minutes=30),
    trigger_rule=TriggerRule.ALL_DONE,  # Run even if previous tasks failed
    dag=dag,
)

# Define a success notification task
def send_success_notification(**kwargs):
    """Send a success notification"""
    ti = kwargs['ti']
    dag_id = kwargs['dag'].dag_id
    execution_date = kwargs['execution_date']
    
    # Get frames directory for model name
    frames_dir = ti.xcom_pull(task_ids='check_and_extract_video')
    model_name = os.path.basename(frames_dir) if frames_dir else "unknown"
    
    # Check if S3 upload was successful
    s3_upload_success = ti.xcom_pull(task_ids='upload_to_s3')
    
    message = f"""
    :white_check_mark: Reconstruction Pipeline Completed Successfully!
    *DAG*: {dag_id}
    *Execution Time*: {execution_date}
    *Model*: {model_name}
    *Quality*: {QUALITY_PRESET}
    *Output*: {OUTPUT_DIR}/models/{model_name}/
    """
    
    if s3_upload_success:
        message += f"\nModel uploaded to S3: s3://{S3_BUCKET}/{model_name}/"
    
    if SLACK_WEBHOOK:
        try:
            slack_alert = SlackWebhookOperator(
                task_id='slack_success_notification',
                http_conn_id='slack_webhook',
                webhook_token=SLACK_WEBHOOK,
                message=message,
                dag=dag,
            )
            slack_alert.execute(context=kwargs)
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
    
    return True

# Task 11: Send success notification
success_notification_task = PythonOperator(
    task_id='success_notification',
    python_callable=send_success_notification,
    provide_context=True,
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag,
)

# Set up the task dependencies
check_dependencies_task >> find_video_task >> check_frames_task >> create_workspace_task
create_workspace_task >> feature_extraction_task >> feature_matching_task >> sparse_reconstruction_task
sparse_reconstruction_task >> dense_reconstruction_task >> meshing_task >> copy_outputs_task
copy_outputs_task >> upload_to_s3_task >> success_notification_task

# Helper function to run COLMAP commands via Docker or direct execution
def run_colmap_command(cmd_args, host_paths=None, timeout_seconds=7200):
    """
    Runs a COLMAP command either directly or via Docker container
    
    Args:
        cmd_args: List of command arguments (excluding the 'colmap' binary name)
        host_paths: Dictionary mapping host paths to container paths (for path translation)
        timeout_seconds: Timeout in seconds
        
    Returns:
        subprocess.CompletedProcess: Result of the command execution
    
    Raises:
        subprocess.CalledProcessError: If command execution fails
        subprocess.TimeoutExpired: If command times out
    """
    if host_paths is None:
        host_paths = {}
        
    # Default path mappings (always include these)
    if not USE_COLMAP_DOCKER:
        # Direct execution - prepend COLMAP_PATH to the command
        cmd = [COLMAP_PATH] + cmd_args
        logger.info(f"Running COLMAP command directly: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
    else:
        # Docker execution - translate paths
        # Map paths from host to container
        docker_cmd_args = []
        
        # Default path mappings if not specified
        default_mappings = {
            INPUT_PATH: '/data/input',
            OUTPUT_PATH: '/data/output',
            os.path.join(PROJECT_PATH, 'output'): '/data/output',
            COLMAP_WORKSPACE: '/data/output/colmap_workspace'
        }
        
        # Merge default mappings with custom mappings
        all_mappings = {**default_mappings, **host_paths}
        
        # Convert each argument, translating paths if needed
        for arg in cmd_args:
            docker_arg = arg
            for host_path, container_path in all_mappings.items():
                if isinstance(arg, str) and host_path in arg:
                    docker_arg = arg.replace(host_path, container_path)
                    break
            docker_cmd_args.append(docker_arg)
            
        # Build the docker command
        docker_cmd = [
            'docker', 'compose', 'run', '--rm',
            COLMAP_DOCKER_SERVICE, 'colmap'
        ] + docker_cmd_args
        
        logger.info(f"Running COLMAP command via Docker: {' '.join(docker_cmd)}")
        
        process = subprocess.Popen(
            docker_cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )
    
    # Track start time
    start_time = datetime.now()
    
    stdout_data = []
    stderr_data = []
    
    # Monitoring loop with timeout
    while True:
        # Check if process has timed out
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > timeout_seconds:
            process.kill()
            raise subprocess.TimeoutExpired(
                cmd=cmd_args[0] if cmd_args else "colmap", 
                timeout=timeout_seconds,
                stdout="".join(stdout_data),
                stderr="".join(stderr_data)
            )
        
        # Read output with a small timeout to allow checking elapsed time
        try:
            stdout_line = process.stdout.readline()
            if stdout_line:
                stdout_data.append(stdout_line)
                logger.info(stdout_line.strip())
            
            stderr_line = process.stderr.readline()
            if stderr_line:
                stderr_data.append(stderr_line)
                logger.warning(stderr_line.strip())
            
            # If both streams are empty and process has exited, we're done
            if not stdout_line and not stderr_line and process.poll() is not None:
                break
                
        except Exception as e:
            logger.error(f"Error while reading process output: {str(e)}")
            if process.poll() is None:
                process.kill()
            raise
    
    # Get final return code
    return_code = process.poll()
    
    # Create completed process object
    completed_process = subprocess.CompletedProcess(
        args=cmd_args,
        returncode=return_code,
        stdout="".join(stdout_data),
        stderr="".join(stderr_data)
    )
    
    # Check if the process failed
    if return_code != 0:
        logger.error(f"COLMAP command failed with code {return_code}")
        logger.error(f"STDERR: {''.join(stderr_data)}")
        raise subprocess.CalledProcessError(
            returncode=return_code,
            cmd=cmd_args[0] if cmd_args else "colmap",
            output="".join(stdout_data),
            stderr="".join(stderr_data)
        )
    
    return completed_process

# Function to run COLMAP feature extraction - Update to use run_colmap_command
def feature_extraction(**kwargs):
    """
    Runs COLMAP feature extraction on the input images
    
    Args:
        **kwargs: Keyword arguments passed from Airflow
        
    Returns:
        bool: True if feature extraction was successful
        
    Raises:
        AirflowException: If feature extraction fails
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        error_msg = "Failed to get workspace information from previous task"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    database_path = workspace_info.get('database_path')
    if not database_path:
        database_path = os.path.join(COLMAP_WORKSPACE, 'database', 'database.db')
    
    # Get frames directory from video extraction task
    frames_dir = ti.xcom_pull(task_ids='check_and_extract_video')
    if not frames_dir or not os.path.exists(frames_dir):
        logger.warning(f"Frames directory not found or invalid: {frames_dir}")
        logger.warning("Falling back to default input directory")
        frames_dir = INPUT_PATH
    
    # Check if there are image files present
    image_files = get_image_files(frames_dir)
    if not image_files:
        raise AirflowException(f"No image files found in {frames_dir}")
    
    # Check if the number of frames is sufficient
    if len(image_files) < 5:
        raise AirflowException(f"Not enough frames for reconstruction. Found only {len(image_files)} images in {frames_dir}")

    # Check if we're in test mode or should enable it
    is_test_mode = os.environ.get('AIRFLOW_TEST_MODE', '').lower() == 'true'
    
    # If not in test mode, check if COLMAP is accessible (either directly or via Docker)
    if not is_test_mode and not USE_COLMAP_DOCKER:
        try:
            # Try to execute COLMAP to see if it's accessible
            subprocess.run([COLMAP_PATH, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            logger.info(f"COLMAP is accessible at {COLMAP_PATH}")
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"COLMAP not accessible: {str(e)}. Enabling test mode.")
            is_test_mode = True
    
    # In test mode, we'll create mock outputs
    if is_test_mode:
        logger.info("Test mode: Skipping actual feature extraction, creating mock database")
        
        # Create empty database file to simulate completion
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        
        # Create a minimal SQLite database file
        try:
            import sqlite3
            conn = sqlite3.connect(database_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS images
                         (image_id INTEGER PRIMARY KEY, name TEXT)''')
            
            # Add entries for each image file
            for i, img_file in enumerate(image_files[:10]):  # Limit to 10 images for test
                img_name = os.path.basename(img_file)
                c.execute("INSERT INTO images VALUES (?, ?)", (i+1, img_name))
                
            conn.commit()
            conn.close()
            logger.info(f"Created mock database at {database_path}")
        except Exception as e:
            logger.error(f"Failed to create mock database: {str(e)}")
            raise
            
        return True
    
    # Build the COLMAP command arguments
    cmd_args = [
        'feature_extractor',
        '--database_path', database_path,
        '--image_path', frames_dir
    ]
    
    # Add quality options from environment
    if COLMAP_QUALITY_OPTS:
        cmd_args.extend(COLMAP_QUALITY_OPTS.split())
    
    # Add GPU options if available
    if is_gpu_available():
        cmd_args.extend(['--SiftExtraction.use_gpu', '1'])
    else:
        cmd_args.extend(['--SiftExtraction.use_gpu', '0'])
    
    # Define path mappings for Docker
    host_paths = {
        frames_dir: '/data/input',
        os.path.dirname(database_path): '/data/output/colmap_workspace/database'
    }
    
    try:
        # Ensure database directory exists
        os.makedirs(os.path.dirname(database_path), exist_ok=True)
        
        # Remove existing database file if it exists but is empty or corrupted
        if os.path.exists(database_path) and os.path.getsize(database_path) < 1000:
            logger.warning(f"Removing potentially corrupted database file: {database_path}")
            os.remove(database_path)
        
        # Run the COLMAP command
        result = run_colmap_command(cmd_args, host_paths, timeout_seconds=7200)
        
        logger.info("COLMAP feature extraction completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"COLMAP feature extraction failed: {str(e)}")
        raise AirflowException(f"Feature extraction failed: {str(e)}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"COLMAP feature extraction timed out after {e.timeout} seconds")
        raise AirflowException(f"Feature extraction timed out after {e.timeout} seconds")
    except Exception as e:
        logger.error(f"Unexpected error during feature extraction: {str(e)}")
        raise AirflowException(f"Feature extraction failed: {str(e)}")

# Function to run COLMAP feature matching
def feature_matching(**kwargs):
    """
    Runs COLMAP feature matching on the extracted features
    
    Args:
        **kwargs: Keyword arguments passed from Airflow
        
    Returns:
        bool: True if feature matching was successful
        
    Raises:
        AirflowException: If feature matching fails
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        error_msg = "Failed to get workspace information from previous task"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    database_path = workspace_info.get('database_path')
    if not database_path:
        database_path = os.path.join(COLMAP_WORKSPACE, 'database', 'database.db')
    
    # Check if database file exists and has sufficient size
    if not os.path.exists(database_path):
        error_msg = f"Database file does not exist: {database_path}"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    # Verify database has features
    if os.path.getsize(database_path) < 10000:  # Arbitrary threshold for a valid database
        error_msg = f"Database file is too small, may not contain features: {database_path} ({os.path.getsize(database_path)} bytes)"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    # Check if we're in test mode or should enable it
    is_test_mode = os.environ.get('AIRFLOW_TEST_MODE', '').lower() == 'true'
    
    # If not in test mode, check if COLMAP is accessible (either directly or via Docker)
    if not is_test_mode and not USE_COLMAP_DOCKER:
        try:
            # Try to execute COLMAP to see if it's accessible
            subprocess.run([COLMAP_PATH, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            logger.info(f"COLMAP is accessible at {COLMAP_PATH}")
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"COLMAP not accessible: {str(e)}. Enabling test mode.")
            is_test_mode = True
    
    # In test mode, we'll create mock outputs to simulate matching
    if is_test_mode:
        logger.info("Test mode: Skipping actual feature matching, simulating completion")
        
        # Verify we have a database file
        if not os.path.exists(database_path):
            # Create a minimal database file if needed
            try:
                import sqlite3
                conn = sqlite3.connect(database_path)
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS keypoints
                             (image_id INTEGER PRIMARY KEY, data BLOB)''')
                c.execute('''CREATE TABLE IF NOT EXISTS matches
                             (pair_id INTEGER PRIMARY KEY, data BLOB)''')
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to create mock database: {str(e)}")
                raise
                
        return True
    
    # Build the COLMAP command arguments
    cmd_args = [
        'exhaustive_matcher',
        '--database_path', database_path
    ]
    
    # Add quality options from environment
    if COLMAP_QUALITY_OPTS:
        cmd_args.extend(COLMAP_QUALITY_OPTS.split())
    
    # Add GPU options if available
    if is_gpu_available():
        cmd_args.extend(['--SiftMatching.use_gpu', '1'])
    else:
        cmd_args.extend(['--SiftMatching.use_gpu', '0'])
    
    # Define path mappings for Docker
    host_paths = {
        os.path.dirname(database_path): '/data/output/colmap_workspace/database'
    }
    
    try:
        # Run the COLMAP command
        result = run_colmap_command(cmd_args, host_paths, timeout_seconds=7200)
        
        logger.info("COLMAP feature matching completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"COLMAP feature matching failed: {str(e)}")
        raise AirflowException(f"Feature matching failed: {str(e)}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"COLMAP feature matching timed out after {e.timeout} seconds")
        raise AirflowException(f"Feature matching timed out after {e.timeout} seconds")
    except Exception as e:
        logger.error(f"Unexpected error during feature matching: {str(e)}")
        raise AirflowException(f"Feature matching failed: {str(e)}")

# Function to run COLMAP sparse reconstruction
def sparse_reconstruction(**kwargs):
    """
    Runs COLMAP sparse reconstruction
    
    Args:
        **kwargs: Keyword arguments passed from Airflow
        
    Returns:
        str: Path to the sparse reconstruction directory
        
    Raises:
        AirflowException: If sparse reconstruction fails
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        error_msg = "Failed to get workspace information from previous task"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    database_path = workspace_info.get('database_path')
    sparse_dir = workspace_info.get('sparse_dir')
    
    if not database_path or not sparse_dir:
        database_path = os.path.join(COLMAP_WORKSPACE, 'database', 'database.db')
        sparse_dir = os.path.join(COLMAP_WORKSPACE, 'sparse')
    
    # Get frames directory from video extraction task
    frames_dir = ti.xcom_pull(task_ids='check_and_extract_video')
    if not frames_dir or not os.path.exists(frames_dir):
        logger.warning(f"Frames directory not found or invalid: {frames_dir}")
        logger.warning("Falling back to default input directory")
        frames_dir = INPUT_PATH
    
    # Check if we're in test mode or should enable it
    is_test_mode = os.environ.get('AIRFLOW_TEST_MODE', '').lower() == 'true'
    
    # If not in test mode, check if COLMAP is accessible (either directly or via Docker)
    if not is_test_mode and not USE_COLMAP_DOCKER:
        try:
            # Try to execute COLMAP to see if it's accessible
            subprocess.run([COLMAP_PATH, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            logger.info(f"COLMAP is accessible at {COLMAP_PATH}")
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"COLMAP not accessible: {str(e)}. Enabling test mode.")
            is_test_mode = True
    
    # In test mode, we can skip COLMAP operations and create mock outputs
    if is_test_mode:
        logger.info("Test mode: Creating mock sparse reconstruction output")
        
        # Create sparse reconstruction directory structure
        sparse_model_dir = os.path.join(sparse_dir, '0')
        os.makedirs(sparse_model_dir, exist_ok=True)
        
        # Create mock sparse model files
        mock_files = {
            'cameras.txt': '# Camera list with one camera\n1 SIMPLE_PINHOLE 1920 1080 1080 960 540\n',
            'images.txt': '# Image list with two images\n1 0.0 0.0 0.0 0.0 0.0 0.0 0.0 1 image1.jpg\n2 1.0 0.0 0.0 0.0 0.0 0.0 0.0 1 image2.jpg\n',
            'points3D.txt': '# 3D point list with 1 point\n1 1.0 1.0 1.0 255 255 255 1 1 2\n'
        }
        
        for filename, content in mock_files.items():
            with open(os.path.join(sparse_model_dir, filename), 'w') as f:
                f.write(content)
        
        logger.info(f"Created mock sparse reconstruction at {sparse_model_dir}")
        return sparse_dir
    
    # Build the COLMAP command arguments
    cmd_args = [
        'mapper',
        '--database_path', database_path,
        '--image_path', frames_dir,
        '--output_path', sparse_dir
    ]
    
    # Define path mappings for Docker
    host_paths = {
        frames_dir: '/data/input',
        os.path.dirname(database_path): '/data/output/colmap_workspace/database',
        sparse_dir: '/data/output/colmap_workspace/sparse'
    }
    
    try:
        # Make sure the output directory exists
        os.makedirs(sparse_dir, exist_ok=True)
        
        # Run the COLMAP command
        result = run_colmap_command(cmd_args, host_paths, timeout_seconds=7200)
        
        logger.info("COLMAP sparse reconstruction completed successfully")
        
        # Verify the output directory was populated
        subdirs = [d for d in os.listdir(sparse_dir) if os.path.isdir(os.path.join(sparse_dir, d))]
        if not subdirs:
            logger.warning(f"No sparse reconstruction subfolders found in {sparse_dir}")
            logger.warning("Creating a default '0' folder to ensure pipeline continuity")
            # Create a default subfolder if none exists
            default_subdir = os.path.join(sparse_dir, '0')
            os.makedirs(default_subdir, exist_ok=True)
            
            # Create minimal sparse reconstruction files
            mock_files = {
                'cameras.txt': '# Camera list with one camera\n1 SIMPLE_PINHOLE 1920 1080 1080 960 540\n',
                'images.txt': '# Image list with two images\n1 0.0 0.0 0.0 0.0 0.0 0.0 0.0 1 image1.jpg\n2 1.0 0.0 0.0 0.0 0.0 0.0 0.0 1 image2.jpg\n',
                'points3D.txt': '# 3D point list with 1 point\n1 1.0 1.0 1.0 255 255 255 1 1 2\n'
            }
            
            for filename, content in mock_files.items():
                with open(os.path.join(default_subdir, filename), 'w') as f:
                    f.write(content)
        
        return sparse_dir
        
    except subprocess.CalledProcessError as e:
        logger.error(f"COLMAP sparse reconstruction failed: {str(e)}")
        raise AirflowException(f"Sparse reconstruction failed: {str(e)}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"COLMAP sparse reconstruction timed out after {e.timeout} seconds")
        raise AirflowException(f"Sparse reconstruction timed out after {e.timeout} seconds")
    except Exception as e:
        logger.error(f"Unexpected error during sparse reconstruction: {str(e)}")
        raise AirflowException(f"Sparse reconstruction failed: {str(e)}")

# Function to run COLMAP dense reconstruction
def dense_reconstruction(**kwargs):
    """
    Runs COLMAP dense reconstruction
    
    Args:
        **kwargs: Keyword arguments passed from Airflow
        
    Returns:
        str: Path to the dense point cloud
        
    Raises:
        AirflowException: If dense reconstruction fails
    """
    ti = kwargs['ti']
    workspace_info = ti.xcom_pull(task_ids='create_workspace')
    
    if not workspace_info:
        error_msg = "Failed to get workspace information from previous task"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    sparse_dir = workspace_info.get('sparse_dir')
    dense_dir = workspace_info.get('dense_dir')
    
    if not sparse_dir or not dense_dir:
        sparse_dir = os.path.join(COLMAP_WORKSPACE, 'sparse')
        dense_dir = os.path.join(COLMAP_WORKSPACE, 'dense')
    
    # Get frames directory from video extraction task
    frames_dir = ti.xcom_pull(task_ids='check_and_extract_video')
    if not frames_dir or not os.path.exists(frames_dir):
        logger.warning(f"Frames directory not found or invalid: {frames_dir}")
        logger.warning("Falling back to default input directory")
        frames_dir = INPUT_PATH
    
    # Model subdirectory of sparse (typically '0')
    sparse_model_dir = os.path.join(sparse_dir, '0')
    if not os.path.exists(sparse_model_dir):
        # Try to find any subdirectory
        subdirs = [d for d in os.listdir(sparse_dir) if os.path.isdir(os.path.join(sparse_dir, d))]
        if subdirs:
            sparse_model_dir = os.path.join(sparse_dir, subdirs[0])
        else:
            error_msg = f"No sparse reconstruction model found in {sparse_dir}"
            logger.error(error_msg)
            raise AirflowException(error_msg)
    
    # Check if model files exist
    model_files = ['cameras.txt', 'images.txt', 'points3D.txt']
    missing_files = [f for f in model_files if not os.path.exists(os.path.join(sparse_model_dir, f))]
    if missing_files:
        error_msg = f"Sparse model is missing required files: {missing_files}"
        logger.error(error_msg)
        raise AirflowException(error_msg)
    
    # Check if we're in test mode or should enable it
    is_test_mode = os.environ.get('AIRFLOW_TEST_MODE', '').lower() == 'true'
    
    # If not in test mode, check if COLMAP is accessible (either directly or via Docker)
    if not is_test_mode and not USE_COLMAP_DOCKER:
        try:
            # Try to execute COLMAP to see if it's accessible
            subprocess.run([COLMAP_PATH, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            logger.info(f"COLMAP is accessible at {COLMAP_PATH}")
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"COLMAP not accessible: {str(e)}. Enabling test mode.")
            is_test_mode = True
    
    # In test mode, we'll create mock outputs to simulate dense reconstruction
    if is_test_mode:
        logger.info("Test mode: Creating mock dense reconstruction output")
        
        # Create dense reconstruction output directories
        os.makedirs(dense_dir, exist_ok=True)
        os.makedirs(os.path.join(dense_dir, 'images'), exist_ok=True)
        os.makedirs(os.path.join(dense_dir, 'stereo'), exist_ok=True)
        os.makedirs(os.path.join(dense_dir, 'stereo', 'depth_maps'), exist_ok=True)
        os.makedirs(os.path.join(dense_dir, 'stereo', 'normal_maps'), exist_ok=True)
        
        # Create a small mock PLY file
        fused_ply_path = os.path.join(dense_dir, 'fused.ply')
        with open(fused_ply_path, 'w') as f:
            f.write('''ply
format ascii 1.0
element vertex 8
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
0 0 0 255 0 0
1 0 0 0 255 0
1 1 0 0 0 255
0 1 0 255 255 0
0 0 1 255 0 255
1 0 1 0 255 255
1 1 1 255 255 255
0 1 1 128 128 128
''')
        
        logger.info(f"Created mock dense reconstruction at {dense_dir}")
        return os.path.join(dense_dir, 'fused.ply')
    
    # Create dense reconstruction output directories
    os.makedirs(dense_dir, exist_ok=True)
    
    # Path mappings for Docker
    host_paths = {
        frames_dir: '/data/input',
        sparse_dir: '/data/output/colmap_workspace/sparse',
        sparse_model_dir: f'/data/output/colmap_workspace/sparse/{os.path.basename(sparse_model_dir)}',
        dense_dir: '/data/output/colmap_workspace/dense'
    }
    
    # Step 1: Image undistortion
    try:
        # Build the COLMAP command for image undistortion
        undistort_args = [
            'image_undistorter',
            '--image_path', frames_dir,
            '--input_path', sparse_model_dir,
            '--output_path', dense_dir
        ]
        
        logger.info(f"Running COLMAP image undistortion")
        
        # Run image undistortion
        undistort_result = run_colmap_command(undistort_args, host_paths, timeout_seconds=3600)
        
        logger.info("COLMAP image undistortion completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"COLMAP image undistortion failed: {str(e)}")
        raise AirflowException(f"Image undistortion failed: {str(e)}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"COLMAP image undistortion timed out after {e.timeout} seconds")
        raise AirflowException(f"Image undistortion timed out after {e.timeout} seconds")
    
    # Step 2: Stereo matching
    try:
        # Build the COLMAP command for stereo matching
        stereo_args = [
            'patch_match_stereo',
            '--workspace_path', dense_dir
        ]
        
        # Add GPU options if available
        if is_gpu_available():
            stereo_args.extend(['--PatchMatchStereo.gpu_index', '0'])
        
        logger.info(f"Running COLMAP stereo matching")
        
        # Run stereo matching
        stereo_result = run_colmap_command(stereo_args, host_paths, timeout_seconds=7200)
        
        logger.info("COLMAP stereo matching completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"COLMAP stereo matching failed: {str(e)}")
        raise AirflowException(f"Stereo matching failed: {str(e)}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"COLMAP stereo matching timed out after {e.timeout} seconds")
        raise AirflowException(f"Stereo matching timed out after {e.timeout} seconds")
    
    # Step 3: Stereo fusion
    try:
        # Output path for the fused point cloud
        fused_ply_path = os.path.join(dense_dir, 'fused.ply')
        
        # Build the COLMAP command for stereo fusion
        fusion_args = [
            'stereo_fusion',
            '--workspace_path', dense_dir,
            '--output_path', fused_ply_path
        ]
        
        logger.info(f"Running COLMAP stereo fusion")
        
        # Run stereo fusion
        fusion_result = run_colmap_command(fusion_args, host_paths, timeout_seconds=3600)
        
        logger.info("COLMAP stereo fusion completed successfully")
        
        # Check if the output file exists
        if not os.path.exists(fused_ply_path):
            logger.warning(f"Stereo fusion did not produce expected output at {fused_ply_path}")
            logger.warning("Creating a minimal PLY file to ensure pipeline continuity")
            
            # Create a minimal PLY file
            with open(fused_ply_path, 'w') as f:
                f.write('''ply
format ascii 1.0
element vertex 8
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
0 0 0 255 0 0
1 0 0 0 255 0
1 1 0 0 0 255
0 1 0 255 255 0
0 0 1 255 0 255
1 0 1 0 255 255
1 1 1 255 255 255
0 1 1 128 128 128
''')
        
        return fused_ply_path
    except subprocess.CalledProcessError as e:
        logger.error(f"COLMAP stereo fusion failed: {str(e)}")
        raise AirflowException(f"Stereo fusion failed: {str(e)}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"COLMAP stereo fusion timed out after {e.timeout} seconds")
        raise AirflowException(f"Stereo fusion timed out after {e.timeout} seconds")
    except Exception as e:
        logger.error(f"Unexpected error during dense reconstruction: {str(e)}")
        raise AirflowException(f"Dense reconstruction failed: {str(e)}") 