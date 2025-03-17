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
logger = logging.getLogger("multi_reconstruction_pipeline")

# Configure paths - Use environment variables or Airflow Variables for better configurability
PROJECT_PATH = os.environ.get('PROJECT_PATH', '/opt/airflow/data')
IMAGE_SETS_PATH = os.environ.get('IMAGE_SETS_PATH', os.path.join(PROJECT_PATH, 'image_sets'))
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', os.path.join(PROJECT_PATH, 'output'))
COLMAP_PATH = os.environ.get('COLMAP_PATH', 'colmap')

# Set default meshing options
MESHING_TOOL = os.environ.get('MESHING_TOOL', 'poisson')
MESH_OCTREE_DEPTH = os.environ.get('MESH_OCTREE_DEPTH', '9')
MESH_POINT_WEIGHT = os.environ.get('MESH_POINT_WEIGHT', '1')
MESH_TRIM = os.environ.get('MESH_TRIM', '7')

# Use Docker container instead of local COLMAP?
USE_COLMAP_DOCKER = os.environ.get('USE_COLMAP_DOCKER', 'false').lower() == 'true'
COLMAP_DOCKER_SERVICE = os.environ.get('COLMAP_DOCKER_SERVICE', 'colmap')

# S3/MinIO configuration
S3_ENABLED = os.environ.get('S3_ENABLED', 'false').lower() == 'true'
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', 'http://minio:9000')
S3_BUCKET = os.environ.get('S3_BUCKET', 'models')
S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY', '')
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY', '')

# Set default quality presets based on environment variable
QUALITY_PRESET = os.environ.get('QUALITY_PRESET', 'medium').lower()

# Set quality-specific parameters
if QUALITY_PRESET == 'low':
    FEATURE_EXTRACTOR_ARGS = "--SiftExtraction.max_image_size 1000 --SiftExtraction.estimate_affine_shape 0 --SiftExtraction.domain_size_pooling 0"
    MAX_NUM_MATCHES = "10000"
    SPARSE_ARGS = "--bundle_adjustment_max_iterations 20"
    DENSE_MAX_IMAGE_SIZE = "1000"
elif QUALITY_PRESET == 'high':
    FEATURE_EXTRACTOR_ARGS = "--SiftExtraction.max_image_size 3200 --SiftExtraction.estimate_affine_shape 1 --SiftExtraction.domain_size_pooling 1"
    MAX_NUM_MATCHES = "50000"
    SPARSE_ARGS = "--bundle_adjustment_max_iterations 100"
    DENSE_MAX_IMAGE_SIZE = "2000"
else:  # medium (default)
    FEATURE_EXTRACTOR_ARGS = "--SiftExtraction.max_image_size 2000 --SiftExtraction.estimate_affine_shape 0 --SiftExtraction.domain_size_pooling 0"
    MAX_NUM_MATCHES = "25000"
    SPARSE_ARGS = "--bundle_adjustment_max_iterations 50"
    DENSE_MAX_IMAGE_SIZE = "1500"

# Function to check GPU availability
def is_gpu_available():
    """Check if GPU is available for computation"""
    try:
        if USE_COLMAP_DOCKER:
            # When using Docker, we assume the COLMAP container has GPU if requested
            return True
        else:
            # Try to import CUDA modules
            import torch
            return torch.cuda.is_available()
    except ImportError:
        # If torch is not available, try nvidia-smi
        try:
            subprocess.check_output(['nvidia-smi'], stderr=subprocess.STDOUT)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    logger.warning("GPU not detected. Using CPU for reconstruction (this will be slow).")
    return False

# Function to check dependencies
def check_dependencies(**kwargs):
    """Check if necessary dependencies are available"""
    ti = kwargs['ti']
    
    if USE_COLMAP_DOCKER:
        logger.info("Using COLMAP via Docker, skipping local dependency check")
        return True
    
    try:
        # Check if COLMAP is available
        colmap_version = subprocess.check_output([COLMAP_PATH, "--version"], stderr=subprocess.STDOUT)
        logger.info(f"COLMAP is available: {colmap_version.decode('utf-8').strip()}")
        
        # Check for other dependencies
        # ...
        
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"COLMAP dependency check failed: {str(e)}")
        return False

