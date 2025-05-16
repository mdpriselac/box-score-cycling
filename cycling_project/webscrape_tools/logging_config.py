import os
import logging
from datetime import datetime
from pathlib import Path
import sys

# Base directory for logs
LOG_DIR = Path(__file__).parent / "webscrape_logs"

# Ensure log directory exists
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

# Formatter constants
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Log levels
DEFAULT_LEVEL = logging.INFO


def get_logger(module_name: str) -> logging.Logger:
    """
    Configure and return a logger for the given module.
    
    Args:
        module_name: The name of the module requesting the logger
        
    Returns:
        A configured logger instance
    """
    # Generate date-based filename
    today = datetime.now().strftime('%Y%m%d')
    log_file = LOG_DIR / f"{today}_{module_name}.log"
    
    # Create logger
    logger = logging.getLogger(module_name)
    logger.setLevel(DEFAULT_LEVEL)
    
    # Clear any existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Create handlers
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(DEFAULT_LEVEL)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(DEFAULT_LEVEL)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger