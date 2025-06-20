# worker_tasks.py
import os
import subprocess
import shutil
import glob
import logging
from rq import get_current_job
from config import PERSISTENT_STORAGE_DIR, TEMP_DOWNLOAD_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_status(message: str):
    """Updates the job's metadata in Redis."""
    job = get_current_job()
    if job:
        job.meta['status'] = message
        job.save_meta()

def execute_download_task(url: str):
    """The main RQ task for downloading media."""
    job = get_current_job()
    task_id = job.id
    
    logging.info(f"Starting download for task {task_id} (URL: {url})")
    update_status('Downloading...')

    try:
        # Determine tool and run download
        tool = "yt-dlp" # Default to yt-dlp, it's very versatile
        if "instagram.com" in url or "flickr.com" in url:
            tool = "gallery-dl"

        TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # Use the job_id as the base for the temporary filename
        temp_output_template = TEMP_DOWNLOAD_DIR / f"{task_id}.%(ext)s"
        command = [tool, url, '--no-mtime', '-o', str(temp_output_template)]
        
        logging.info(f"Executing: {' '.join(command)}")
        subprocess.run(command, capture_output=True, text=True, check=True)

        # Find the downloaded file
        search_pattern = str(TEMP_DOWNLOAD_DIR / f"{task_id}.*")
        files = [f for f in glob.glob(search_pattern) if not f.endswith('.part')]
        if not files:
            raise FileNotFoundError("Download succeeded but no output file was found.")
        
        temp_filepath = files[0]
        final_filename = os.path.basename(temp_filepath)
        
        # Move file to persistent storage
        PERSISTENT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        persistent_filepath = PERSISTENT_STORAGE_DIR / final_filename
        shutil.move(temp_filepath, persistent_filepath)
        
        logging.info(f"Task {task_id} completed. File: {final_filename}")
        
        # Return the final filename for storage in job.result
        return {'status': 'Completed', 'filename': final_filename}

    except Exception as e:
        logging.error(f"Task {task_id} failed: {e}")
        # When an exception is raised, RQ automatically marks the job as failed
        # and stores the exception info.
        raise # Re-raise the exception to let RQ handle it
    finally:
        # Cleanup all temp files associated with this task
        for item in glob.glob(str(TEMP_DOWNLOAD_DIR / f"{task_id}.*")):
            os.remove(item)