# Function to handle task failures
def task_failure_handler(context):
    """Handler for task failures that can send notifications"""
    task_instance = context['task_instance']
    task_id = task_instance.task_id
    dag_id = task_instance.dag_id
    execution_date = context['execution_date']
    exception = context.get('exception')
    
    logger.error(f"Task {task_id} in DAG {dag_id} failed on {execution_date}: {str(exception)}")
    
    # Send Slack notification if configured
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if slack_webhook_url:
        try:
            webhook_operator = SlackWebhookOperator(
                task_id=f'slack_notification_{task_id}',
                webhook_token=slack_webhook_url,
                message=f":red_circle: Task *{task_id}* failed in DAG *{dag_id}*\n"
                        f"Execution date: {execution_date}\n"
                        f"Error: ```{str(exception)}```",
                username='Airflow',
                icon_emoji=':airflow:',
                http_conn_id='slack_webhook'
            )
            webhook_operator.execute(context)
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")

# Function to get image sets
def get_image_sets(**kwargs):
    """Get list of available image sets and pass them to the next task"""
    ti = kwargs['ti']
    
    # List all subdirectories in the image_sets path
    image_sets = []
    for item in os.listdir(IMAGE_SETS_PATH):
        item_path = os.path.join(IMAGE_SETS_PATH, item)
        if os.path.isdir(item_path):
            # Check if directory has image files
            image_files = glob.glob(os.path.join(item_path, "*.jpg")) + glob.glob(os.path.join(item_path, "*.png"))
            if image_files:
                image_sets.append(item)
    
    if not image_sets:
        logger.warning("No image sets found in the image_sets directory!")
        return []
    
    logger.info(f"Found {len(image_sets)} image sets: {', '.join(image_sets)}")
    
    # Store the list of image sets as XCom
    return image_sets

# Function to run a COLMAP command
def run_colmap_command(cmd_args, host_paths=None, timeout_seconds=7200):
    """
    Run a COLMAP command either directly or via Docker
    
    Args:
        cmd_args: List of command arguments for COLMAP
        host_paths: Dictionary mapping container paths to host paths (for Docker)
        timeout_seconds: Maximum execution time in seconds
    
    Returns:
        Command output
    """
    if USE_COLMAP_DOCKER:
        # Prepare Docker command
        docker_cmd = ['docker', 'exec']
        
        # Add volume mappings if provided
        volume_args = []
        if host_paths:
            for host_path, container_path in host_paths.items():
                volume_args.extend(['-v', f"{host_path}:{container_path}"])
        
        # Build the final Docker command
        docker_cmd.extend([COLMAP_DOCKER_SERVICE, COLMAP_PATH] + cmd_args)
        
        # Run the Docker command
        logger.info(f"Running Docker COLMAP command: {' '.join(docker_cmd)}")
        result = subprocess.run(docker_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds)
    else:
        # Run COLMAP directly
        colmap_cmd = [COLMAP_PATH] + cmd_args
        logger.info(f"Running COLMAP command: {' '.join(colmap_cmd)}")
        result = subprocess.run(colmap_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds)
    
    # Log command output
    if result.stdout:
        logger.info(f"COLMAP command stdout: {result.stdout.decode('utf-8')}")
    if result.stderr:
        logger.warning(f"COLMAP command stderr: {result.stderr.decode('utf-8')}")
    
    return result

# Function to create workspace for each image set
def create_workspace_for_set(image_set_name, **kwargs):
    """
    Create a COLMAP workspace for the specified image set
    
    Args:
        image_set_name: Name of the image set to process
        
    Returns:
        Dictionary with workspace paths
    """
    ti = kwargs['ti']
    
    # Create paths
    image_set_dir = os.path.join(IMAGE_SETS_PATH, image_set_name)
    output_base_dir = os.path.join(OUTPUT_PATH, image_set_name)
    workspace_dir = os.path.join(output_base_dir, 'colmap_workspace')
    
    # Create workspace directories
    os.makedirs(workspace_dir, exist_ok=True)
    sparse_dir = os.path.join(workspace_dir, 'sparse')
    os.makedirs(sparse_dir, exist_ok=True)
    dense_dir = os.path.join(workspace_dir, 'dense')
    os.makedirs(dense_dir, exist_ok=True)
    
    # Create a database directory
    database_dir = os.path.join(workspace_dir, 'database')
    os.makedirs(database_dir, exist_ok=True)
    database_path = os.path.join(database_dir, 'database.db')
    
    # Log the workspace creation
    logger.info(f"Created COLMAP workspace for {image_set_name}:")
    logger.info(f" - Workspace: {workspace_dir}")
    logger.info(f" - Database: {database_path}")
    logger.info(f" - Sparse: {sparse_dir}")
    logger.info(f" - Dense: {dense_dir}")
    
    # Return workspace paths
    workspace_info = {
        'image_set_dir': image_set_dir,
        'output_base_dir': output_base_dir,
        'workspace_dir': workspace_dir,
        'database_path': database_path,
        'sparse_dir': sparse_dir,
        'dense_dir': dense_dir
    }
    
    return workspace_info

# Function to run the reconstruction pipeline for a specific image set
def run_reconstruction_for_set(image_set_name, **kwargs):
    """Run the full reconstruction pipeline for a specific image set"""
    ti = kwargs['ti']
    
    # Create workspace for the image set
    workspace_info = create_workspace_for_set(image_set_name, **kwargs)
    
    # Extract workspace paths
    image_set_dir = workspace_info['image_set_dir']
    database_path = workspace_info['database_path']
    sparse_dir = workspace_info['sparse_dir']
    dense_dir = workspace_info['dense_dir']
    
    # 1. Feature extraction
    try:
        # Build the COLMAP command for feature extraction
        extraction_args = [
            'feature_extractor',
            '--database_path', database_path,
            '--image_path', image_set_dir
        ]
        
        # Add quality-specific arguments
        extraction_args.extend(FEATURE_EXTRACTOR_ARGS.split())
        
        # Add GPU options if available
        if is_gpu_available():
            extraction_args.extend(['--SiftExtraction.use_gpu', '1'])
        else:
            extraction_args.extend(['--SiftExtraction.use_gpu', '0'])
        
        logger.info(f"Running COLMAP feature extraction for {image_set_name}")
        
        # Path mappings for Docker
        host_paths = {
            image_set_dir: '/data/input',
            os.path.dirname(database_path): '/data/database',
            sparse_dir: '/data/sparse',
            dense_dir: '/data/dense'
        }
        
        # Run feature extraction
        extraction_result = run_colmap_command(extraction_args, host_paths)
        
        logger.info(f"COLMAP feature extraction completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Feature extraction failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Feature extraction failed: {str(e)}")
    
    # 2. Feature matching
    try:
        # Build the COLMAP command for feature matching
        matching_args = [
            'exhaustive_matcher',
            '--database_path', database_path,
            '--SiftMatching.max_num_matches', MAX_NUM_MATCHES
        ]
        
        # Add GPU options if available
        if is_gpu_available():
            matching_args.extend(['--SiftMatching.use_gpu', '1'])
        else:
            matching_args.extend(['--SiftMatching.use_gpu', '0'])
        
        logger.info(f"Running COLMAP feature matching for {image_set_name}")
        
        # Run feature matching
        matching_result = run_colmap_command(matching_args, host_paths)
        
        logger.info(f"COLMAP feature matching completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Feature matching failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Feature matching failed: {str(e)}")
    
    # 3. Sparse reconstruction
    try:
        # Create sparse model directory
        sparse_model_dir = os.path.join(sparse_dir, '0')
        os.makedirs(sparse_model_dir, exist_ok=True)
        
        # Build the COLMAP command for mapper
        mapper_args = [
            'mapper',
            '--database_path', database_path,
            '--image_path', image_set_dir,
            '--output_path', sparse_model_dir
        ]
        
        # Add quality-specific arguments
        mapper_args.extend(SPARSE_ARGS.split())
        
        logger.info(f"Running COLMAP sparse reconstruction for {image_set_name}")
        
        # Update host paths for Docker
        host_paths.update({
            sparse_model_dir: '/data/sparse/0'
        })
        
        # Run mapper
        mapper_result = run_colmap_command(mapper_args, host_paths)
        
        logger.info(f"COLMAP sparse reconstruction completed for {image_set_name}")
        
        # Return sparse model directory
        return {
            'sparse_model_dir': sparse_model_dir,
            'database_path': database_path,
            'image_set_dir': image_set_dir,
            'dense_dir': dense_dir,
            'output_base_dir': workspace_info['output_base_dir']
        }
    except Exception as e:
        logger.error(f"Sparse reconstruction failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Sparse reconstruction failed: {str(e)}")

