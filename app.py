import os
import subprocess
import threading
from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import glob
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time # Import time for sleep

# Thread pool for download tasks and lock for thread-safe operations
executor = ThreadPoolExecutor(max_workers=4) # Limit concurrent downloads
downloads_lock = Lock()

app = Flask(__name__)

# Directory to store downloaded files
DOWNLOAD_FOLDER = os.path.abspath('downloads') # Use absolute path
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# In-memory list to track downloads (in a real app, use a DB or persistent store)
downloads = [] # { 'id': UUID, 'url': str, 'status': str, 'filename': str or None }

def run_download(url, download_id):
    """Runs the download process in a separate thread."""
    # Use the lock to safely find and update the download entry
    with downloads_lock:
        download_entry = next((d for d in downloads if d['id'] == download_id), None)
    
    if not download_entry:
        print(f"Error: Download entry not found for ID {download_id}")
        return

    try:
        # Determine which tool to use. yt-dlp is generally more versatile.
        if "youtube.com" in url or "youtu.be" in url or "tiktok.com" in url: # Added tiktok
            tool = "yt-dlp"
        else:
            tool = "gallery-dl"

        download_entry['status'] = 'Downloading...'
        print(f"Starting download for {url} using {tool} with ID {download_id}")

        # Define a predictable temporary output path for the downloaded file(s)
        # The tools will add their own extensions, so we just use the UUID as a base
        temp_output_path_base = os.path.join(DOWNLOAD_FOLDER, str(download_id))
        
        # Common options for both yt-dlp and gallery-dl
        command = [tool, url, '-P', DOWNLOAD_FOLDER, '-o', temp_output_path_base + '.%(ext)s']

        # Execute the download command
        result = subprocess.run(command, capture_output=True, text=True, check=False) # check=False to handle non-zero exit codes

        if result.returncode == 0:
            print(f"Download successful for {url}")
            
            # --- Filename identification: More robust approach ---
            # Find the actual downloaded file(s) based on the UUID prefix
            downloaded_files = glob.glob(f"{temp_output_path_base}.*")
            
            filename = None
            if downloaded_files:
                # If multiple files are downloaded (e.g., separate audio/video), pick one or handle appropriately.
                # For simplicity, we'll take the first one found that's not a temporary file.
                for fpath in downloaded_files:
                    # Exclude temporary files if any exist (e.g., .part, .temp)
                    if not fpath.endswith(('.part', '.temp', '.json')): 
                        filename = os.path.basename(fpath)
                        break
            
            if filename:
                download_entry['status'] = 'Completed'
                download_entry['filename'] = filename
                print(f"Identified filename for ID {download_id}: {filename}")
            else:
                download_entry['status'] = 'Completed (Filename Unknown)' # Still completed, but couldn't name
                download_entry['filename'] = 'unknown_file'
                print(f"Could not identify filename for ID {download_id} after download. Files found: {downloaded_files}")
                print(f"Stdout: {result.stdout}\nStderr: {result.stderr}") # Log for debugging
        else:
            error_msg = result.stderr.strip() or f"Download failed with exit code {result.returncode}"
            download_entry['status'] = f'Failed: {error_msg[:100]}...'
            download_entry['filename'] = None
            print(f"Download failed for {url} (ID {download_id}): {result.stderr}")

    except Exception as e:
        error_msg = str(e)
        download_entry['status'] = f'Failed: {error_msg[:100]}...'
        download_entry['filename'] = None
        print(f"An error occurred during download for {url} (ID {download_id}): {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            new_download_id = str(uuid.uuid4()) # Generate a unique UUID for each download
            with downloads_lock:
                downloads.append({
                    'id': new_download_id,
                    'url': url,
                    'status': 'Pending',
                    'filename': None
                })
            print(f"Added download request for {url} with ID {new_download_id}")

            # Submit the download task to the thread pool
            executor.submit(run_download, url, new_download_id)

        # Redirect to GET request to avoid form resubmission on refresh
        return redirect(url_for('index'))

    # GET request: Render the page with the current download list
    with downloads_lock:
        # Pass a copy of the list to the template to avoid modification issues during rendering
        return render_template('index.html', downloads=list(downloads))

@app.route('/downloads/<path:filename>') # Use <path:filename> to allow slashes in filename
def serve_download(filename):
    """Serves the downloaded file."""
    # Ensure the requested filename is actually in our downloads list
    # This prevents serving arbitrary files from the DOWNLOAD_FOLDER
    with downloads_lock:
        # Check if any download entry has this filename and is completed
        is_valid_file = any(
            d.get('filename') == filename and d.get('status', '').startswith('Completed')
            for d in downloads
        )

    if not is_valid_file:
        print(f"Attempt to serve unauthorized or incomplete file: {filename}")
        return "Unauthorized or file not ready", 403 # Forbidden

    try:
        # send_from_directory handles safety checks against directory traversal
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True) # as_attachment=True prompts download
    except FileNotFoundError:
        print(f"File not found at {os.path.join(DOWNLOAD_FOLDER, filename)}")
        return "File not found", 404
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return "Error serving file", 500


if __name__ == '__main__':
    # In a production Docker environment, you'd use a production WSGI server like Gunicorn
    # For local testing, running with app.run() is fine. Use debug=True for development.
    app.run(host='0.0.0.0', debug=True) # debug=True is good for development