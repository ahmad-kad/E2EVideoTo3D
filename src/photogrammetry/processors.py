def run_meshroom(input_dir, output_dir):
    """Run Meshroom with appropriate hardware acceleration."""
    import os
    
    # Check if GPU is available based on environment variable
    use_gpu = os.environ.get('USE_GPU', '0') == '1'
    meshroom_binary = os.environ.get('MESHROOM_BINARY', 'meshroom_batch_cpu')
    
    if use_gpu:
        print("Running Meshroom with GPU acceleration")
        cmd = f"{meshroom_binary} --input {input_dir} --output {output_dir} --cache ./cache --gpu"
    else:
        print("Running Meshroom with CPU only")
        cmd = f"{meshroom_binary} --input {input_dir} --output {output_dir} --cache ./cache --cpu-only"
    
    # Execute command...
    import subprocess
    result = subprocess.run(cmd, shell=True, check=True)
    return result.returncode == 0 