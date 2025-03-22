#!/usr/bin/env python3
"""
E2E3D Container Healthcheck

This script is used by Docker to check if the service is healthy.
It performs various checks to ensure the service is ready to process jobs.
"""

import os
import sys
import socket
import logging
import traceback
import importlib
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('e2e3d.healthcheck')

def check_filesystem_access():
    """Check if filesystem is accessible and writeable."""
    try:
        # Check data directories
        data_dirs = [
            '/app/data/input',
            '/app/data/output',
            '/app/logs'
        ]
        
        for directory in data_dirs:
            if not os.path.isdir(directory):
                logger.error(f"Directory does not exist: {directory}")
                return False
            
            # Try to write a test file
            test_file = os.path.join(directory, '.healthcheck')
            try:
                with open(test_file, 'w') as f:
                    f.write('healthcheck')
                os.remove(test_file)
            except Exception as e:
                logger.error(f"Failed to write to directory {directory}: {e}")
                return False
        
        return True
    
    except Exception as e:
        logger.error(f"Filesystem check failed: {e}")
        return False

def check_python_imports():
    """Check if required Python packages are available."""
    required_packages = [
        'numpy',
        'PIL',
        'minio',
        'requests'
    ]
    
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            logger.error(f"Required package not available: {package}")
            return False
    
    return True

def check_external_connectivity():
    """Check if external services are reachable."""
    # Check if MinIO is reachable
    minio_host = os.environ.get('MINIO_ENDPOINT', 'minio:9000')
    if ':' in minio_host:
        minio_host, minio_port = minio_host.split(':', 1)
        minio_port = int(minio_port)
    else:
        minio_port = 9000
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((minio_host, minio_port))
        logger.debug(f"Connection to MinIO at {minio_host}:{minio_port} successful")
    except Exception as e:
        logger.error(f"Failed to connect to MinIO at {minio_host}:{minio_port}: {e}")
        return False
    
    return True

def check_system_resources():
    """Check if system has sufficient resources."""
    try:
        # Check available disk space
        df_process = subprocess.run(
            ['df', '-h', '/app'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if df_process.returncode != 0:
            logger.error(f"Failed to check disk space: {df_process.stderr}")
            return False
        
        # Parse df output
        df_lines = df_process.stdout.strip().split('\n')
        if len(df_lines) < 2:
            logger.error(f"Unexpected df output: {df_process.stdout}")
            return False
        
        # Get available disk space percentage
        df_parts = df_lines[1].split()
        if len(df_parts) < 5:
            logger.error(f"Unexpected df line format: {df_lines[1]}")
            return False
        
        use_percent = df_parts[4].rstrip('%')
        try:
            use_percent = int(use_percent)
            if use_percent > 90:
                logger.error(f"Disk usage too high: {use_percent}%")
                return False
        except ValueError:
            logger.error(f"Failed to parse disk usage percentage: {df_parts[4]}")
            return False
        
        # Check memory - skip if free command isn't available 
        try:
            mem_process = subprocess.run(
                ['free', '-m'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if mem_process.returncode != 0:
                logger.warning(f"Failed to check memory: {mem_process.stderr}")
                # Don't fail the health check if free isn't available
        except FileNotFoundError:
            logger.warning("The 'free' command is not available in this container, skipping memory check")
        
        return True
    
    except Exception as e:
        logger.error(f"System resource check failed: {e}")
        return False

def main():
    """Run all healthchecks and return appropriate exit code."""
    try:
        checks = [
            ("Filesystem Access", check_filesystem_access),
            ("Python Imports", check_python_imports),
            ("External Connectivity", check_external_connectivity),
            ("System Resources", check_system_resources)
        ]
        
        success = True
        for name, check_func in checks:
            logger.debug(f"Running healthcheck: {name}")
            result = check_func()
            if not result:
                logger.error(f"Healthcheck failed: {name}")
                success = False
            else:
                logger.debug(f"Healthcheck passed: {name}")
        
        if success:
            logger.debug("All healthchecks passed")
            return 0
        else:
            logger.error("One or more healthchecks failed")
            return 1
    
    except Exception as e:
        logger.error(f"Unexpected error in healthcheck: {e}")
        logger.debug(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 