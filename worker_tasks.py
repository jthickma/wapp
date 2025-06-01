import os
import subprocess
import shutil
import glob
from config import PERSISTENT_DOWNLOAD_DIR, TEMP_DOWNLOAD_DIR
from database import update_task_status

def determine_tool_and_command(url, task_id, temp_output_base):
    """
    Determines the download tool and constructs the command.
    -P for yt-dlp specifies path prefix for output template.
    -o for yt-dlp specifies output template.
    gallery-dl uses -D for directory and --filename for template.
    """
    tool = None
    # Add more sophisticated tool detection based on URL patterns
    if "tiktok.com" in url or "youtube.com" in url or "vimeo.com" in url:
        tool = "yt-dlp"
    elif "instagram.com" in url or "flickr.com" in url:
        tool = "gallery-dl"
    else:
        raise ValueError(f"Unsupported URL pattern: {url}")

    if tool == "yt-dlp":
        # Output template: {task_id}.{extension} inside TEMP_DOWNLOAD_DIR
        output_template = os.path.join(TEMP_DOWNLOAD_DIR, f"{task_id}.%(ext)s")
        command = [
            tool, url,
            '--no-check-certificate', # Can be useful in some environments
            '--no-mtime', # Don't use server modification time
            '-o', output_template
        ]
    elif tool == "gallery-dl":
        # gallery-dl saves files named by their original name by default,
        # or by a template. We want to control the name.
        # filename template needs to be simple here, gallery-dl handles extensions.
        # It will create files like: {task_id}.jpg, {task_id}.png etc.
        # So we give it the base name.
        filename_template = task_id # gallery-dl will append .extension
        command = [
            tool, url,
            '-D', TEMP_DOWNLOAD_DIR, # Download directory
            '--filename', filename_template # Output filename template (base)
        ]
    return command, tool

def find_downloaded_file(task_id, tool_used):
    """
    Finds the actual downloaded file(s) based on the task_id prefix in TEMP_DOWNLOAD_DIR.
    Returns the full path to the primary downloaded file and its basename.
    """
    # Prioritize non-temporary files.
    # This glob pattern tries to find files starting with task_id
    search_pattern = os.path.join(TEMP_DOWNLOAD_DIR, f"{task_id}.*")
    downloaded_files = glob.glob(search_pattern)
    
    primary_file_path = None
    actual_filename = None

    if downloaded_files:
        # Filter out common temporary file extensions
        # and known metadata files like .json from yt-dlp's --write-info-json
        valid_files = [
            f for f in downloaded_files
            if not f.endswith(('.part', '.temp', '.ytdl', '.json'))
        ]
        if valid_files:
            # If multiple valid files (e.g., gallery-dl downloads an album),
            # this basic example just picks the first one.
            # For albums, you might want to zip them or handle them differently.
            primary_file_path = valid_files[0]
            actual_filename = os.path.basename(primary_file_path)
            
            # If gallery-dl was used and it created a subdirectory named task_id,
            # look for files inside that subdirectory.
            if tool_used == "gallery-dl":
                potential_subdir = os.path.join(TEMP_DOWNLOAD_DIR, task_id)
                if os.path.isdir(potential_subdir):
                    subdir_files = glob.glob(os.path.join(potential_subdir, "*"))
                    valid_subdir_files = [
                        f for f in subdir_files
                        if not os.path.basename(f).startswith('.') and # ignore hidden files
                           not f.endswith(('.part', '.temp', '.json'))
                    ]
                    if valid_subdir_files:
                        # TODO: Handle multiple files in subdir (e.g., zip them)
                        # For now, take the first one as primary.
                        primary_file_path = valid_subdir_files[0]
                        actual_filename = os.path.basename(primary_file_path)


    return primary_file_path, actual_filename


def execute_download_task(task_id, url):
    print(f"WORKER: Starting download for Task ID {task_id}, URL {url}")
    update_task_status(task_id, status='Downloading...')

    temp_output_base = os.path.join(TEMP_DOWNLOAD_DIR, task_id) # Base for temp files

    try:
        command, tool_used = determine_tool_and_command(url, task_id, temp_output_base)
        
        print(f"WORKER: Executing command: {' '.join(command)}")
        # Ensure yt-dlp and gallery-dl are in PATH or provide full path to them.
        result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=TEMP_DOWNLOAD_DIR)

        downloaded_temp_filepath = None
        final_filename = None

        if result.returncode == 0:
            print(f"WORKER: Subprocess successful for {task_id}.")
            downloaded_temp_filepath, final_filename = find_downloaded_file(task_id, tool_used)

            if downloaded_temp_filepath and final_filename:
                print(f"WORKER: Identified downloaded file: {downloaded_temp_filepath} with final name: {final_filename}")
                
                # Ensure PERSISTENT_DOWNLOAD_DIR exists (worker might start before app)
                if not os.path.exists(PERSISTENT_DOWNLOAD_DIR):
                    os.makedirs(PERSISTENT_DOWNLOAD_DIR, exist_ok=True)

                persistent_filepath = os.path.join(PERSISTENT_DOWNLOAD_DIR, final_filename)
                
                # Ensure no filename collision in persistent storage (optional, depends on desired behavior)
                # If collision, could rename: final_filename = f"{task_id}_{original_filename}"
                if os.path.exists(persistent_filepath):
                    # Simple collision handling: append task_id prefix if not already there
                    if not final_filename.startswith(task_id):
                         final_filename = f"{task_id}_{final_filename}"
                         persistent_filepath = os.path.join(PERSISTENT_DOWNLOAD_DIR, final_filename)
                    else: # If already has task_id, maybe add a counter or overwrite
                        print(f"WORKER: Warning - File {persistent_filepath} already exists. Overwriting.")
                        # os.remove(persistent_filepath) # if overwrite is desired

                shutil.move(downloaded_temp_filepath, persistent_filepath)
                print(f"WORKER: Moved {downloaded_temp_filepath} to {persistent_filepath}")
                
                update_task_status(task_id, status='Completed', filename=final_filename, relative_path=final_filename)
                print(f"WORKER: Task {task_id} completed. File: {final_filename}")
            else:
                error_msg = "Download command succeeded but output file not found."
                print(f"WORKER: Error for {task_id} - {error_msg} Stdout: {result.stdout}, Stderr: {result.stderr}")
                update_task_status(task_id, status='Failed', error_message=error_msg)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or f"Download failed with exit code {result.returncode}"
            print(f"WORKER: Download failed for {task_id}: {error_msg}")
            update_task_status(task_id, status='Failed', error_message=error_msg[:500])

    except Exception as e:
        error_msg = str(e)
        print(f"WORKER: An unexpected error occurred for task {task_id}: {error_msg}")
        update_task_status(task_id, status='Failed', error_message=error_msg[:500])
    finally:
        # Clean up any remaining temporary files or directories for this task_id
        # This is a broader cleanup than just the single `downloaded_temp_filepath`
        # as some tools might create multiple files or subdirectories.
        cleanup_patterns = [
            os.path.join(TEMP_DOWNLOAD_DIR, f"{task_id}*"), # Files starting with task_id
            os.path.join(TEMP_DOWNLOAD_DIR, task_id)      # A directory named task_id
        ]
        for pattern in cleanup_patterns:
            matched_items = glob.glob(pattern)
            for item_path in matched_items:
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.remove(item_path)
                        print(f"WORKER: Cleaned temp file: {item_path}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        print(f"WORKER: Cleaned temp directory: {item_path}")
                except Exception as e_clean:
                    print(f"WORKER: Error cleaning up {item_path}: {e_clean}")
