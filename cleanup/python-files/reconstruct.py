#!/usr/bin/env python3
"""
Reconstruction Entry Point

This script is the main entry point for running the 3D reconstruction pipeline.
It simply forwards to the CLI module.
"""

import os
import sys

# Add the parent directory to the path so we can import the package
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.reconstruction.cli import main

if __name__ == "__main__":
    sys.exit(main()) 