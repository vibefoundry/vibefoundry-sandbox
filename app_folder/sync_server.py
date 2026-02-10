#!/usr/bin/env python3
"""
VibeFoundry Sync Server
Simple HTTP server for browser-based file sync with VibeFoundry Assistant
Uses watchdog for native file system events - pushes changes via WebSocket
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sock import Sock
import os
import json
import pty
import subprocess
import select
import struct
import fcntl
import termios
import signal
import threading
import time

# Watchdog for native file system events
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("WARNING: watchdog not installed. File watching disabled.")
    print("Install with: pip install watchdog")

app = Flask(__name__)
# Explicit CORS config for GitHub Codespaces (their proxy can be tricky)
CORS(app, resources={r"/*": {"origins": "*", "supports_credentials": True}})
sock = Sock(app)


# Connected watch clients (WebSocket connections)
watch_clients = set()
watch_clients_lock = threading.Lock()

# Log all requests + ensure CORS headers (GitHub Codespaces proxy can strip them)
@app.after_request
def after_request(response):
    print(f"[{request.method}] {request.path} - {response.status_code}", flush=True)
    # Explicit CORS headers for GitHub Codespaces proxy
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FOLDER = os.path.join(BASE_DIR, "app_folder")
SCRIPTS_FOLDER = os.path.join(APP_FOLDER, "scripts")
METADATA_FOLDER = os.path.join(APP_FOLDER, "meta_data")

# Files/patterns to ignore in file watcher
IGNORE_PATTERNS = [
    '.ds_store', 'thumbs.db', 'desktop.ini',
    '.git', '__pycache__', '.pyc', '.pyo',
    'zone.identifier', '.tmp', '.temp', '~',
    'sync_server.py', 'metadatafarmer.py'
]


def should_ignore(path):
    """Check if file should be ignored"""
    name = os.path.basename(path).lower()
    for pattern in IGNORE_PATTERNS:
        if pattern in name:
            return True
    if name.startswith('.'):
        return True
    return False


def broadcast_change(change_type, filepath):
    """Broadcast file change to all connected watch clients"""
    relative_path = os.path.relpath(filepath, APP_FOLDER)
    message = json.dumps({
        "type": "file_change",
        "change": change_type,
        "path": relative_path,
        "timestamp": time.time()
    })

    with watch_clients_lock:
        dead_clients = set()
        for client in watch_clients:
            try:
                client.send(message)
            except:
                dead_clients.add(client)
        # Remove disconnected clients
        watch_clients.difference_update(dead_clients)


if WATCHDOG_AVAILABLE:
    class AppFolderHandler(FileSystemEventHandler):
        """Handler for file system events in app_folder"""

        def __init__(self):
            self._recent_events = {}
            self._lock = threading.Lock()

        def _debounce(self, path):
            """Debounce rapid events on the same file"""
            now = time.time()
            with self._lock:
                if now - self._recent_events.get(path, 0) < 0.5:
                    return True
                self._recent_events[path] = now
                # Clean old entries
                self._recent_events = {k: v for k, v in self._recent_events.items() if now - v < 5.0}
            return False

        def _handle_event(self, event, change_type):
            if event.is_directory:
                return
            path = event.src_path
            if should_ignore(path):
                return
            if self._debounce(path):
                return

            print(f"[WATCH] {change_type}: {os.path.relpath(path, APP_FOLDER)}", flush=True)
            broadcast_change(change_type, path)

        def on_created(self, event):
            self._handle_event(event, "created")

        def on_modified(self, event):
            self._handle_event(event, "modified")

        def on_deleted(self, event):
            self._handle_event(event, "deleted")


# Global observer
file_observer = None


def start_file_watcher():
    """Start the file watcher"""
    global file_observer

    if not WATCHDOG_AVAILABLE:
        print("File watcher not available (watchdog not installed)")
        return False

    try:
        file_observer = Observer()
        handler = AppFolderHandler()

        # Watch the entire app_folder
        file_observer.schedule(handler, APP_FOLDER, recursive=True)
        file_observer.start()
        print(f"File watcher started on {APP_FOLDER}", flush=True)
        return True
    except Exception as e:
        print(f"Failed to start file watcher: {e}", flush=True)
        return False


def stop_file_watcher():
    """Stop the file watcher"""
    global file_observer
    if file_observer:
        file_observer.stop()
        file_observer.join(timeout=1.0)
        file_observer = None


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "vibefoundry-sync"})


@app.route("/files", methods=["GET"])
def list_files():
    """List all files in the codespace as a tree structure"""
    # Folders to skip entirely
    SKIP_FOLDERS = {'node_modules', '__pycache__', '.git', '.venv', 'venv', '.cache'}

    def build_tree(path, name):
        result = {
            "name": name,
            "path": os.path.relpath(path, BASE_DIR),
            "isDirectory": os.path.isdir(path)
        }

        if os.path.isdir(path):
            result["children"] = []
            try:
                entries = sorted(os.listdir(path))
                # Directories first, then files
                dirs = [e for e in entries if os.path.isdir(os.path.join(path, e))]
                files = [e for e in entries if not os.path.isdir(os.path.join(path, e))]

                for entry in dirs + files:
                    # Skip hidden files and large folders
                    if entry.startswith('.') or entry in SKIP_FOLDERS:
                        continue
                    child_path = os.path.join(path, entry)
                    result["children"].append(build_tree(child_path, entry))
            except PermissionError:
                pass
        else:
            stat = os.stat(path)
            result["size"] = stat.st_size
            result["modified"] = stat.st_mtime

        return result

    # Build tree from BASE_DIR to include all project folders
    tree = build_tree(BASE_DIR, os.path.basename(BASE_DIR))
    return jsonify({"tree": tree})


@app.route("/files/<path:filepath>", methods=["GET"])
def get_file(filepath):
    """Get contents of any file in the project"""
    full_path = os.path.join(BASE_DIR, filepath)

    # Security check - ensure path is within BASE_DIR
    if not os.path.abspath(full_path).startswith(os.path.abspath(BASE_DIR)):
        return jsonify({"error": "Invalid path"}), 400

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    if os.path.isdir(full_path):
        return jsonify({"error": "Path is a directory"}), 400

    try:
        with open(full_path, "r") as f:
            content = f.read()
        return jsonify({
            "name": os.path.basename(filepath),
            "path": filepath,
            "content": content,
            "modified": os.stat(full_path).st_mtime
        })
    except UnicodeDecodeError:
        return jsonify({"error": "Binary file cannot be read as text"}), 400


# Files that should never be synced to the client
EXCLUDED_FILES = {'sync_server.py', 'metadatafarmer.py', 'CLAUDE.md'}
EXCLUDED_DIRS = {'meta_data', '__pycache__', 'node_modules'}


@app.route("/scripts", methods=["GET"])
def list_scripts():
    """List all files in app_folder recursively (excluding server files)"""
    def collect_files(folder, prefix=""):
        files = []
        if not os.path.exists(folder):
            return files
        for entry in os.listdir(folder):
            # Skip hidden files, excluded dirs, and excluded files
            if entry.startswith('.') or entry in EXCLUDED_DIRS:
                continue
            filepath = os.path.join(folder, entry)
            relative_path = os.path.join(prefix, entry) if prefix else entry
            if os.path.isfile(filepath):
                # Skip excluded files
                if entry in EXCLUDED_FILES:
                    continue
                stat = os.stat(filepath)
                files.append({
                    "name": entry,
                    "path": relative_path,
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
            elif os.path.isdir(filepath):
                files.extend(collect_files(filepath, relative_path))
        return files

    scripts = collect_files(APP_FOLDER)
    return jsonify({"scripts": scripts})


@app.route("/scripts/<path:filepath>", methods=["GET"])
def get_script(filepath):
    """Download a specific file from app_folder (supports nested paths)"""
    # Block access to excluded files
    filename = os.path.basename(filepath)
    if filename in EXCLUDED_FILES:
        return jsonify({"error": "Access denied"}), 403

    full_path = os.path.join(APP_FOLDER, filepath)

    # Security check - ensure path is within APP_FOLDER
    if not os.path.abspath(full_path).startswith(os.path.abspath(APP_FOLDER)):
        return jsonify({"error": "Invalid path"}), 400

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    # Return file contents as JSON for easier browser handling
    try:
        with open(full_path, "r") as f:
            content = f.read()
    except UnicodeDecodeError:
        return jsonify({"error": "Binary file cannot be read as text"}), 400

    return jsonify({
        "name": os.path.basename(filepath),
        "path": filepath,
        "content": content,
        "modified": os.stat(full_path).st_mtime
    })


@app.route("/scripts/<path:filepath>", methods=["POST"])
def upload_script(filepath):
    """Upload a file to the app_folder (supports nested paths)"""
    # Block uploads to excluded files
    filename = os.path.basename(filepath)
    if filename in EXCLUDED_FILES:
        return jsonify({"error": "Cannot overwrite protected file"}), 403

    # Security check - ensure path doesn't escape app folder
    if ".." in filepath:
        return jsonify({"error": "Invalid path"}), 400

    full_path = os.path.join(APP_FOLDER, filepath)

    # Security check - ensure path is within APP_FOLDER
    if not os.path.abspath(full_path).startswith(os.path.abspath(APP_FOLDER)):
        return jsonify({"error": "Invalid path"}), 400

    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "No content provided"}), 400

    # Create parent directories if needed
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, "w") as f:
        f.write(data["content"])

    return jsonify({
        "status": "ok",
        "name": os.path.basename(filepath),
        "path": filepath,
        "message": f"File {filepath} uploaded"
    })


@app.route("/metadata", methods=["POST"])
def upload_metadata():
    """Receive metadata files from browser"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    os.makedirs(METADATA_FOLDER, exist_ok=True)

    # Write input metadata
    if "input_metadata" in data:
        with open(os.path.join(METADATA_FOLDER, "input_metadata.txt"), "w") as f:
            f.write(data["input_metadata"])

    # Write output metadata
    if "output_metadata" in data:
        with open(os.path.join(METADATA_FOLDER, "output_metadata.txt"), "w") as f:
            f.write(data["output_metadata"])

    return jsonify({"status": "ok", "message": "Metadata updated"})


