"""
Logging functionality for the Sensor Manager.

This module provides consistent logging with colored output for the terminal.
"""

import logging
import os
import sys
from enum import Enum


class LogColor(Enum):
    """ANSI color codes for terminal output."""
    
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'


class ColoredFormatter(logging.Formatter):
    """Logging formatter that adds colors based on log level."""
    
    COLORS = {
        logging.DEBUG: LogColor.BLUE.value,
        logging.INFO: LogColor.GREEN.value,
        logging.WARNING: LogColor.YELLOW.value,
        logging.ERROR: LogColor.RED.value,
        logging.CRITICAL: f"{LogColor.BOLD.value}{LogColor.RED.value}"
    }
    
    def __init__(self, fmt=None, datefmt=None, colors_enabled=True):
        """Initialize formatter with color support."""
        super().__init__(fmt, datefmt)
        self.colors_enabled = colors_enabled
    
    def format(self, record):
        """Format log record with colors based on level."""
        formatted = super().format(record)
        
        if not self.colors_enabled:
            return formatted
        
        # Add color based on log level
        color = self.COLORS.get(record.levelno, LogColor.RESET.value)
        return f"{color}{formatted}{LogColor.RESET.value}"


def setup_logger(name="sensor_manager", level=logging.INFO, colors_enabled=True):
    """
    Configure and return a logger with the specified name and level.
    
    Args:
        name: Logger name
        level: Logging level (default: INFO)
        colors_enabled: Whether to enable colored output
        
    Returns:
        Configured logger
    """
    # Check if colors should be disabled
    if os.environ.get("NO_COLORS") or not sys.stdout.isatty():
        colors_enabled = False
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        colors_enabled=colors_enabled
    )
    
    # Attach formatter to handler
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


# Create a default logger instance
logger = setup_logger()

# Helper functions for common log levels
def info(msg, *args, **kwargs):
    """Log a message with INFO level."""
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """Log a message with WARNING level."""
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """Log a message with ERROR level."""
    logger.error(msg, *args, **kwargs)

def debug(msg, *args, **kwargs):
    """Log a message with DEBUG level."""
    logger.debug(msg, *args, **kwargs)


# Helper functions with formatting
def success(msg):
    """Log a success message (green INFO)."""
    info(f"✅ {msg}")

def failure(msg):
    """Log a failure message (red ERROR)."""
    error(f"❌ {msg}")

def step(msg):
    """Log a step in a process (blue INFO)."""
    info(f"⏩ {msg}")

def header(msg):
    """Log a header (bold cyan INFO)."""
    if logger.handlers and isinstance(logger.handlers[0].formatter, ColoredFormatter):
        info(f"{LogColor.BOLD.value}{LogColor.CYAN.value}{msg}{LogColor.RESET.value}")
    else:
        info(f"== {msg} ==")