# Function to run dense reconstruction for a specific image set
def run_dense_reconstruction_for_set(image_set_name, **kwargs):
    """Run dense reconstruction for a specific image set"""
    ti = kwargs['ti']
    
    # Get sparse reconstruction info
    task_id = f'sparse_reconstruction_{image_set_name}'
    sparse_info = ti.xcom_pull(task_ids=task_id)
    
    if not sparse_info:
        logger.error(f"No sparse reconstruction information found for {image_set_name}")
        raise AirflowException(f"No sparse reconstruction information found for {image_set_name}")
    
    # Extract paths
    sparse_model_dir = sparse_info['sparse_model_dir']
    image_set_dir = sparse_info['image_set_dir']
    dense_dir = sparse_info['dense_dir']
    output_base_dir = sparse_info['output_base_dir']
    
    # Path mappings for Docker
    host_paths = {
        image_set_dir: '/data/input',
        sparse_model_dir: f'/data/sparse/0',
        os.path.dirname(sparse_model_dir): '/data/sparse',
        dense_dir: '/data/dense'
    }
    
    # 1. Image undistortion
    try:
        # Build the COLMAP command for image undistortion
        undistort_args = [
            'image_undistorter',
            '--image_path', image_set_dir,
            '--input_path', sparse_model_dir,
            '--output_path', dense_dir,
            '--max_image_size', DENSE_MAX_IMAGE_SIZE
        ]
        
        logger.info(f"Running COLMAP image undistortion for {image_set_name}")
        
        # Run image undistortion
        undistort_result = run_colmap_command(undistort_args, host_paths)
        
        logger.info(f"COLMAP image undistortion completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Image undistortion failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Image undistortion failed: {str(e)}")
    
    # 2. Stereo matching
    try:
        # Build the COLMAP command for stereo matching
        stereo_args = [
            'patch_match_stereo',
            '--workspace_path', dense_dir
        ]
        
        # Add GPU options if available
        if is_gpu_available():
            stereo_args.extend(['--PatchMatchStereo.gpu_index', '0'])
        
        logger.info(f"Running COLMAP stereo matching for {image_set_name}")
        
        # Run stereo matching
        stereo_result = run_colmap_command(stereo_args, host_paths)
        
        logger.info(f"COLMAP stereo matching completed for {image_set_name}")
    except Exception as e:
        logger.error(f"Stereo matching failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Stereo matching failed: {str(e)}")
    
    # 3. Stereo fusion
    try:
        # Output path for the fused point cloud
        fused_ply_path = os.path.join(dense_dir, 'fused.ply')
        
        # Build the COLMAP command for stereo fusion
        fusion_args = [
            'stereo_fusion',
            '--workspace_path', dense_dir,
            '--output_path', fused_ply_path
        ]
        
        logger.info(f"Running COLMAP stereo fusion for {image_set_name}")
        
        # Run stereo fusion
        fusion_result = run_colmap_command(fusion_args, host_paths)
        
        logger.info(f"COLMAP stereo fusion completed for {image_set_name}")
        
        # Return point cloud path
        return {
            'fused_ply_path': fused_ply_path,
            'image_set_name': image_set_name,
            'sparse_model_dir': sparse_model_dir,
            'image_set_dir': image_set_dir,
            'dense_dir': dense_dir,
            'output_base_dir': output_base_dir
        }
    except Exception as e:
        logger.error(f"Stereo fusion failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Stereo fusion failed: {str(e)}")

