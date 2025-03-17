"""
Settings Module

This module provides functions to access configuration settings from environment
variables, with reasonable defaults.
"""

import os
import json
from typing import Dict, Any, Optional

# Default configuration values
DEFAULT_CONFIG = {
    "project_path": os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')),
    "colmap_path": "colmap",
    "quality_preset": "medium",
    "use_gpu": "auto",
    "s3_enabled": False,
    "s3_endpoint": "http://localhost:9000",
    "s3_bucket": "models",
    "s3_access_key": "minioadmin",
    "s3_secret_key": "minioadmin",
    "s3_region": "us-east-1"
}

# Quality presets with their corresponding parameter values
QUALITY_PRESETS = {
    "low": {
        "colmap_image_size": 1000,
        "voxel_size": 0.05,
        "normal_k": 30,
        "depth": 8,
        "mesh_method": "open3d"
    },
    "medium": {
        "colmap_image_size": 2000,
        "voxel_size": 0.02,
        "normal_k": 50,
        "depth": 9,
        "mesh_method": "poisson"
    },
    "high": {
        "colmap_image_size": 3000,
        "voxel_size": 0.01,
        "normal_k": 100,
        "depth": 10,
        "mesh_method": "poisson"
    }
}


def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get a configuration value from the environment or default config.
    
    Args:
        key: The configuration key to look up (will be uppercased for env vars)
        default: Optional default value if not found
        
    Returns:
        The configuration value
    """
    env_key = key.upper()
    env_value = os.environ.get(env_key)
    
    if env_value is not None:
        return env_value
    
    return DEFAULT_CONFIG.get(key, default)


def get_project_path() -> str:
    """Get the project root directory path."""
    return get_config_value("project_path")


def get_input_path() -> str:
    """Get the input directory path."""
    return os.path.join(get_project_path(), "data", "input")


def get_output_path() -> str:
    """Get the output directory path."""
    return os.path.join(get_project_path(), "data", "output")


def get_colmap_path() -> str:
    """Get the path to the COLMAP executable."""
    return get_config_value("colmap_path")


def get_quality_preset(preset_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the parameters for a quality preset.
    
    Args:
        preset_name: The name of the preset (low, medium, high)
                    If None, uses the value from config
    
    Returns:
        A dictionary of quality parameters
    """
    if preset_name is None:
        preset_name = get_config_value("quality_preset")
    
    # Default to medium if the preset is not found
    if preset_name not in QUALITY_PRESETS:
        preset_name = "medium"
    
    return QUALITY_PRESETS[preset_name] 