@app.route("/metadata", methods=["GET"])
def get_metadata():
    """Get current metadata files"""
    result = {}

    input_path = os.path.join(METADATA_FOLDER, "input_metadata.txt")
    if os.path.exists(input_path):
        with open(input_path, "r") as f:
            result["input_metadata"] = f.read()

    output_path = os.path.join(METADATA_FOLDER, "output_metadata.txt")
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            result["output_metadata"] = f.read()

    return jsonify(result)


@app.route("/reset", methods=["POST"])
def reset_codespace():
    """Reset the codespace to latest dev-branch (git reset --hard, clean, pull)"""
    try:
        # Run git fetch first
        fetch_result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Reset to origin/dev-branch
        reset_result = subprocess.run(
            ["git", "reset", "--hard", "origin/dev-branch"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Clean untracked files and directories (removes scripts, etc.)
        clean_result = subprocess.run(
            ["git", "clean", "-fd"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Pull latest
        pull_result = subprocess.run(
            ["git", "pull", "origin", "dev-branch"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )

        return jsonify({
            "status": "ok",
            "message": "Codespace reset to latest dev-branch",
            "fetch": {"stdout": fetch_result.stdout, "stderr": fetch_result.stderr},
            "reset": {"stdout": reset_result.stdout, "stderr": reset_result.stderr},
            "clean": {"stdout": clean_result.stdout, "stderr": clean_result.stderr},
            "pull": {"stdout": pull_result.stdout, "stderr": pull_result.stderr}
        })
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Git command timed out"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@sock.route("/watch")
def watch(ws):
    """WebSocket endpoint for file change notifications"""
    print("[WATCH] Client connected", flush=True)

    with watch_clients_lock:
        watch_clients.add(ws)

    try:
        # Send initial connected message
        ws.send(json.dumps({
            "type": "connected",
            "watching": APP_FOLDER,
            "watchdog_available": WATCHDOG_AVAILABLE
        }))

        # Keep connection alive - respond to pings
        while True:
            try:
                data = ws.receive(timeout=30)
                if data:
                    try:
                        msg = json.loads(data)
                        if msg.get('type') == 'ping':
                            ws.send(json.dumps({"type": "pong"}))
                    except:
                        pass
            except:
                # Timeout or error, send keepalive
                try:
                    ws.send(json.dumps({"type": "keepalive"}))
                except:
                    break
    finally:
        with watch_clients_lock:
            watch_clients.discard(ws)
        print("[WATCH] Client disconnected", flush=True)


def set_winsize(fd, row, col, xpix=0, ypix=0):
    """Set terminal window size"""
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


# Fixed terminal size
FIXED_COLS = 75
FIXED_ROWS = 30


@sock.route("/terminal")
def terminal(ws):
    """WebSocket terminal endpoint"""
    pid, fd = pty.fork()

    if pid == 0:
        # Child process - start bash directly (no tmux)
        os.chdir(APP_FOLDER)
        os.environ["TERM"] = "xterm-256color"
        os.execvp("bash", ["bash", "-l"])
    else:
        # Parent process - relay data
        set_winsize(fd, FIXED_ROWS, FIXED_COLS)

        # Make fd non-blocking
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        try:
            while True:
                # Check for data from terminal
                r, _, _ = select.select([fd], [], [], 0.1)
                if fd in r:
                    try:
                        data = os.read(fd, 8192)
                        if data:
                            ws.send(data.decode("utf-8", errors="replace"))
                    except OSError:
                        break

                # Check for data from websocket
                try:
                    data = ws.receive(timeout=0.01)
                    if data:
                        # Check for JSON commands (resize, ping)
                        if data.startswith('{'):
                            try:
                                msg = json.loads(data)
                                if msg.get('type') == 'resize':
                                    set_winsize(fd, FIXED_ROWS, FIXED_COLS)
                                elif msg.get('type') == 'ping':
                                    ws.send('{"type":"pong"}')
                            except:
                                pass
                        else:
                            os.write(fd, data.encode("utf-8"))
                except:
                    pass
        finally:
            os.close(fd)
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)


if __name__ == "__main__":
    print("Starting VibeFoundry Sync Server on port 8787...")

    # Start file watcher
    if start_file_watcher():
        print("File watcher: using native OS events (inotify)")
    else:
        print("File watcher: disabled")

    try:
        app.run(host="0.0.0.0", port=8787, debug=False)
    finally:
        stop_file_watcher()
