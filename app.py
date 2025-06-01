import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_cors import CORS
from redis import Redis
from rq import Queue
from config import REDIS_URL, PERSISTENT_DOWNLOAD_DIR, FILE_SERVE_BASE_URL
import database
import worker_tasks # So Flask app knows about the task function

app = Flask(__name__)
CORS(app) # Allow all origins for simplicity, configure as needed

# RQ Queue
redis_conn = Redis.from_url(REDIS_URL)
download_queue = Queue("downloads", connection=redis_conn) # 'downloads' is the queue name

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            task_id = database.create_task(url)
            try:
                # Enqueue the job to be processed by an RQ worker
                download_queue.enqueue(worker_tasks.execute_download_task, task_id, url, job_timeout='2h') # 2 hour timeout
                print(f"APP: Enqueued download task {task_id} for URL: {url}")
            except Exception as e:
                print(f"APP: Error enqueuing task {task_id}: {e}")
                database.update_task_status(task_id, status='Failed', error_message=f"Failed to enqueue: {str(e)}")
        return redirect(url_for('index'))

    tasks = database.get_all_tasks()
    return render_template('index.html', downloads=tasks, file_serve_base_url=FILE_SERVE_BASE_URL)

@app.route('/status/<task_id>', methods=['GET'])
def get_task_status_api(task_id):
    task = database.get_task(task_id)
    if task:
        return jsonify(dict(task)) # Convert SQLite Row to dict for JSON
    return jsonify({'error': 'Task not found'}), 404

# Route to serve downloaded files from the persistent storage
@app.route(f"{FILE_SERVE_BASE_URL}/<path:filename>")
def serve_downloaded_file(filename):
    # Security: Ensure filename is safe and actually corresponds to a completed task's file.
    # This basic implementation relies on the filename stored in DB.
    # A more robust check would verify if 'filename' is indeed from a completed task.
    print(f"APP: Attempting to serve: {filename} from {PERSISTENT_DOWNLOAD_DIR}")
    try:
        return send_from_directory(PERSISTENT_DOWNLOAD_DIR, filename, as_attachment=True)
    except FileNotFoundError:
        print(f"APP: File not found: {filename} in {PERSISTENT_DOWNLOAD_DIR}")
        return "File not found", 404
    except Exception as e:
        print(f"APP: Error serving file {filename}: {e}")
        return "Error serving file", 500


if __name__ == '__main__':
    # This is for local Flask dev server.
    # In production (Coolify), use Gunicorn.
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    # The port Coolify exposes will be different.
    app.run(host='0.0.0.0', port=5000, debug=True)
    