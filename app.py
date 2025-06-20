#!/usr/bin/env python3
"""
Media Downloader Web App
A simple Flask application for downloading media from various platforms.
"""

import os
import uuid
import threading
import subprocess
import shutil
import glob
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
TEMP_DIR = BASE_DIR / "temp"

# Ensure directories exist
DOWNLOADS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

class JobStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class DownloadJob:
    id: str
    url: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    filename: Optional[str] = None
    error_message: Optional[str] = None
    progress: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

class DownloadManager:
    def __init__(self):
        self.jobs: Dict[str, DownloadJob] = {}
        self.lock = threading.Lock()

    def create_job(self, url: str) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now()
        
        job = DownloadJob(
            id=job_id,
            url=url,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now
        )
        
        with self.lock:
            self.jobs[job_id] = job
        
        # Start download in background thread
        thread = threading.Thread(target=self._download_worker, args=(job_id,))
        thread.daemon = True
        thread.start()
        
        return job_id

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        with self.lock:
            return self.jobs.get(job_id)

    def get_all_jobs(self) -> list[DownloadJob]:
        with self.lock:
            return sorted(self.jobs.values(), key=lambda x: x.created_at, reverse=True)

    def _update_job(self, job_id: str, **kwargs):
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                for key, value in kwargs.items():
                    setattr(job, key, value)
                job.updated_at = datetime.now()

    def _download_worker(self, job_id: str):
        """Background worker to handle the actual download"""
        try:
            job = self.get_job(job_id)
            if not job:
                return

            logger.info(f"Starting download for job {job_id}: {job.url}")
            self._update_job(job_id, status=JobStatus.DOWNLOADING, progress=10)

            # Determine the appropriate tool
            tool = self._get_download_tool(job.url)
            
            # Create temp directory for this job
            temp_job_dir = TEMP_DIR / job_id
            temp_job_dir.mkdir(exist_ok=True)

            try:
                # Build command
                output_template = str(temp_job_dir / "%(title)s.%(ext)s")
                command = [
                    tool,
                    job.url,
                    "--no-mtime",
                    "--output", output_template,
                    "--no-playlist"  # Download single video only
                ]

                logger.info(f"Executing: {' '.join(command)}")
                self._update_job(job_id, progress=30)

                # Run the download command
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=1800,  # 30 minute timeout
                    cwd=temp_job_dir
                )

                if result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode, command, result.stdout, result.stderr
                    )

                self._update_job(job_id, progress=80)

                # Find the downloaded file
                downloaded_files = list(temp_job_dir.glob("*"))
                downloaded_files = [f for f in downloaded_files if f.is_file()]
                
                if not downloaded_files:
                    raise FileNotFoundError("No files were downloaded")

                # Move the file to the downloads directory
                source_file = downloaded_files[0]  # Take the first file
                filename = f"{job_id}_{source_file.name}"
                destination = DOWNLOADS_DIR / filename

                shutil.move(str(source_file), str(destination))
                
                logger.info(f"Download completed for job {job_id}: {filename}")
                self._update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    filename=filename,
                    progress=100
                )

            finally:
                # Clean up temp directory
                if temp_job_dir.exists():
                    shutil.rmtree(temp_job_dir, ignore_errors=True)

        except subprocess.TimeoutExpired:
            error_msg = "Download timed out after 30 minutes"
            logger.error(f"Job {job_id} failed: {error_msg}")
            self._update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=error_msg
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"Download failed: {e.stderr or e.stdout or str(e)}"
            logger.error(f"Job {job_id} failed: {error_msg}")
            self._update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=error_msg[:200]  # Limit error message length
            )
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Job {job_id} failed: {error_msg}")
            self._update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=error_msg[:200]
            )

    def _get_download_tool(self, url: str) -> str:
        """Determine which tool to use based on the URL"""
        if any(domain in url.lower() for domain in ['instagram.com', 'flickr.com']):
            return 'gallery-dl'
        return 'yt-dlp'

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
CORS(app)

# Initialize download manager
download_manager = DownloadManager()

@app.route('/')
def index():
    """Main page with download form and job list"""
    jobs = download_manager.get_all_jobs()
    return render_template('index.html', jobs=jobs)

@app.route('/download', methods=['POST'])
def start_download():
    """Start a new download job"""
    url = request.form.get('url', '').strip()
    
    if not url:
        flash('Please provide a valid URL', 'error')
        return redirect(url_for('index'))
    
    # Basic URL validation
    if not (url.startswith('http://') or url.startswith('https://')):
        flash('URL must start with http:// or https://', 'error')
        return redirect(url_for('index'))
    
    try:
        job_id = download_manager.create_job(url)
        flash(f'Download started for: {url}', 'success')
        logger.info(f"Created download job {job_id} for URL: {url}")
    except Exception as e:
        logger.error(f"Failed to create download job: {e}")
        flash('Failed to start download. Please try again.', 'error')
    
    return redirect(url_for('index'))

@app.route('/status/<job_id>')
def job_status(job_id: str):
    """Get status of a specific job"""
    job = download_manager.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(job.to_dict())

@app.route('/download/<job_id>')
def download_file(job_id: str):
    """Download a completed file"""
    job = download_manager.get_job(job_id)
    
    if not job:
        return "Job not found", 404
    
    if job.status != JobStatus.COMPLETED or not job.filename:
        return "File not ready for download", 404
    
    file_path = DOWNLOADS_DIR / job.filename
    if not file_path.exists():
        return "File not found", 404
    
    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name=job.filename
        )
    except Exception as e:
        logger.error(f"Error serving file {job.filename}: {e}")
        return "Error serving file", 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'jobs_count': len(download_manager.jobs)
    })

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_code=404, 
                         error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', 
                         error_code=500, 
                         error_message="Internal server error"), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 12000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Media Downloader on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)