import os
import subprocess
import threading
from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import glob
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# Thread pool for download tasks and lock for thread-safe operations
executor = ThreadPoolExecutor(max_workers=4)
downloads_lock = Lock()

app = Flask(__name__)

# Directory to store downloaded files
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# In-memory list to track downloads (use a lock for thread safety)
downloads = []

def run_download(url, download_id):
    """Runs the download process in a separate thread."""
    # Find the download entry by its ID
    download_entry = next((d for d in downloads if d['id'] == download_id), None)
    if not download_entry:
        print(f"Error: Download entry not found for ID {download_id}")
        return

    try:
        # Determine which tool to use
        if "youtube.com" in url or "youtu.be" in url:
            tool = "yt-dlp"
        else:
            tool = "gallery-dl"

        download_entry['status'] = 'Downloading...'
        print(f"Starting download for {url} using {tool}")

        # Use a deterministic output template so we know the filename in advance
        output_template = f"{download_id}.%(ext)s"
        command = [tool, url, '-P', DOWNLOAD_FOLDER, '-o', output_template]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Download successful for {url}")
            download_entry['status'] = 'Completed'
            # Identify the downloaded file by globbing
            pattern = os.path.join(DOWNLOAD_FOLDER, f"{download_id}.*")
            matches = glob.glob(pattern)
            if matches:
                filename = os.path.basename(matches[0])
                download_entry['filename'] = filename
                print(f"Identified filename for {url}: {filename}")
            else:
                download_entry['filename'] = None
                print(f"No file found for pattern {pattern}")
        else:
            print(f"Download failed for {url}: {result.stderr}")
            download_entry['status'] = f'Failed: {result.stderr[:100]}...'
            download_entry['filename'] = None

    except Exception as e:
        print(f"An error occurred during download for {url}: {e}")
        download_entry['status'] = f'Failed: {e}'
        download_entry['filename'] = None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            with downloads_lock:
                download_id = len(downloads) + 1
                downloads.append({'id': download_id, 'url': url, 'status': 'Pending', 'filename': None})
            print(f"Added download request for {url} with ID {download_id}")

            # Submit the download task to the thread pool
            executor.submit(run_download, url, download_id)

        # Redirect to GET request to avoid form resubmission on refresh
        return redirect(url_for('index'))

    # GET request: Render the page with the current download list
    return render_template('index.html', downloads=downloads)

@app.route('/downloads/<filename>')
def serve_download(filename):
    """Serves the downloaded file."""
    try:
        # Ensure filename is safe to prevent directory traversal
        # send_from_directory handles this safety check
        return send_from_directory(DOWNLOAD_FOLDER, filename)
    except FileNotFoundError:
        return "File not found", 404
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return "Error serving file", 500


if __name__ == '__main__':
    # In a production Docker environment, you'd use a production WSGI server like Gunicorn
    # For local testing, running with app.run() is fine
    app.run(debug=True, host='0.0.0.0')
