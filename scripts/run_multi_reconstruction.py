#!/usr/bin/env python3
"""
Run Multi-Reconstruction Pipeline

This script executes the multi-reconstruction pipeline directly for sample datasets.
"""

import os
import sys
import logging
import time
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("run_multi_reconstruction")

# Define paths
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INPUT_PATH = os.path.join(PROJECT_PATH, 'data', 'input')
OUTPUT_PATH = os.path.join(PROJECT_PATH, 'data', 'output')
QUALITY_PRESET = 'medium'  # 'low', 'medium', 'high'

def check_docker_status():
    """Check if Docker is available and running."""
    try:
        subprocess.run(['docker', 'info'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("Docker is available and running")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("Docker is not available or not running")
        raise Exception("Docker is required but not available")

def find_image_sets():
    """Find all image sets in the input directory."""
    image_sets = []
    
    # Look for directories in the input path
    for item in os.listdir(INPUT_PATH):
        item_path = os.path.join(INPUT_PATH, item)
        
        # Check if this is a directory with image files
        if os.path.isdir(item_path):
            if item in ['CognacStJacquesDoor', 'FrameSequence']:
                logger.info(f"Found image set: {item}")
                image_sets.append(item)
    
    if not image_sets:
        logger.warning("No sample image sets found in the input directory")
        raise Exception("No sample image sets found")
    
    logger.info(f"Found {len(image_sets)} image sets: {', '.join(image_sets)}")
    return image_sets

def run_reconstruction(image_set):
    """Run the reconstruction process for a specific image set using Docker."""
    try:
        logger.info(f"Starting reconstruction for image set: {image_set}")
        
        # Define paths
        input_dir = os.path.join(INPUT_PATH, image_set)
        output_dir = os.path.join(OUTPUT_PATH, 'models', image_set)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare Docker run command
        docker_cmd = [
            'docker', 'run', '--rm',
            '-v', f"{INPUT_PATH}:/app/data/input",
            '-v', f"{OUTPUT_PATH}:/app/data/output",
            '-e', f"QUALITY_PRESET={QUALITY_PRESET}",
            'e2e3d-reconstruction',
            f"/app/data/input/{image_set}",
            '--output', f"/app/data/output/models/{image_set}",
            '--quality', QUALITY_PRESET,
            '--verbose'
        ]
        
        # Run the Docker command
        logger.info(f"Running command: {' '.join(docker_cmd)}")
        start_time = time.time()
        
        process = subprocess.Popen(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        # Track stdout and stderr
        stdout_lines = []
        stderr_lines = []
        
        # Monitor the process
        while process.poll() is None:
            stdout_line = process.stdout.readline()
            if stdout_line:
                logger.info(f"[{image_set}] {stdout_line.strip()}")
                stdout_lines.append(stdout_line)
            
            stderr_line = process.stderr.readline()
            if stderr_line:
                logger.warning(f"[{image_set}] ERROR: {stderr_line.strip()}")
                stderr_lines.append(stderr_line)
            
            time.sleep(0.1)
        
        # Get any remaining output
        stdout_lines.extend(process.stdout.readlines())
        stderr_lines.extend(process.stderr.readlines())
        
        # Check the exit code
        if process.returncode != 0:
            error_msg = f"Reconstruction failed for {image_set} with exit code {process.returncode}"
            if stderr_lines:
                error_msg += f"\nError details: {''.join(stderr_lines)}"
            logger.error(error_msg)
            
            # Write error details to a file in the output directory
            with open(os.path.join(output_dir, 'reconstruction_error.log'), 'w') as f:
                f.write(f"Error running reconstruction:\n")
                f.write(f"Exit code: {process.returncode}\n\n")
                f.write(f"STDERR:\n{''.join(stderr_lines)}\n\n")
                f.write(f"STDOUT:\n{''.join(stdout_lines)}\n")
            
            return {
                'status': 'failed',
                'image_set': image_set,
                'exit_code': process.returncode,
                'duration': time.time() - start_time
            }
        
        # Check if expected outputs exist
        mesh_file = os.path.join(output_dir, 'mesh', 'reconstructed_mesh.obj')
        
        if not os.path.exists(mesh_file):
            logger.warning(f"No mesh found for {image_set}")
            
            # Create a JSON report about what happened
            with open(os.path.join(output_dir, 'reconstruction_results.json'), 'w') as f:
                json.dump({
                    'status': 'warning',
                    'image_set': image_set,
                    'message': 'No mesh generated',
                    'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'duration': time.time() - start_time,
                }, f, indent=2)
            
            return {
                'status': 'warning',
                'image_set': image_set,
                'message': 'No mesh generated',
                'duration': time.time() - start_time
            }
        
        # Successful completion
        logger.info(f"Reconstruction completed successfully for {image_set} in {time.time() - start_time:.2f} seconds")
        
        # Create a success report
        with open(os.path.join(output_dir, 'reconstruction_results.json'), 'w') as f:
            json.dump({
                'status': 'success',
                'image_set': image_set,
                'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'duration': time.time() - start_time,
                'mesh_file': os.path.relpath(mesh_file, output_dir),
                'quality_preset': QUALITY_PRESET
            }, f, indent=2)
        
        return {
            'status': 'success',
            'image_set': image_set,
            'duration': time.time() - start_time
        }
    
    except Exception as e:
        logger.error(f"Error processing image set {image_set}: {str(e)}")
        
        # Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Write error to a file
        with open(os.path.join(output_dir, 'reconstruction_error.log'), 'w') as f:
            f.write(f"Error: {str(e)}\n")
        
        return {
            'status': 'error',
            'image_set': image_set,
            'error': str(e)
        }

def generate_summary_report(results):
    """Generate a summary report of all reconstructions."""
    # Count successes, warnings, and failures
    successes = sum(1 for r in results.values() if r and r.get('status') == 'success')
    warnings = sum(1 for r in results.values() if r and r.get('status') == 'warning')
    failures = sum(1 for r in results.values() if r and (r.get('status') == 'failed' or r.get('status') == 'error'))
    
    # Create the summary report
    summary = {
        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'image_sets_processed': len(results),
        'successes': successes,
        'warnings': warnings,
        'failures': failures,
        'details': list(results.values())
    }
    
    # Write the summary to a file
    summary_file = os.path.join(OUTPUT_PATH, 'reconstruction_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Summary report generated at {summary_file}")
    logger.info(f"Processed {len(results)} image sets: {successes} successes, {warnings} warnings, {failures} failures")
    
    return summary

def main():
    """Run the multi-reconstruction pipeline directly."""
    logger.info("Starting multi-reconstruction pipeline")
    
    # Step 1: Check Docker status
    logger.info("Checking Docker status")
    try:
        check_docker_status()
    except Exception as e:
        logger.error(f"Docker check failed: {str(e)}")
        return 1
    
    # Step 2: Find image sets
    logger.info("Finding image sets")
    try:
        image_sets = find_image_sets()
    except Exception as e:
        logger.error(f"Finding image sets failed: {str(e)}")
        return 1
    
    # Step 3: Process each image set
    results = {}
    
    for image_set in image_sets:
        logger.info(f"Processing image set: {image_set}")
        try:
            result = run_reconstruction(image_set)
            results[image_set] = result
            logger.info(f"Completed processing {image_set} with status: {result.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"Error processing {image_set}: {str(e)}")
            results[image_set] = {
                'status': 'error',
                'image_set': image_set,
                'error': str(e)
            }
    
    # Step 4: Generate summary report
    logger.info("Generating summary report")
    try:
        summary = generate_summary_report(results)
        logger.info(f"Summary: {summary}")
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
    
    logger.info("Multi-reconstruction pipeline completed")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 