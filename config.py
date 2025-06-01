import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# --- Redis Configuration ---
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# --- Persistent Storage for Downloads ---
# This path is INSIDE the Docker container.
# Coolify should map a VPS directory to this path.
PERSISTENT_DOWNLOAD_DIR = os.environ.get('PERSISTENT_DOWNLOAD_DIR', os.path.join(BASE_DIR, 'persistent_downloads'))

# --- Temporary Download Directory (inside container) ---
# Used by workers before moving to persistent storage.
TEMP_DOWNLOAD_DIR = os.environ.get('TEMP_DOWNLOAD_DIR', '/tmp/downloader_temp')

# --- Database Configuration ---
# SQLite DB file will be stored in the persistent_downloads directory
# to ensure it persists across container restarts if that directory is a volume.
# Alternatively, place it in another dedicated persistent volume.
DATABASE_DIR = PERSISTENT_DOWNLOAD_DIR # Or another persistent path
SQLITE_DB_FILE = os.path.join(DATABASE_DIR, 'downloads.db')

# Ensure directories exist
if not os.path.exists(PERSISTENT_DOWNLOAD_DIR):
    os.makedirs(PERSISTENT_DOWNLOAD_DIR, exist_ok=True)
if not os.path.exists(TEMP_DOWNLOAD_DIR):
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
if DATABASE_DIR == PERSISTENT_DOWNLOAD_DIR and not os.path.exists(DATABASE_DIR): # Ensure DB dir also exists
     os.makedirs(DATABASE_DIR, exist_ok=True)

# --- Application settings ---
# Base URL for accessing downloaded files if served by a reverse proxy.
# If Flask serves them directly, this might not be needed or set differently.
# Example: "https://yourdomain.com/mediafiles/"
# For now, we'll use Flask's `send_from_directory`.
FILE_SERVE_BASE_URL = "/downloads" # Relative to Flask app
