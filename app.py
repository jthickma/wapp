# app.py
import logging
from itertools import chain
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, flash
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
from config import REDIS_URL, PERSISTENT_STORAGE_DIR, FILE_SERVE_BASE_URL
import worker_tasks

# --- App Initialization ---
app = Flask(__name__)
app.secret_key = 'a-much-simpler-secret-key'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Redis & RQ ---
try:
    redis_conn = Redis.from_url(REDIS_URL)
    download_queue = Queue("downloads", connection=redis_conn)
except RedisConnectionError:
    redis_conn = None
    download_queue = None
    logging.error("FATAL: Could not connect to Redis.")

# --- Helper to format job data for the template ---
def format_job_for_template(job):
    status = job.get_status()
    error_message = job.exc_info.splitlines()[-1] if job.is_failed else None
    
    # Custom statuses from worker metadata
    if status == 'started':
        status = job.meta.get('status', 'Downloading...')
        
    # Get final filename from the job result if completed
    filename = None
    if job.is_finished and isinstance(job.result, dict):
        filename = job.result.get('filename')

    return {
        'id': job.id,
        'url': job.args[0] if job.args else 'N/A', # URL is the first argument
        'status': status.capitalize(),
        'filename': filename,
        'relative_path': filename, # For consistency with template
        'error_message': error_message
    }

# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if not redis_conn:
        return "Error: Cannot connect to Redis. The application is disabled.", 503

    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            # Enqueue the job. The job ID will be our task ID.
            job = download_queue.enqueue(worker_tasks.execute_download_task, url, job_timeout='1h')
            flash(f"Download requested for: {url}", "success")
        return redirect(url_for('index'))

    # Get jobs from all relevant registries to build the dashboard
    q_jobs = download_queue.get_job_ids()
    started_jobs = StartedJobRegistry('downloads', connection=redis_conn).get_job_ids()
    finished_jobs = FinishedJobRegistry('downloads', connection=redis_conn).get_job_ids()
    failed_jobs = FailedJobRegistry('downloads', connection=redis_conn).get_job_ids()

    # Fetch all job objects, avoiding duplicates
    job_ids = set(chain(q_jobs, started_jobs, finished_jobs, failed_jobs))
    jobs = Job.fetch_many(list(job_ids), connection=redis_conn)
    
    # Sort by creation time, newest first
    tasks = sorted([format_job_for_template(j) for j in jobs if j], key=lambda x: x['id'], reverse=True)

    return render_template('index.html', downloads=tasks, file_serve_base_url=FILE_SERVE_BASE_URL)

@app.route('/status/<job_id>')
def task_status(job_id):
    if not redis_conn:
        return jsonify({'error': 'Redis unavailable'}), 503
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return jsonify(format_job_for_template(job))
    except Exception:
        return jsonify({'error': 'Task not found'}), 404

@app.route(f"{FILE_SERVE_BASE_URL}/<path:filename>")
def serve_downloaded_file(filename):
    if not redis_conn:
        return "Error: Redis unavailable", 503
        
    # Security check: Filename must be the ID of a successfully completed job.
    job_id, extension = filename.split('.', 1)
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        if not job.is_finished:
             return "File not yet available.", 404
             
        # Verify the result from the job matches
        job_result_filename = job.result.get('filename')
        if job_result_filename == filename:
            PERSISTENT_STORAGE_DIR.mkdir(exist_ok=True)
            return send_from_directory(PERSISTENT_STORAGE_DIR, filename, as_attachment=True)
        else:
            return "Unauthorized access.", 403

    except Exception:
        return "File not found or invalid.", 404
    