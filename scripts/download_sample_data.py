#!/usr/bin/env python
"""
Download sample data for testing the reconstruction pipeline.
"""

import os
import sys
import argparse
import urllib.request
import zipfile
import shutil
from pathlib import Path

# Sample datasets available for download
SAMPLE_DATASETS = {
    "CognacStJacquesDoor": {
        "url": "https://github.com/openMVG/ImageDataset_SceauxCastle/raw/master/images/CognacStJacquesDoor.zip",
        "description": "Cognac St Jacques Door - 20 images"
    },
    "fountain": {
        "url": "https://github.com/colmap/colmap/raw/dev/datasets/fountain.zip",
        "description": "Fountain - 11 images"
    }
}

def download_file(url, destination):
    """Download a file from a URL to a destination path."""
    print(f"Downloading {url} to {destination}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    
    # Download with progress indicator
    def report_progress(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\rDownloading: {percent}% [{count * block_size}/{total_size} bytes]")
        sys.stdout.flush()
    
    try:
        urllib.request.urlretrieve(url, destination, reporthook=report_progress)
        print("\nDownload complete!")
        return True
    except Exception as e:
        print(f"\nError downloading file: {e}")
        return False

def extract_zip(zip_path, extract_to):
    """Extract a zip file to a destination directory."""
    print(f"Extracting {zip_path} to {extract_to}")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print("Extraction complete!")
        return True
    except Exception as e:
        print(f"Error extracting zip file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Download sample data for testing")
    parser.add_argument("dataset", choices=list(SAMPLE_DATASETS.keys()), 
                        help="Dataset to download")
    parser.add_argument("output_dir", type=str, 
                        help="Directory to save the dataset")
    parser.add_argument("--keep_zip", action="store_true", 
                        help="Keep the zip file after extraction")
    
    args = parser.parse_args()
    
    # Get dataset info
    dataset_info = SAMPLE_DATASETS[args.dataset]
    url = dataset_info["url"]
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download zip file
    zip_path = output_dir / f"{args.dataset}.zip"
    if not download_file(url, zip_path):
        sys.exit(1)
    
    # Extract zip file
    if not extract_zip(zip_path, output_dir):
        sys.exit(1)
    
    # Clean up zip file if not keeping it
    if not args.keep_zip:
        os.remove(zip_path)
        print(f"Removed zip file: {zip_path}")
    
    print(f"Dataset {args.dataset} successfully downloaded to {output_dir}")

if __name__ == "__main__":
    main() 