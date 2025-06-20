import os
import logging
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_cors import CORS
from redis import Redis, ConnectionError
from rq import Queue
from config import REDIS_URL, PERSISTENT_DOWNLOAD_DIR, FILE_SERVE_BASE_URL
import database
import worker_tasks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# RQ Queue with connection error handling
try:
    redis_conn = Redis.from_url(REDIS_URL)
    redis_conn.ping()  # Test connection
    download_queue = Queue("downloads", connection=redis_conn)
    logger.info("Redis connection established successfully")
except ConnectionError as e:
    logger.error(f"Redis connection failed: {e}")
    redis_conn = None
    download_queue = None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if not download_queue:
            return render_template('index.html', 
                                 downloads=[], 
                                 file_serve_base_url=FILE_SERVE_BASE_URL,
                                 error="Redis connection unavailable. Please contact administrator.")
        
        url = request.form.get('url')
        if url:
            try:
                task_id = database.create_task(url)
                download_queue.enqueue(worker_tasks.execute_download_task, task_id, url, job_timeout='2h')
                logger.info(f"Enqueued download task {task_id} for URL: {url}")
            except Exception as e:
                logger.error(f"Error enqueuing task: {e}")
                if 'task_id' in locals():
                    database.update_task_status(task_id, status='Failed', 
                                              error_message=f"Failed to enqueue: {str(e)}")
        return redirect(url_for('index'))

    try:
        tasks = database.get_all_tasks()
        return render_template('index.html', downloads=tasks, file_serve_base_url=FILE_SERVE_BASE_URL)
    except Exception as e:
        logger.error(f"Database error: {e}")
        return render_template('index.html', downloads=[], 
                             file_serve_base_url=FILE_SERVE_BASE_URL,
                             error="Database error. Please contact administrator.")

@app.route('/status/<task_id>', methods=['GET'])
def get_task_status_api(task_id):
    try:
        task = database.get_task(task_id)
        if task:
            return jsonify(dict(task))
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route(f"{FILE_SERVE_BASE_URL}/<path:filename>")
def serve_downloaded_file(filename):
    try:
        # Verify file exists in database
        tasks = database.get_all_tasks()
        valid_files = [task['relative_path'] for task in tasks if task['relative_path'] == filename and task['status'] == 'Completed']
        
        if not valid_files:
            logger.warning(f"Unauthorized file access attempt: {filename}")
            return "File not found or not available for download", 404
            
        logger.info(f"Serving file: {filename} from {PERSISTENT_DOWNLOAD_DIR}")
        return send_from_directory(PERSISTENT_DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
        return "File not found", 404
    except Exception as e:
        logger.error(f"Error serving file {filename}: {e}")
        return "Error serving file", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
