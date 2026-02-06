#!/usr/bin/env python3
"""
VibeFoundry Sync Server
Simple HTTP server for browser-based file sync with VibeFoundry Assistant
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import subprocess
import signal
import atexit

app = Flask(__name__)
CORS(app)  # Allow browser connections from any origin

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FOLDER = os.path.join(BASE_DIR, "app_folder")
SCRIPTS_FOLDER = os.path.join(APP_FOLDER, "scripts")
METADATA_FOLDER = os.path.join(APP_FOLDER, "meta_data")

# ttyd configuration
TTYD_PORT = 7681
ttyd_process = None


def start_ttyd():
    """Start ttyd terminal server"""
    global ttyd_process
    if ttyd_process is not None:
        return

    try:
        # Start ttyd with CORS allowed, running bash in app_folder
        ttyd_process = subprocess.Popen(
            [
                "ttyd",
                "-p", str(TTYD_PORT),
                "-W",  # Allow write (bidirectional)
                "-t", "fontSize=14",
                "-t", "fontFamily=Menlo, Monaco, 'Courier New', monospace",
                "-t", "theme={'background': '#ffffff', 'foreground': '#1e1e1e'}",
                "bash"
            ],
            cwd=APP_FOLDER,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"Started ttyd on port {TTYD_PORT}")
    except FileNotFoundError:
        print("ERROR: ttyd not found. Install with: brew install ttyd (macOS) or apt install ttyd (Linux)")


def stop_ttyd():
    """Stop ttyd terminal server"""
    global ttyd_process
    if ttyd_process is not None:
        ttyd_process.terminate()
        try:
            ttyd_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ttyd_process.kill()
        ttyd_process = None
        print("Stopped ttyd")


# Register cleanup
atexit.register(stop_ttyd)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "vibefoundry-sync"})


@app.route("/terminal-url", methods=["GET"])
def terminal_url():
    """Get the ttyd terminal URL"""
    return jsonify({"port": TTYD_PORT})


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


@app.route("/scripts", methods=["GET"])
def list_scripts():
    """List all files in scripts folder recursively"""
    def collect_files(folder, prefix=""):
        files = []
        if not os.path.exists(folder):
            return files
        for entry in os.listdir(folder):
            # Skip hidden files and node_modules
            if entry.startswith('.') or entry == 'node_modules' or entry == '__pycache__':
                continue
            filepath = os.path.join(folder, entry)
            relative_path = os.path.join(prefix, entry) if prefix else entry
            if os.path.isfile(filepath):
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

    scripts = collect_files(SCRIPTS_FOLDER)
    return jsonify({"scripts": scripts})


@app.route("/scripts/<path:filepath>", methods=["GET"])
def get_script(filepath):
    """Download a specific file from scripts folder (supports nested paths)"""
    full_path = os.path.join(SCRIPTS_FOLDER, filepath)

    # Security check - ensure path is within SCRIPTS_FOLDER
    if not os.path.abspath(full_path).startswith(os.path.abspath(SCRIPTS_FOLDER)):
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
    """Upload a file to the scripts folder (supports nested paths)"""
    # Security check - ensure path doesn't escape scripts folder
    if ".." in filepath:
        return jsonify({"error": "Invalid path"}), 400

    full_path = os.path.join(SCRIPTS_FOLDER, filepath)

    # Security check - ensure path is within SCRIPTS_FOLDER
    if not os.path.abspath(full_path).startswith(os.path.abspath(SCRIPTS_FOLDER)):
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


if __name__ == "__main__":
    print("Starting VibeFoundry Sync Server on port 8787...")
    start_ttyd()
    try:
        app.run(host="0.0.0.0", port=8787, debug=False)
    finally:
        stop_ttyd()
