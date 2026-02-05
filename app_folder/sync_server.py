#!/usr/bin/env python3
"""
VibeFoundry Sync Server
Simple HTTP server for browser-based file sync with VibeFoundry Assistant
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_sock import Sock
import os
import json
import pty
import subprocess
import select

app = Flask(__name__)
CORS(app)  # Allow browser connections from any origin
sock = Sock(app)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FOLDER = os.path.join(BASE_DIR, "app_folder")
SCRIPTS_FOLDER = os.path.join(APP_FOLDER, "scripts")
METADATA_FOLDER = os.path.join(APP_FOLDER, "meta_data")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "vibefoundry-sync"})


@app.route("/scripts", methods=["GET"])
def list_scripts():
    """List all Python scripts"""
    scripts = []
    if os.path.exists(SCRIPTS_FOLDER):
        for filename in os.listdir(SCRIPTS_FOLDER):
            if filename.endswith(".py"):
                filepath = os.path.join(SCRIPTS_FOLDER, filename)
                stat = os.stat(filepath)
                scripts.append({
                    "name": filename,
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
    return jsonify({"scripts": scripts})


@app.route("/scripts/<filename>", methods=["GET"])
def get_script(filename):
    """Download a specific script"""
    if not filename.endswith(".py"):
        return jsonify({"error": "Invalid file type"}), 400

    filepath = os.path.join(SCRIPTS_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Script not found"}), 404

    # Return file contents as JSON for easier browser handling
    with open(filepath, "r") as f:
        content = f.read()

    return jsonify({
        "name": filename,
        "content": content,
        "modified": os.stat(filepath).st_mtime
    })


@app.route("/scripts/<filename>", methods=["POST"])
def upload_script(filename):
    """Upload a script to the scripts folder"""
    if not filename.endswith(".py"):
        return jsonify({"error": "Invalid file type"}), 400

    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "No content provided"}), 400

    os.makedirs(SCRIPTS_FOLDER, exist_ok=True)
    filepath = os.path.join(SCRIPTS_FOLDER, filename)

    with open(filepath, "w") as f:
        f.write(data["content"])

    return jsonify({
        "status": "ok",
        "name": filename,
        "message": f"Script {filename} uploaded"
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


@sock.route("/terminal")
def terminal(ws):
    """WebSocket terminal endpoint"""
    pid, fd = pty.fork()

    if pid == 0:
        # Child process - start bash
        os.chdir(APP_FOLDER)
        os.execvp("bash", ["bash"])
    else:
        # Parent process - relay data
        try:
            while True:
                # Check for data from terminal
                r, _, _ = select.select([fd], [], [], 0.1)
                if fd in r:
                    try:
                        data = os.read(fd, 1024)
                        if data:
                            ws.send(data.decode("utf-8", errors="replace"))
                    except OSError:
                        break

                # Check for data from websocket
                try:
                    data = ws.receive(timeout=0.01)
                    if data:
                        os.write(fd, data.encode("utf-8"))
                except:
                    pass
        finally:
            os.close(fd)
            os.waitpid(pid, 0)


if __name__ == "__main__":
    print("Starting VibeFoundry Sync Server on port 8787...")
    app.run(host="0.0.0.0", port=8787, debug=False)
