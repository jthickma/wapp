import os
import subprocess
import threading
from flask import Flask, render_template, request, send_from_directory, redirect, url_for

app = Flask(__name__)

# Directory to store downloaded files
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# In-memory list to track downloads (for demonstration purposes)
# In a real application, you would use a database for persistence and better tracking
downloads = []

def run_download(url, download_id):
    """Runs the download process in a separate thread."""
    # Find the download entry by its ID
    download_entry = next((d for d in downloads if d['id'] == download_id), None)
    if not download_entry:
        print(f"Error: Download entry not found for ID {download_id}")
        return

    try:
        # Determine which tool to use based on the URL (basic check)
        if "youtube.com" in url or "youtu.be" in url:
            tool = "yt-dlp"
        else:
            tool = "gallery-dl"

        download_entry['status'] = 'Downloading...'
        print(f"Starting download for {url} using {tool}")

        # Construct the command
        # --output "%(title)s.%(ext)s" for yt-dlp to get a predictable filename
        # gallery-dl uses a similar default or can be configured
        # We will list files in the directory after download to find the file
        command = [tool, url, '-P', DOWNLOAD_FOLDER] # -P sets the download directory

        # Execute the command
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Download successful for {url}")
            download_entry['status'] = 'Completed'
            # Attempt to find the downloaded file(s)
            # This is a simplification; a more robust approach would parse tool output
            # or use a specific output template to know the exact filename(s)
            # For now, we'll just list files modified recently or look for common patterns
            # A better approach for yt-dlp is using --print filename
            # A better approach for gallery-dl is also using output templates
            # Let's list files in the download directory and assume the latest is the one
            # This is NOT reliable if multiple downloads happen concurrently
            # A robust solution would involve parsing the tool's output for the final filename
            # Or passing a specific output template to the tool and knowing the filename beforehand
            try:
                # Simple approach: list files and find the newest one in the download folder
                # This is highly unreliable in a multi-user scenario
                # A better approach is needed for production
                files_before = set(os.listdir(DOWNLOAD_FOLDER))
                # Re-run with --print filename for yt-dlp if applicable
                if tool == "yt-dlp":
                     filename_command = ["yt-dlp", "--print", "filename", "-P", DOWNLOAD_FOLDER, url]
                     filename_result = subprocess.run(filename_command, capture_output=True, text=True)
                     if filename_result.returncode == 0:
                         # yt-dlp --print filename outputs the expected filename relative to the output dir
                         # We need to clean it up and join with the download folder path
                         output_filename = filename_result.stdout.strip()
                         # yt-dlp might output multiple lines if it downloads multiple files (e.g., playlists)
                         # This simple example assumes a single file download
                         # For playlists, the approach needs to be more complex
                         if '\n' in output_filename:
                             print(f"Warning: yt-dlp printed multiple filenames for {url}. Only linking the first one.")
                             output_filename = output_filename.split('\n')[0]

                         # Clean the filename to remove potential invalid characters or paths
                         # This is a basic cleaning, more robust sanitization might be needed
                         base_filename = os.path.basename(output_filename)
                         download_entry['filename'] = base_filename
                         print(f"Identified filename for {url}: {base_filename}")
                     else:
                         print(f"Could not determine filename for {url} using --print filename: {filename_result.stderr}")
                         download_entry['filename'] = "unknown_file" # Indicate file could not be determined
                         download_entry['status'] = 'Completed (Filename Unknown)' # Update status

                elif tool == "gallery-dl":
                     # gallery-dl doesn't have a simple --print filename like yt-dlp
                     # A common approach is to define a strict output template
                     # For this example, we'll just list files after the download and hope to find it
                     # This is very unreliable. A production version MUST parse gallery-dl output
                     # or use a very specific output template.
                     print(f"Warning: Filename detection for gallery-dl is unreliable. Please check the {DOWNLOAD_FOLDER} directory.")
                     # Simple (unreliable) attempt to find a new file
                     files_after = set(os.listdir(DOWNLOAD_FOLDER))
                     new_files = list(files_after - files_before)
                     if new_files:
                         # Assuming the first new file is the one (highly risky)
                         download_entry['filename'] = new_files[0]
                         print(f"Possibly identified filename for {url}: {new_files[0]} (unreliable)")
                     else:
                         download_entry['filename'] = "unknown_file"
                         download_entry['status'] = 'Completed (Filename Unknown)'


            except Exception as e:
                print(f"Error identifying downloaded file for {url}: {e}")
                download_entry['filename'] = "unknown_file"
                download_entry['status'] = 'Completed (Filename Error)'


        else:
            print(f"Download failed for {url}: {result.stderr}")
            download_entry['status'] = f'Failed: {result.stderr[:100]}...' # Truncate error message
            download_entry['filename'] = None # No file available

    except Exception as e:
        print(f"An error occurred during download for {url}: {e}")
        download_entry['status'] = f'Failed: {e}'
        download_entry['filename'] = None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            # Generate a simple unique ID for this download entry
            download_id = len(downloads) + 1
            downloads.append({'id': download_id, 'url': url, 'status': 'Pending', 'filename': None})
            print(f"Added download request for {url} with ID {download_id}")

            # Start the download in a new thread
            # This prevents the web server from blocking, but is not a robust background job queue
            # For production, consider using Celery or similar
            thread = threading.Thread(target=run_download, args=(url, download_id))
            thread.start()

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