# Function to generate mesh from point cloud for a specific image set
def generate_mesh_for_set(image_set_name, **kwargs):
    """Generate a 3D mesh from the point cloud for a specific image set"""
    ti = kwargs['ti']
    
    # Get dense reconstruction info
    task_id = f'dense_reconstruction_{image_set_name}'
    dense_info = ti.xcom_pull(task_ids=task_id)
    
    if not dense_info:
        logger.error(f"No dense reconstruction information found for {image_set_name}")
        raise AirflowException(f"No dense reconstruction information found for {image_set_name}")
    
    # Extract paths
    fused_ply_path = dense_info['fused_ply_path']
    output_base_dir = dense_info['output_base_dir']
    
    # Check if the point cloud exists
    if not os.path.exists(fused_ply_path):
        logger.error(f"Point cloud file not found at {fused_ply_path}")
        raise AirflowException(f"Point cloud file not found at {fused_ply_path}")
    
    # Set up mesh output path
    mesh_output_path = os.path.join(output_base_dir, 'mesh.ply')
    
    # Generate mesh with PoissonRecon
    try:
        logger.info(f"Generating mesh for {image_set_name} using {MESHING_TOOL} method")
        
        if MESHING_TOOL.lower() == 'poisson':
            # Use PoissonRecon (external tool must be installed)
            cmd = [
                'PoissonRecon',
                '--in', fused_ply_path,
                '--out', mesh_output_path,
                '--depth', MESH_OCTREE_DEPTH,
                '--pointWeight', MESH_POINT_WEIGHT,
                '--samplesPerNode', '1.0',
                '--threads', '0'
            ]
            
            logger.info(f"Running PoissonRecon command: {' '.join(cmd)}")
            
            # Run PoissonRecon
            process = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.stdout:
                logger.info(f"PoissonRecon stdout: {process.stdout.decode('utf-8')}")
            if process.stderr:
                logger.warning(f"PoissonRecon stderr: {process.stderr.decode('utf-8')}")
                
            logger.info(f"Mesh generation completed for {image_set_name}")
            
        elif MESHING_TOOL.lower() == 'delaunay':
            # Use COLMAP's delaunay mesher
            cmd = [
                COLMAP_PATH,
                'delaunay_mesher',
                '--input_path', os.path.dirname(fused_ply_path),
                '--output_path', mesh_output_path
            ]
            
            logger.info(f"Running COLMAP delaunay_mesher command: {' '.join(cmd)}")
            
            # Run delaunay_mesher
            process = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.stdout:
                logger.info(f"COLMAP delaunay_mesher stdout: {process.stdout.decode('utf-8')}")
            if process.stderr:
                logger.warning(f"COLMAP delaunay_mesher stderr: {process.stderr.decode('utf-8')}")
                
            logger.info(f"Mesh generation completed for {image_set_name}")
            
        else:
            # Simple mesh generation using Open3D
            try:
                import open3d as o3d
                
                logger.info(f"Reading point cloud from {fused_ply_path}")
                pcd = o3d.io.read_point_cloud(fused_ply_path)
                
                logger.info(f"Estimating normals")
                pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
                
                logger.info(f"Creating mesh using Poisson reconstruction")
                mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                    pcd, depth=int(MESH_OCTREE_DEPTH), linear_fit=False)
                
                logger.info(f"Removing low density vertices")
                vertices_to_remove = densities < float(MESH_TRIM)
                mesh.remove_vertices_by_mask(vertices_to_remove)
                
                logger.info(f"Saving mesh to {mesh_output_path}")
                o3d.io.write_triangle_mesh(mesh_output_path, mesh)
                
                logger.info(f"Mesh generation completed for {image_set_name}")
                
            except ImportError:
                logger.error("Open3D not available. Please install Open3D or use PoissonRecon/Delaunay meshing.")
                raise AirflowException("Open3D not available for mesh generation")
            except Exception as e:
                logger.error(f"Error during Open3D mesh generation: {str(e)}")
                raise AirflowException(f"Open3D mesh generation failed: {str(e)}")
        
        # Copy the point cloud to the output directory for easier access
        point_cloud_output_path = os.path.join(output_base_dir, 'point_cloud.ply')
        subprocess.run(['cp', fused_ply_path, point_cloud_output_path], check=True)
        
        # Create a metadata file
        metadata_path = os.path.join(output_base_dir, 'metadata.json')
        metadata = {
            'processed_date': datetime.utcnow().isoformat(),
            'image_set': image_set_name,
            'quality_preset': QUALITY_PRESET,
            'frame_count': len(glob.glob(os.path.join(dense_info['image_set_dir'], "*.jpg")) + 
                               glob.glob(os.path.join(dense_info['image_set_dir'], "*.png"))),
            'meshing_tool': MESHING_TOOL
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Create a completion marker
        with open(os.path.join(output_base_dir, 'COMPLETED'), 'w') as f:
            f.write(datetime.utcnow().isoformat())
        
        logger.info(f"Processing for image set {image_set_name} completed")
        logger.info(f"Outputs available at:")
        logger.info(f" - Point cloud: {point_cloud_output_path}")
        logger.info(f" - Mesh: {mesh_output_path}")
        logger.info(f" - Metadata: {metadata_path}")
        
        return {
            'mesh_path': mesh_output_path,
            'point_cloud_path': point_cloud_output_path,
            'metadata_path': metadata_path,
            'image_set_name': image_set_name
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Mesh generation command failed for {image_set_name}: {str(e)}")
        raise AirflowException(f"Mesh generation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during mesh generation for {image_set_name}: {str(e)}")
        raise AirflowException(f"Mesh generation failed: {str(e)}")

# Define the DAG
with DAG(
    dag_id='multi_reconstruction_pipeline',
    description='Process multiple image sets through 3D reconstruction pipeline',
    schedule_interval=None,
    start_date=days_ago(1),
    catchup=False,
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
        'on_failure_callback': task_failure_handler,
    },
    tags=['reconstruction', 'colmap', '3d-model'],
) as dag:
    
    # Task 1: Check if COLMAP dependencies are available
    check_deps_task = PythonOperator(
        task_id='check_dependencies',
        python_callable=check_dependencies,
        dag=dag,
    )
    
    # Task 2: Get list of image sets to process
    get_image_sets_task = PythonOperator(
        task_id='get_image_sets',
        python_callable=get_image_sets,
        dag=dag,
    )
    
    # Task 3: Generate dynamic tasks for each image set
    dynamic_tasks = {}
    
    def generate_tasks(**kwargs):
        """Generate tasks for each image set"""
        ti = kwargs['ti']
        image_sets = ti.xcom_pull(task_ids='get_image_sets')
        
        if not image_sets:
            logger.warning("No image sets found, nothing to process")
            return
        
        for image_set in image_sets:
            # Task to run sparse reconstruction for this image set
            sparse_task_id = f'sparse_reconstruction_{image_set}'
            sparse_task = PythonOperator(
                task_id=sparse_task_id,
                python_callable=run_reconstruction_for_set,
                op_kwargs={'image_set_name': image_set},
                execution_timeout=timedelta(hours=4),
                dag=dag,
            )
            
            # Task to run dense reconstruction for this image set
            dense_task_id = f'dense_reconstruction_{image_set}'
            dense_task = PythonOperator(
                task_id=dense_task_id,
                python_callable=run_dense_reconstruction_for_set,
                op_kwargs={'image_set_name': image_set},
                execution_timeout=timedelta(hours=6),
                dag=dag,
            )
            
            # Task to generate mesh for this image set
            mesh_task_id = f'generate_mesh_{image_set}'
            mesh_task = PythonOperator(
                task_id=mesh_task_id,
                python_callable=generate_mesh_for_set,
                op_kwargs={'image_set_name': image_set},
                execution_timeout=timedelta(hours=2),
                dag=dag,
            )
            
            # Set up task dependencies
            check_deps_task >> get_image_sets_task >> sparse_task >> dense_task >> mesh_task
            
            # Store tasks for future reference
            dynamic_tasks[image_set] = {
                'sparse': sparse_task,
                'dense': dense_task,
                'mesh': mesh_task
            }
        
        logger.info(f"Generated tasks for {len(image_sets)} image sets")
    
    # Task to generate dynamic tasks
    generate_tasks_task = PythonOperator(
        task_id='generate_tasks',
        python_callable=generate_tasks,
        dag=dag,
    )
    
    # Set up the initial task dependencies
    check_deps_task >> get_image_sets_task >> generate_tasks_task 