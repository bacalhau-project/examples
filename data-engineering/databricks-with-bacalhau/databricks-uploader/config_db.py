#!/usr/bin/env python3
"""Shared configuration database utilities."""

import os
from pathlib import Path


def get_config_db_path(state_dir: str = None) -> str:
    """
    Get the path for the shared configuration database.
    
    Args:
        state_dir: Directory for state files. Defaults to 'state' in current directory.
        
    Returns:
        Path to the configuration database.
    """
    if state_dir is None:
        state_dir = os.environ.get('UPLOADER_STATE_DIR', 'state')
    
    # Create state directory if it doesn't exist
    state_path = Path(state_dir)
    state_path.mkdir(parents=True, exist_ok=True)
    
    # Configuration database is in the state directory
    config_db = state_path / 'uploader_config.db'
    
    return str(config_db)