#!/usr/bin/env python3
import os
import socket
import logging
import subprocess
import time
import signal
import atexit
import json
import glob
import uuid
from datetime import datetime
from flask import Flask, jsonify, request, send_file
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('reconstruction_api')

app = Flask(__name__)

# Global job tracking
active_jobs = {}  # job_id -> process_info
job_history = {}  # job_id -> status_info

metrics_pid = None
metrics_process = None

def is_port_in_use(port):
    """Check if the given port is in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(('localhost', port)) == 0
    except Exception as e:
        logger.error(f"Error checking port {port}: {e}")
        return False

def start_metrics_server():
    """Start the Prometheus metrics server as a persistent subprocess."""
    global metrics_pid, metrics_process
    try:
        # Use Popen to keep the process running independently
        metrics_process = subprocess.Popen(
            ['python3', '-c', '''
import os
import time
import threading
from prometheus_client import start_http_server, Counter, Gauge

# Create metrics
RECONSTRUCTION_TOTAL = Counter('reconstruction_total', 'Total number of reconstruction jobs processed')
RECONSTRUCTION_SUCCESS = Counter('reconstruction_success', 'Number of successful reconstruction jobs')
RECONSTRUCTION_FAILURE = Counter('reconstruction_failure', 'Number of failed reconstruction jobs')
ACTIVE_JOBS = Gauge('e2e3d_active_jobs', 'Number of active reconstruction jobs')
JOB_DURATION = Counter('e2e3d_job_duration_seconds', 'Total time spent processing jobs', ['job_id', 'status'])

# Start server
start_http_server(9101)
print("Metrics server started on port 9101")

# Keep the process running
while True:
    time.sleep(60)
'''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        metrics_pid = metrics_process.pid
        logger.info(f"Metrics server started with PID {metrics_pid}")
        
        # Give it a moment to start up
        time.sleep(1)
        
        # Verify it's actually running
        if is_port_in_use(9101):
            return True
        else:
            logger.error("Failed to start metrics server - port not listening")
            return False
    except Exception as e:
        logger.error(f"Error starting metrics server: {e}")
        return False

def cleanup_metrics_server():
    """Cleanup function to terminate the metrics server on exit."""
    global metrics_process
    if metrics_process:
        logger.info(f"Stopping metrics server with PID {metrics_process.pid}")
        try:
            metrics_process.terminate()
            metrics_process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating metrics server: {e}")
            try:
                metrics_process.kill()
            except:
                pass

# Register cleanup function
atexit.register(cleanup_metrics_server)

def update_metric(name, value=1, labels=None):
    """Update a Prometheus metric via API call."""
    try:
        if not metrics_enabled or not is_port_in_use(9101):
            return False
            
        if name == 'active_jobs':
            # Special case for gauge
            script = f'''
import time
from prometheus_client import Gauge
ACTIVE_JOBS = Gauge('e2e3d_active_jobs', 'Number of active reconstruction jobs')
ACTIVE_JOBS.set({value})
'''
        elif name == 'job_duration':
            if not labels or 'job_id' not in labels or 'status' not in labels:
                logger.error("Missing required labels for job_duration metric")
                return False
                
            job_id = labels['job_id']
            status = labels['status']
            script = f'''
from prometheus_client import Counter
JOB_DURATION = Counter('e2e3d_job_duration_seconds', 'Total time spent processing jobs', ['job_id', 'status'])
JOB_DURATION.labels(job_id="{job_id}", status="{status}").inc({value})
'''
        else:
            # Counter metrics
            metric_map = {
                'reconstruction_total': 'RECONSTRUCTION_TOTAL',
                'reconstruction_success': 'RECONSTRUCTION_SUCCESS', 
                'reconstruction_failure': 'RECONSTRUCTION_FAILURE'
            }
            if name not in metric_map:
                logger.error(f"Unknown metric: {name}")
                return False
                
            script = f'''
from prometheus_client import Counter
{metric_map[name]} = Counter('{name}', 'E2E3D metric')
{metric_map[name]}.inc({value})
'''
            
        # Execute the Python code in a separate process
        result = subprocess.run(
            ['python3', '-c', script],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Error updating metric {name}: {result.stderr}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error updating metric {name}: {e}")
        return False

def job_monitor_thread(job_id, process, output_dir):
    """Background thread to monitor a job and update metrics."""
    try:
        # Register the job in active jobs
        start_time = time.time()
        active_jobs[job_id] = {
            'process': process,
            'start_time': start_time,
            'status': 'running',
            'output_dir': output_dir
        }
        
        # Update active jobs metric
        update_metric('active_jobs', len(active_jobs))
        
        # Wait for the process to complete
        return_code = process.wait()
        
        # Update job status based on return code and SUCCESS file
        end_time = time.time()
        duration = end_time - start_time
        
        # Check for SUCCESS or FAILURE files
        success_file = os.path.join(output_dir, 'SUCCESS')
        failure_file = os.path.join(output_dir, 'FAILURE')
        
        if os.path.exists(success_file):
            status = 'completed'
            update_metric('reconstruction_success')
        elif os.path.exists(failure_file):
            status = 'failed'
            update_metric('reconstruction_failure')
        elif return_code == 0:
            status = 'completed'
            update_metric('reconstruction_success')
        else:
            status = 'failed'
            update_metric('reconstruction_failure')
        
        # Update job history
        job_history[job_id] = {
            'status': status,
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'output_dir': output_dir
        }
        
        # Update metrics
        update_metric('reconstruction_total')
        update_metric('job_duration', duration, {'job_id': job_id, 'status': status})
        
        # Remove from active jobs
        if job_id in active_jobs:
            del active_jobs[job_id]
            update_metric('active_jobs', len(active_jobs))
            
        logger.info(f"Job {job_id} completed with status {status} in {duration:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error in job monitor thread for job {job_id}: {e}")
        
        # Update job history with error
        job_history[job_id] = {
            'status': 'error',
            'error': str(e),
            'start_time': active_jobs.get(job_id, {}).get('start_time', time.time()),
            'end_time': time.time(),
            'output_dir': output_dir
        }
        
        # Remove from active jobs
        if job_id in active_jobs:
            del active_jobs[job_id]
            update_metric('active_jobs', len(active_jobs))
            update_metric('reconstruction_failure')

# Initialize metrics if enabled
metrics_enabled = os.environ.get('ENABLE_METRICS', 'false').lower() == 'true'
if metrics_enabled:
    logger.info("Prometheus metrics available")
    
    # Check if port is already in use (metrics server already running)
    if is_port_in_use(9101):
        logger.info("Metrics server already running on port 9101")
    else:
        logger.info("Starting metrics server on port 9101")
        start_metrics_server()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

@app.route('/api/metrics', methods=['GET'])
def metrics_check():
    """Check if metrics server is available."""
    if metrics_enabled:
        if is_port_in_use(9101):
            return jsonify({"status": "available", "port": 9101})
        elif start_metrics_server():
            return jsonify({"status": "available", "port": 9101})
        else:
            return jsonify({"status": "unavailable", "reason": "Failed to start metrics server"})
    else:
        return jsonify({"status": "unavailable", "reason": "Metrics not enabled"})

@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs and their status."""
    try:
        # Combine active jobs and job history
        all_jobs = {}
        
        # Add active jobs
        for job_id, job_info in active_jobs.items():
            all_jobs[job_id] = {
                'status': job_info['status'],
                'start_time': job_info['start_time'],
                'elapsed': time.time() - job_info['start_time'],
                'output_dir': job_info['output_dir']
            }
            
        # Add completed jobs from history
        for job_id, job_info in job_history.items():
            if job_id not in all_jobs:  # Don't overwrite active jobs
                all_jobs[job_id] = {
                    'status': job_info['status'],
                    'start_time': job_info['start_time'],
                    'end_time': job_info.get('end_time'),
                    'duration': job_info.get('duration'),
                    'output_dir': job_info.get('output_dir')
                }
                
                # Add error info if available
                if 'error' in job_info:
                    all_jobs[job_id]['error'] = job_info['error']
        
        return jsonify({"jobs": all_jobs})
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/job/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a specific job."""
    try:
        # Check active jobs first
        if job_id in active_jobs:
            job_info = active_jobs[job_id]
            return jsonify({
                'job_id': job_id,
                'status': job_info['status'],
                'start_time': job_info['start_time'],
                'elapsed': time.time() - job_info['start_time'],
                'output_dir': job_info['output_dir']
            })
            
        # Check job history
        if job_id in job_history:
            job_info = job_history[job_id]
            response = {
                'job_id': job_id,
                'status': job_info['status'],
                'start_time': job_info['start_time']
            }
            
            # Add optional fields if available
            for field in ['end_time', 'duration', 'error', 'output_dir']:
                if field in job_info:
                    response[field] = job_info[field]
                    
            return jsonify(response)
            
        # Check if we can find the job directory
        output_base = "/app/data/output"
        job_dir = os.path.join(output_base, job_id)
        
        if os.path.isdir(job_dir):
            # Find timestamp directories
            timestamp_dirs = glob.glob(os.path.join(job_dir, f"{job_id}_*"))
            
            if timestamp_dirs:
                latest_dir = max(timestamp_dirs)
                success_file = os.path.join(latest_dir, "SUCCESS")
                failure_file = os.path.join(latest_dir, "FAILURE")
                
                if os.path.exists(success_file):
                    with open(success_file, 'r') as f:
                        success_info = f.read().strip()
                    return jsonify({
                        'job_id': job_id,
                        'status': 'completed',
                        'output_dir': latest_dir,
                        'details': success_info
                    })
                elif os.path.exists(failure_file):
                    with open(failure_file, 'r') as f:
                        failure_info = f.read().strip()
                    return jsonify({
                        'job_id': job_id,
                        'status': 'failed',
                        'output_dir': latest_dir,
                        'error': failure_info
                    })
                else:
                    # Job directory exists but no status file
                    return jsonify({
                        'job_id': job_id,
                        'status': 'unknown',
                        'output_dir': latest_dir,
                        'note': 'Job directory exists but status cannot be determined'
                    })
        
        # Job not found
        return jsonify({"error": f"Job {job_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/job/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running job."""
    try:
        if job_id not in active_jobs:
            return jsonify({"error": f"Job {job_id} not found or not running"}), 404
            
        # Get the process
        process = active_jobs[job_id]['process']
        
        # Attempt to terminate gracefully
        process.terminate()
        
        # Wait a moment for graceful termination
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't terminate gracefully
            process.kill()
        
        # Update job history
        job_history[job_id] = {
            'status': 'cancelled',
            'start_time': active_jobs[job_id]['start_time'],
            'end_time': time.time(),
            'duration': time.time() - active_jobs[job_id]['start_time'],
            'output_dir': active_jobs[job_id]['output_dir']
        }
        
        # Remove from active jobs
        del active_jobs[job_id]
        update_metric('active_jobs', len(active_jobs))
        
        return jsonify({"status": "cancelled", "job_id": job_id})
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/job/<job_id>/results', methods=['GET'])
def get_job_results(job_id):
    """Get list of result files for a job."""
    try:
        # Find the job directory
        output_base = "/app/data/output"
        job_dir = os.path.join(output_base, job_id)
        
        if not os.path.isdir(job_dir):
            return jsonify({"error": f"Job directory for {job_id} not found"}), 404
            
        # Find timestamp directories
        timestamp_dirs = glob.glob(os.path.join(job_dir, f"{job_id}_*"))
        
        if not timestamp_dirs:
            return jsonify({"error": f"No results found for job {job_id}"}), 404
            
        latest_dir = max(timestamp_dirs)
        
        # Check if job completed successfully
        success_file = os.path.join(latest_dir, "SUCCESS")
        if not os.path.exists(success_file):
            return jsonify({"error": f"Job {job_id} did not complete successfully"}), 400
            
        # Find all result files
        mesh_files = glob.glob(os.path.join(latest_dir, "mesh", "*"))
        texture_files = glob.glob(os.path.join(latest_dir, "textures", "*"))
        pointcloud_files = glob.glob(os.path.join(latest_dir, "pointcloud", "*"))
        
        # Create file listing with metadata
        files = []
        
        for file_list in [mesh_files, texture_files, pointcloud_files]:
            for filepath in file_list:
                if os.path.isfile(filepath):
                    rel_path = os.path.relpath(filepath, output_base)
                    files.append({
                        "path": rel_path,
                        "type": os.path.splitext(filepath)[1][1:],  # File extension without dot
                        "size": os.path.getsize(filepath),
                        "url": f"/api/file/{rel_path}"
                    })
        
        return jsonify({
            "job_id": job_id,
            "result_dir": os.path.relpath(latest_dir, output_base),
            "files": files
        })
    except Exception as e:
        logger.error(f"Error getting job results: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/file/<path:filepath>', methods=['GET'])
def get_file(filepath):
    """Serve a specific file."""
    try:
        full_path = os.path.join("/app/data/output", filepath)
        
        if not os.path.isfile(full_path):
            return jsonify({"error": f"File {filepath} not found"}), 404
            
        return send_file(full_path)
    except Exception as e:
        logger.error(f"Error serving file {filepath}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/reconstruct', methods=['POST'])
def reconstruct():
    """Endpoint to trigger reconstruction."""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Extract required parameters
        image_set_path = data.get('image_set_path')
        quality = data.get('quality', 'medium')
        job_id = data.get('job_id', f"job_{uuid.uuid4().hex[:8]}")
        
        if not image_set_path:
            return jsonify({"error": "image_set_path is required"}), 400
            
        # Log the request
        logger.info(f"Received reconstruction request: job_id={job_id}, path={image_set_path}, quality={quality}")
        
        # Validate image_set_path exists
        if not os.path.isdir(image_set_path):
            return jsonify({"error": f"Input directory does not exist: {image_set_path}"}), 400
            
        # Start reconstruction process in background
        output_dir = f"/app/data/output/{job_id}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir_with_timestamp = f"{output_dir}/{job_id}_{timestamp}"
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        cmd = [
            "python3", "/app/scripts/reconstruct.py",
            image_set_path,
            "--job-id", job_id,
            "--quality", quality,
            "--output", output_dir_with_timestamp,
            "--verbose"
        ]
        
        # Add optional parameters if provided
        if data.get('use_gpu') is not None:
            cmd.extend(["--use-gpu", str(data['use_gpu']).lower()])
            
        if data.get('upload'):
            cmd.append("--upload")
            
        if data.get('notify_url'):
            cmd.extend(["--notify-url", data['notify_url']])
        
        logger.info(f"Launching reconstruction process with command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Start monitoring thread
        monitor = threading.Thread(
            target=job_monitor_thread,
            args=(job_id, process, output_dir_with_timestamp),
            daemon=True
        )
        monitor.start()
        
        # Update metrics for new job
        update_metric('active_jobs', len(active_jobs))
        
        return jsonify({"status": "submitted", "job_id": job_id})
    except Exception as e:
        logger.error(f"Error processing reconstruction request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 