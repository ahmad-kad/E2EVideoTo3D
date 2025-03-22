#!/usr/bin/env python3
import os
import socket
import logging
import subprocess
import time
import signal
import atexit
from flask import Flask, jsonify, request
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('reconstruction_api')

app = Flask(__name__)

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
from prometheus_client import start_http_server, Counter

# Create metric
RECONSTRUCTION_COUNT = Counter('reconstruction_total', 'Total number of reconstruction jobs processed')

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

@app.route('/api/reconstruct', methods=['POST'])
def reconstruct():
    """Endpoint to trigger reconstruction."""
    # This would typically validate the request and queue a job
    return jsonify({"status": "submitted", "job_id": "sample_job_123"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) 