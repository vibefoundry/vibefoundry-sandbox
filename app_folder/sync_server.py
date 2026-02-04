#!/usr/bin/env python3
"""
VibeFoundry Sync Server
Simple HTTP server for browser-based file sync with VibeFoundry Assistant
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)  # Allow browser connections from any origin

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
    app.run(host="0.0.0.0", port=8787, debug=False)
