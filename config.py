# config.py
import os
from pathlib import Path

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent

# --- Redis Configuration ---
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# --- Storage Configuration ---
# These paths are INSIDE the Docker container.
PERSISTENT_STORAGE_DIR = Path(os.environ.get('PERSISTENT_STORAGE_DIR', BASE_DIR / 'persistent_storage'))
TEMP_DOWNLOAD_DIR = Path(os.environ.get('TEMP_DOWNLOAD_DIR', '/tmp/downloader_temp'))

# --- Application Settings ---
FILE_SERVE_BASE_URL = "/downloads"