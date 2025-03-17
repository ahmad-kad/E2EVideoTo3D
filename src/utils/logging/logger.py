"""
Logger Module

This module provides centralized logging functionality with consistent formatting.
"""

import os
import sys
import logging
import datetime
from typing import Optional

# Default log format
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Default log level
DEFAULT_LOG_LEVEL = logging.INFO

# Logger cache to avoid creating multiple loggers for the same name
_loggers = {}


def setup_logging(log_file: Optional[str] = None,
                 log_level: int = DEFAULT_LOG_LEVEL,
                 log_format: str = DEFAULT_LOG_FORMAT) -> None:
    """
    Set up basic logging configuration.
    
    Args:
        log_file: Path to log file (if None, logs to console only)
        log_level: Logging level (default: INFO)
        log_format: Log message format
    """
    handlers = []
    
    # Always add a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # Add a file handler if log_file is specified
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    If a logger with this name already exists, returns the existing logger.
    Otherwise, creates a new logger with appropriate configuration.
    
    Args:
        name: The name of the logger
        
    Returns:
        A configured logger instance
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    
    # Don't propagate to the root logger to avoid duplicate messages
    logger.propagate = False
    
    # Set the log level
    logger.setLevel(DEFAULT_LOG_LEVEL)
    
    # Create a handler if no handlers exist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
        logger.addHandler(handler)
    
    # Store the logger in the cache
    _loggers[name] = logger
    
    return logger


def get_timestamped_log_file(base_dir: str, prefix: str = "reconstruction_run") -> str:
    """
    Generate a timestamped log file path.
    
    Args:
        base_dir: Base directory for log files
        prefix: Prefix for the log file name
        
    Returns:
        A path to a log file with a timestamp
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    return os.path.join(log_dir, f"{prefix}_{timestamp}.log") 