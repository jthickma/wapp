import sqlite3
import uuid
import time
import threading
from config import SQLITE_DB_FILE

# Thread lock for database operations
_db_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(SQLITE_DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row # Access columns by name
    return conn

def init_db():
    with _db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                filename TEXT,
                relative_path TEXT, -- Path relative to PERSISTENT_DOWNLOAD_DIR
                error_message TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

def create_task(url):
    init_db()  # Ensure table exists
    task_id = str(uuid.uuid4())
    now = time.time()
    with _db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (id, url, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (task_id, url, 'Pending', now, now))
        conn.commit()
        conn.close()
    return task_id

def get_task(task_id):
    with _db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        conn.close()
    return task

def update_task_status(task_id, status, filename=None, relative_path=None, error_message=None):
    now = time.time()
    with _db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        updates = {
            'status': status,
            'filename': filename,
            'relative_path': relative_path,
            'error_message': error_message,
            'updated_at': now
        }
        set_clauses = []
        values = []
        for key, value in updates.items():
            if value is not None or key in ['error_message', 'filename', 'relative_path']:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if not set_clauses:
            conn.close()
            return False

        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        values.append(task_id)
        
        cursor.execute(sql, tuple(values))
        conn.commit()
        updated_rows = cursor.rowcount > 0
        conn.close()
    return updated_rows

def get_all_tasks(limit=50, offset=0):
    with _db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset))
        tasks = cursor.fetchall()
        conn.close()
    return tasks

# Initialize DB schema when this module is first imported
init_db()
