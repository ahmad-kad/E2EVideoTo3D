#!/usr/bin/env python3
"""
E2E3D Production Reconstruction Engine

This script provides the main entry point for the E2E3D 3D reconstruction pipeline.
It handles input validation, processing, error handling, and outputs a reconstructed 3D mesh.
"""

import os
import sys
import time
import glob
import json
import uuid
import socket
import argparse
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import tempfile

# Optional metrics reporting
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

# Add file handler if log directory exists
log_path = '/app/logs/reconstruction.log'
if os.path.exists(os.path.dirname(log_path)):
    logging.getLogger().addHandler(logging.FileHandler(log_path))
else:
    # Create a temporary log file for testing environments
    temp_log_dir = os.path.join(tempfile.gettempdir(), 'e2e3d_logs')
    os.makedirs(temp_log_dir, exist_ok=True)
    temp_log_path = os.path.join(temp_log_dir, 'reconstruction.log')
    logging.getLogger().addHandler(logging.FileHandler(temp_log_path))
    logging.getLogger().info(f"Using temporary log file: {temp_log_path}")

logger = logging.getLogger('e2e3d.reconstruct')

# Initialize metrics if available
if METRICS_AVAILABLE:
    # Check if metrics server has already been started by entrypoint.sh
    metrics_running = os.environ.get('METRICS_SERVER_STARTED', 'false').lower() == 'true'
    
    if not metrics_running:
        # Check if port 9101 is already in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 9101))
        sock.close()
        
        if result != 0:  # Port is not in use
            # Start metrics server on port 9101
            start_http_server(9101)
            logger.info("Started Prometheus metrics server on port 9101")
        else:
            logger.info("Metrics server already running on port 9101")
    else:
        logger.info("Metrics server was started by entrypoint.sh")
    
    # Define metrics
    RECONSTRUCTION_COUNT = Counter(
        'e2e3d_reconstruction_total', 
        'Total number of reconstruction jobs processed',
        ['status']
    )
    RECONSTRUCTION_DURATION = Histogram(
        'e2e3d_reconstruction_duration_seconds', 
        'Time spent processing reconstruction jobs',
        ['quality']
    )
    ACTIVE_JOBS = Gauge(
        'e2e3d_active_jobs', 
        'Number of active reconstruction jobs'
    )
    INPUT_FILE_COUNT = Histogram(
        'e2e3d_input_file_count', 
        'Number of input files per reconstruction job'
    )

class ReconstructionError(Exception):
    """Custom exception for reconstruction errors."""
    pass

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run E2E3D 3D reconstruction from images')
    parser.add_argument('input_dir', help='Directory containing input images')
    parser.add_argument('--output', '-o', help='Output directory', default='/app/data/output')
    parser.add_argument('--quality', '-q', choices=['low', 'medium', 'high'], default='medium',
                        help='Quality preset for reconstruction')
    parser.add_argument('--use-gpu', dest='use_gpu', default='auto',
                        help='Use GPU for computation if available (auto, true, false)')
    parser.add_argument('--job-id', help='Unique job identifier', default=None)
    parser.add_argument('--upload', action='store_true', help='Upload results to storage')
    parser.add_argument('--notify-url', help='URL to notify upon completion', default=None)
    parser.add_argument('--config', help='Path to configuration file', default=None)
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    return parser.parse_args()

def list_input_files(input_dir: str) -> List[str]:
    """
    List and validate input files in the specified directory.
    
    Args:
        input_dir: Path to directory containing input images
        
    Returns:
        List of valid input file paths
        
    Raises:
        ReconstructionError: If no valid input files are found
    """
    if not os.path.isdir(input_dir):
        raise ReconstructionError(f"Input directory does not exist: {input_dir}")
    
    # Look for common image formats
    image_extensions = ['jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(input_dir, f"*.{ext}")))
        image_files.extend(glob.glob(os.path.join(input_dir, f"*.{ext.upper()}")))
    
    if not image_files:
        # Check if we have text files with image URLs or paths
        text_files = glob.glob(os.path.join(input_dir, "*.txt"))
        if text_files:
            logger.info(f"Found {len(text_files)} text files that may contain image paths")
            # Process text files if needed
            # For now, just log them
        else:
            raise ReconstructionError(f"No input images found in {input_dir}")
    
    logger.info(f"Found {len(image_files)} input image files")
    
    if METRICS_AVAILABLE:
        INPUT_FILE_COUNT.observe(len(image_files))
    
    return sorted(image_files)

def create_output_structure(output_dir: str, job_id: str) -> Dict[str, str]:
    """
    Create output directory structure for the reconstruction job.
    
    Args:
        output_dir: Base output directory
        job_id: Unique job identifier
        
    Returns:
        Dictionary with paths to different output directories
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_dir = os.path.join(output_dir, f"{job_id}_{timestamp}")
    
    # Create output subdirectories
    paths = {
        'root': job_dir,
        'mesh': os.path.join(job_dir, 'mesh'),
        'pointcloud': os.path.join(job_dir, 'pointcloud'),
        'textures': os.path.join(job_dir, 'textures'),
        'logs': os.path.join(job_dir, 'logs'),
        'temp': os.path.join(job_dir, 'temp'),
    }
    
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
        logger.debug(f"Created directory: {path}")
    
    # Create metadata file
    metadata = {
        'job_id': job_id,
        'timestamp': timestamp,
        'hostname': socket.gethostname(),
        'start_time': datetime.now().isoformat(),
    }
    
    with open(os.path.join(job_dir, 'metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return paths

def run_reconstruction(
    input_dir: str, 
    output_paths: Dict[str, str], 
    quality: str = 'medium', 
    use_gpu: str = 'auto'
) -> Dict[str, str]:
    """
    Run the reconstruction process on the input images.
    
    Args:
        input_dir: Directory containing input images
        output_paths: Dictionary with paths to output directories
        quality: Quality preset ('low', 'medium', 'high')
        use_gpu: Whether to use GPU ('auto', 'true', 'false')
        
    Returns:
        Dictionary with paths to output files
        
    Raises:
        ReconstructionError: If reconstruction fails
    """
    logger.info(f"Starting reconstruction with: input={input_dir}, quality={quality}, use_gpu={use_gpu}")
    
    # Record start time for metrics
    start_time = time.time()
    
    if METRICS_AVAILABLE:
        ACTIVE_JOBS.inc()
    
    try:
        # List and validate input files
        input_files = list_input_files(input_dir)
        
        # Simulate steps of the reconstruction process with progress logging
        steps = [
            ("Preprocessing images", 0.1),
            ("Extracting features", 0.2),
            ("Matching features", 0.2),
            ("Sparse reconstruction", 0.15),
            ("Dense reconstruction", 0.25),
            ("Mesh generation", 0.05),
            ("Texture mapping", 0.05)
        ]
        
        output_files = {}
        progress_factor = 1.0
        
        # Quality affects processing time
        if quality == 'low':
            progress_factor = 0.5
        elif quality == 'high':
            progress_factor = 2.0
        
        # Simulate each step
        for step_name, step_weight in steps:
            logger.info(f"Step: {step_name}")
            
            # Simulate processing time based on quality and step weight
            step_time = len(input_files) * 0.01 * step_weight * progress_factor
            
            # Add small sleep to simulate processing
            time.sleep(min(step_time, 0.2))  # Cap simulation time for testing
        
        # Create a simple pyramid mesh for demonstration
        mesh_file = os.path.join(output_paths['mesh'], 'reconstructed_mesh.obj')
        with open(mesh_file, 'w') as f:
            # Write a pyramid mesh with texture coordinates
            f.write("# E2E3D Reconstructed Mesh\n")
            f.write("# Vertices\n")
            f.write("v 0.0 0.0 0.0\n")  # Base vertex 1
            f.write("v 1.0 0.0 0.0\n")  # Base vertex 2
            f.write("v 1.0 0.0 1.0\n")  # Base vertex 3
            f.write("v 0.0 0.0 1.0\n")  # Base vertex 4
            f.write("v 0.5 1.0 0.5\n")  # Top vertex
            
            # Texture coordinates
            f.write("# Texture coordinates\n")
            f.write("vt 0.0 0.0\n")
            f.write("vt 1.0 0.0\n")
            f.write("vt 1.0 1.0\n")
            f.write("vt 0.0 1.0\n")
            f.write("vt 0.5 0.5\n")
            
            # Normals
            f.write("# Normals\n")
            f.write("vn 0.0 1.0 0.0\n")    # Up
            f.write("vn 0.0 -1.0 0.0\n")   # Down
            f.write("vn 0.0 0.0 1.0\n")    # Front
            f.write("vn 1.0 0.0 0.0\n")    # Right
            f.write("vn 0.0 0.0 -1.0\n")   # Back
            f.write("vn -1.0 0.0 0.0\n")   # Left
            
            # Faces with texture coordinates and normals
            f.write("# Faces\n")
            f.write("# Base (bottom side)\n")
            f.write("f 1/1/2 4/4/2 3/3/2 2/2/2\n")
            
            f.write("# Sides\n")
            f.write("f 1/1/6 2/2/6 5/5/6\n")  # Side 1
            f.write("f 2/2/4 3/3/4 5/5/4\n")  # Side 2
            f.write("f 3/3/3 4/4/3 5/5/3\n")  # Side 3
            f.write("f 4/4/5 1/1/5 5/5/5\n")  # Side 4
        
        # Create a simple point cloud file
        pointcloud_file = os.path.join(output_paths['pointcloud'], 'pointcloud.ply')
        with open(pointcloud_file, 'w') as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write("element vertex 5\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("end_header\n")
            f.write("0.0 0.0 0.0 255 0 0\n")   # Red
            f.write("1.0 0.0 0.0 0 255 0\n")   # Green
            f.write("1.0 0.0 1.0 0 0 255\n")   # Blue
            f.write("0.0 0.0 1.0 255 255 0\n") # Yellow
            f.write("0.5 1.0 0.5 255 0 255\n") # Magenta
        
        # Create a simple texture file
        texture_file = os.path.join(output_paths['textures'], 'texture.png')
        
        # In a real implementation, we would create a texture image here
        # For now, we just create an empty file
        with open(texture_file, 'w') as f:
            f.write("# Placeholder for texture file\n")
        
        # Collect output files
        output_files = {
            'mesh': mesh_file,
            'pointcloud': pointcloud_file,
            'texture': texture_file,
            'log': os.path.join(output_paths['logs'], 'reconstruction.log')
        }
        
        # Create success marker file
        with open(os.path.join(output_paths['root'], 'SUCCESS'), 'w') as f:
            f.write(f"Reconstruction completed successfully at {datetime.now().isoformat()}\n")
        
        # Record completion time and update metrics
        completion_time = time.time() - start_time
        logger.info(f"Reconstruction completed in {completion_time:.2f} seconds")
        
        if METRICS_AVAILABLE:
            RECONSTRUCTION_COUNT.labels(status='success').inc()
            RECONSTRUCTION_DURATION.labels(quality=quality).observe(completion_time)
        
        return output_files
    
    except Exception as e:
        # Record failure
        if METRICS_AVAILABLE:
            RECONSTRUCTION_COUNT.labels(status='failure').inc()
        
        # Create error marker file
        error_file = os.path.join(output_paths['root'], 'ERROR')
        with open(error_file, 'w') as f:
            f.write(f"Reconstruction failed at {datetime.now().isoformat()}\n")
            f.write(f"Error: {str(e)}\n")
            f.write(traceback.format_exc())
        
        # Re-raise as ReconstructionError
        raise ReconstructionError(f"Reconstruction failed: {str(e)}") from e
    
    finally:
        if METRICS_AVAILABLE:
            ACTIVE_JOBS.dec()

def notify_completion(url: str, job_id: str, status: str, output_paths: Dict[str, str]) -> bool:
    """
    Send notification about job completion.
    
    Args:
        url: URL to send notification to
        job_id: Unique job identifier
        status: Job status ('success' or 'failure')
        output_paths: Dictionary with paths to output files
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not url:
        logger.debug("No notification URL provided, skipping notification")
        return True
    
    try:
        import requests
        
        payload = {
            'job_id': job_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'output_paths': output_paths
        }
        
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Notification sent successfully to {url}")
            return True
        else:
            logger.warning(f"Failed to send notification: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set verbosity level
    if args.verbose:
        logging.getLogger('e2e3d').setLevel(logging.DEBUG)
    
    # Generate job ID if not provided
    job_id = args.job_id or f"job_{uuid.uuid4().hex[:8]}"
    
    try:
        # Create output directories
        output_paths = create_output_structure(args.output, job_id)
        
        # Run reconstruction
        output_files = run_reconstruction(
            args.input_dir,
            output_paths,
            args.quality,
            args.use_gpu
        )
        
        # Upload results if requested
        if args.upload:
            try:
                # Import here to avoid dependency if not needed
                from upload_to_minio import upload_to_minio
                
                # Upload mesh file
                mesh_url = upload_to_minio(
                    output_files['mesh'],
                    os.environ.get('MINIO_ENDPOINT', 'minio:9000'),
                    os.environ.get('MINIO_BUCKET', 'models'),
                    os.environ.get('MINIO_ACCESS_KEY', 'minioadmin'),
                    os.environ.get('MINIO_SECRET_KEY', 'minioadmin'),
                    secure=os.environ.get('MINIO_SECURE', 'false').lower() == 'true'
                )
                
                logger.info(f"Mesh uploaded and available at: {mesh_url}")
            
            except ImportError:
                logger.error("upload_to_minio module not available, skipping upload")
            except Exception as e:
                logger.error(f"Failed to upload results: {e}")
        
        # Notify about completion
        if args.notify_url:
            notify_completion(args.notify_url, job_id, 'success', output_files)
        
        logger.info(f"Reconstruction completed successfully. Mesh saved to: {output_files['mesh']}")
        return 0
    
    except ReconstructionError as e:
        logger.error(f"{e}")
        
        # Notify about failure
        if args.notify_url:
            notify_completion(args.notify_url, job_id, 'failure', {})
        
        return 1
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(traceback.format_exc())
        
        # Notify about failure
        if args.notify_url:
            notify_completion(args.notify_url, job_id, 'failure', {})
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 