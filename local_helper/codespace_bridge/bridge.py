#!/usr/bin/env python3
"""
VibeFoundry CodeSpace Bridge
A native app for syncing files between local machine and GitHub Codespaces
"""

import webview
import threading
import json
import os
import sys
import subprocess
import webbrowser
import time
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Configuration
GITHUB_CLIENT_ID = "Ov23liYto761PIPmtvFf"  # Replace with your GitHub OAuth App Client ID
GITHUB_SCOPES = "codespace user:email"
CODESPACE_REPO = "vibefoundry/vibefoundry-sandbox"
REMOTE_PATH = "/workspaces/vibefoundry-sandbox"

# Global state
class AppState:
    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), ".vibefoundry-bridge")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.load_config()

    def load_config(self):
        os.makedirs(self.config_dir, exist_ok=True)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.github_token = data.get("github_token")
                    self.github_user = data.get("github_user")
                    self.project_folder = data.get("project_folder")
                    self.selected_codespace = data.get("selected_codespace")
                    return
            except:
                pass
        self.github_token = None
        self.github_user = None
        self.project_folder = None
        self.selected_codespace = None

    def save_config(self):
        data = {
            "github_token": self.github_token,
            "github_user": self.github_user,
            "project_folder": self.project_folder,
            "selected_codespace": self.selected_codespace
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f)

state = AppState()


class BridgeAPI:
    """API exposed to the JavaScript frontend"""

    def __init__(self):
        self.window = None

    def set_window(self, window):
        self.window = window

    def get_state(self):
        """Get current app state"""
        return {
            "logged_in": state.github_token is not None,
            "username": state.github_user,
            "project_folder": state.project_folder,
            "selected_codespace": state.selected_codespace,
            "gh_installed": self._check_gh_installed()
        }

    def _check_gh_installed(self):
        """Check if GitHub CLI is installed"""
        try:
            result = subprocess.run(["gh", "--version"], capture_output=True)
            return result.returncode == 0
        except:
            return False

    def _gh_auth_status(self):
        """Check if gh CLI is authenticated"""
        try:
            result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    def start_github_login(self):
        """Start GitHub Device Flow authentication"""
        try:
            # Request device code
            data = urllib.parse.urlencode({
                "client_id": GITHUB_CLIENT_ID,
                "scope": GITHUB_SCOPES
            }).encode()

            req = urllib.request.Request(
                "https://github.com/login/device/code",
                data=data,
                headers={"Accept": "application/json"}
            )

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())

            device_code = result["device_code"]
            user_code = result["user_code"]
            verification_uri = result["verification_uri"]
            expires_in = result["expires_in"]
            interval = result.get("interval", 5)

            # Open browser for user to enter code
            webbrowser.open(verification_uri)

            # Return code for display
            return {
                "success": True,
                "user_code": user_code,
                "verification_uri": verification_uri,
                "device_code": device_code,
                "interval": interval,
                "expires_in": expires_in
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def poll_github_login(self, device_code, interval):
        """Poll for GitHub login completion"""
        try:
            data = urllib.parse.urlencode({
                "client_id": GITHUB_CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            }).encode()

            req = urllib.request.Request(
                "https://github.com/login/oauth/access_token",
                data=data,
                headers={"Accept": "application/json"}
            )

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())

            if "access_token" in result:
                state.github_token = result["access_token"]

                # Get user info
                user_req = urllib.request.Request(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {state.github_token}",
                        "Accept": "application/json"
                    }
                )
                with urllib.request.urlopen(user_req) as user_response:
                    user_data = json.loads(user_response.read().decode())
                    state.github_user = user_data.get("login")

                # Also login gh CLI with this token
                self._setup_gh_cli()

                state.save_config()
                return {"success": True, "username": state.github_user}

            elif result.get("error") == "authorization_pending":
                return {"success": False, "pending": True}

            else:
                return {"success": False, "error": result.get("error_description", "Unknown error")}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _setup_gh_cli(self):
        """Configure gh CLI with our token"""
        if not state.github_token:
            return
        try:
            # Write token to gh CLI
            process = subprocess.Popen(
                ["gh", "auth", "login", "--with-token"],
                stdin=subprocess.PIPE,
                capture_output=True,
                text=True
            )
            process.communicate(input=state.github_token)
        except:
            pass

    def logout(self):
        """Logout from GitHub"""
        state.github_token = None
        state.github_user = None
        state.save_config()
        return {"success": True}

    def select_folder(self):
        """Open folder selection dialog"""
        folder = self.window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=state.project_folder or os.path.expanduser("~")
        )
        if folder and len(folder) > 0:
            state.project_folder = folder[0]
            state.save_config()
            return {"success": True, "folder": folder[0]}
        return {"success": False}

    def get_codespaces(self):
        """List available Codespaces"""
        if not state.github_token:
            return {"success": False, "error": "Not logged in"}

        try:
            req = urllib.request.Request(
                "https://api.github.com/user/codespaces",
                headers={
                    "Authorization": f"Bearer {state.github_token}",
                    "Accept": "application/vnd.github+json"
                }
            )

            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())

            codespaces = []
            for cs in data.get("codespaces", []):
                if CODESPACE_REPO in cs.get("repository", {}).get("full_name", ""):
                    codespaces.append({
                        "name": cs["name"],
                        "state": cs["state"],
                        "created_at": cs["created_at"],
                        "web_url": cs.get("web_url", "")
                    })

            return {"success": True, "codespaces": codespaces}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def select_codespace(self, name):
        """Select a Codespace"""
        state.selected_codespace = name
        state.save_config()
        return {"success": True}

    def create_codespace(self):
        """Create a new Codespace"""
        if not state.github_token:
            return {"success": False, "error": "Not logged in"}

        try:
            data = json.dumps({
                "repository_id": None,  # Will be looked up
                "ref": "main"
            }).encode()

            # First get repo ID
            req = urllib.request.Request(
                f"https://api.github.com/repos/{CODESPACE_REPO}",
                headers={
                    "Authorization": f"Bearer {state.github_token}",
                    "Accept": "application/vnd.github+json"
                }
            )
            with urllib.request.urlopen(req) as response:
                repo_data = json.loads(response.read().decode())
                repo_id = repo_data["id"]

            # Create codespace
            create_data = json.dumps({
                "repository_id": repo_id,
                "ref": "main"
            }).encode()

            create_req = urllib.request.Request(
                "https://api.github.com/user/codespaces",
                data=create_data,
                headers={
                    "Authorization": f"Bearer {state.github_token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            with urllib.request.urlopen(create_req) as response:
                cs_data = json.loads(response.read().decode())

            return {
                "success": True,
                "name": cs_data["name"],
                "state": cs_data["state"]
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def launch_codespace(self):
        """Open Codespace in browser"""
        if not state.selected_codespace:
            return {"success": False, "error": "No Codespace selected"}

        url = f"https://github.com/codespaces/{state.selected_codespace}"
        webbrowser.open(url)
        return {"success": True}

    def push_metadata(self):
        """Push metadata to Codespace"""
        if not state.selected_codespace:
            return {"success": False, "error": "No Codespace selected"}
        if not state.project_folder:
            return {"success": False, "error": "No project folder selected"}

        meta_folder = os.path.join(state.project_folder, "app_folder", "meta_data")
        if not os.path.exists(meta_folder):
            meta_folder = os.path.join(state.project_folder, "meta_data")

        if not os.path.exists(meta_folder):
            return {"success": False, "error": "meta_data folder not found"}

        try:
            cmd = [
                "gh", "codespace", "cp",
                "-c", state.selected_codespace,
                "-r",
                meta_folder,
                f"remote:{REMOTE_PATH}/meta_data"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return {"success": True}
            else:
                return {"success": False, "error": result.stderr or "Push failed"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Push timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pull_scripts(self):
        """Pull scripts from Codespace"""
        if not state.selected_codespace:
            return {"success": False, "error": "No Codespace selected"}
        if not state.project_folder:
            return {"success": False, "error": "No project folder selected"}

        local_scripts = os.path.join(state.project_folder, "app_folder", "scripts")
        os.makedirs(local_scripts, exist_ok=True)

        try:
            cmd = [
                "gh", "codespace", "cp",
                "-c", state.selected_codespace,
                "-r",
                f"remote:{REMOTE_PATH}/scripts/",
                local_scripts
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                files = [f for f in os.listdir(local_scripts) if f.endswith('.py')]
                return {"success": True, "files": files}
            else:
                if "no such file" in result.stderr.lower():
                    return {"success": False, "error": "No scripts folder in Codespace yet"}
                return {"success": False, "error": result.stderr or "Pull failed"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Pull timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_scripts(self):
        """Run Python scripts locally"""
        if not state.project_folder:
            return {"success": False, "error": "No project folder selected"}

        scripts_folder = os.path.join(state.project_folder, "app_folder", "scripts")
        if not os.path.exists(scripts_folder):
            return {"success": False, "error": "No scripts folder found"}

        py_files = [f for f in os.listdir(scripts_folder) if f.endswith('.py')]
        if not py_files:
            return {"success": False, "error": "No Python scripts found"}

        # Create output folder
        output_folder = os.path.join(state.project_folder, "output_folder")
        os.makedirs(output_folder, exist_ok=True)

        results = []
        for script in py_files:
            script_path = os.path.join(scripts_folder, script)
            try:
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    cwd=state.project_folder,
                    timeout=300
                )
                results.append({
                    "script": script,
                    "success": result.returncode == 0,
                    "output": result.stdout[:500] if result.stdout else "",
                    "error": result.stderr[:500] if result.stderr else ""
                })
            except subprocess.TimeoutExpired:
                results.append({"script": script, "success": False, "error": "Timed out"})
            except Exception as e:
                results.append({"script": script, "success": False, "error": str(e)})

        return {"success": True, "results": results}


# HTML/CSS/JS for the UI
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>VibeFoundry Bridge</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }

        .container {
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            max-width: 400px;
            margin: 0 auto;
        }

        h1 {
            font-size: 24px;
            margin-bottom: 4px;
            color: #333;
        }

        .subtitle {
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
        }

        .section {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }

        .section:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }

        .section-title {
            font-size: 12px;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 10px;
            font-weight: 600;
        }

        .status-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ccc;
        }

        .status-dot.green { background: #22c55e; }
        .status-dot.yellow { background: #eab308; }
        .status-dot.red { background: #ef4444; }

        .btn {
            display: block;
            width: 100%;
            padding: 14px 20px;
            border: none;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 10px;
        }

        .btn:last-child {
            margin-bottom: 0;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }

        .btn-secondary {
            background: #f3f4f6;
            color: #333;
        }

        .btn-secondary:hover:not(:disabled) {
            background: #e5e7eb;
        }

        .btn-success {
            background: #22c55e;
            color: white;
        }

        .btn-success:hover:not(:disabled) {
            background: #16a34a;
        }

        .btn-row {
            display: flex;
            gap: 10px;
        }

        .btn-row .btn {
            flex: 1;
        }

        select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            font-size: 14px;
            margin-bottom: 10px;
            background: white;
        }

        select:focus {
            outline: none;
            border-color: #667eea;
        }

        .folder-display {
            padding: 12px;
            background: #f9fafb;
            border-radius: 8px;
            font-size: 13px;
            color: #666;
            word-break: break-all;
            margin-bottom: 10px;
        }

        .login-code {
            text-align: center;
            padding: 20px;
            background: #f9fafb;
            border-radius: 10px;
            margin-bottom: 15px;
        }

        .login-code .code {
            font-size: 32px;
            font-weight: bold;
            letter-spacing: 4px;
            color: #667eea;
            font-family: monospace;
        }

        .login-code .hint {
            font-size: 13px;
            color: #666;
            margin-top: 8px;
        }

        .status-message {
            padding: 12px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 10px;
        }

        .status-message.success {
            background: #dcfce7;
            color: #166534;
        }

        .status-message.error {
            background: #fee2e2;
            color: #991b1b;
        }

        .status-message.info {
            background: #e0e7ff;
            color: #3730a3;
        }

        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #fff;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .hidden {
            display: none !important;
        }

        .user-info {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .user-info .username {
            font-weight: 600;
            color: #333;
        }

        .user-info .logout {
            font-size: 13px;
            color: #667eea;
            cursor: pointer;
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌉 VibeFoundry Bridge</h1>
        <p class="subtitle">Sync files with your Codespace</p>

        <!-- GitHub Auth Section -->
        <div class="section" id="auth-section">
            <div class="section-title">GitHub Account</div>

            <div id="logged-out" class="hidden">
                <div id="login-start">
                    <button class="btn btn-primary" onclick="startLogin()">
                        🔐 Login with GitHub
                    </button>
                </div>

                <div id="login-pending" class="hidden">
                    <div class="login-code">
                        <div class="code" id="user-code">----</div>
                        <div class="hint">Enter this code on GitHub</div>
                    </div>
                    <div class="status-message info">
                        <span class="loading"></span>
                        Waiting for authorization...
                    </div>
                </div>
            </div>

            <div id="logged-in" class="hidden">
                <div class="user-info">
                    <div>
                        <span class="status-dot green"></span>
                        <span class="username" id="username">@user</span>
                    </div>
                    <span class="logout" onclick="logout()">Logout</span>
                </div>
            </div>
        </div>

        <!-- Project Folder Section -->
        <div class="section" id="folder-section">
            <div class="section-title">Project Folder</div>
            <div class="folder-display" id="folder-display">No folder selected</div>
            <button class="btn btn-secondary" onclick="selectFolder()">
                📁 Select Folder
            </button>
        </div>

        <!-- Codespace Section -->
        <div class="section" id="codespace-section">
            <div class="section-title">Codespace</div>
            <select id="codespace-select" onchange="selectCodespace()">
                <option value="">Select a Codespace...</option>
            </select>
            <div class="btn-row">
                <button class="btn btn-secondary" onclick="refreshCodespaces()">
                    🔄 Refresh
                </button>
                <button class="btn btn-success" onclick="launchCodespace()" id="launch-btn" disabled>
                    🚀 Launch
                </button>
            </div>
        </div>

        <!-- Sync Section -->
        <div class="section" id="sync-section">
            <div class="section-title">Sync & Run</div>
            <div id="sync-status"></div>
            <div class="btn-row">
                <button class="btn btn-primary" onclick="pushMetadata()" id="push-btn">
                    📤 Push
                </button>
                <button class="btn btn-primary" onclick="pullScripts()" id="pull-btn">
                    📥 Pull
                </button>
            </div>
            <button class="btn btn-success" onclick="runScripts()" id="run-btn">
                ▶️ Run Scripts
            </button>
        </div>
    </div>

    <script>
        let pollInterval = null;

        async function init() {
            const state = await pywebview.api.get_state();
            updateUI(state);
            if (state.logged_in) {
                refreshCodespaces();
            }
        }

        function updateUI(state) {
            // Auth state
            if (state.logged_in) {
                document.getElementById('logged-out').classList.add('hidden');
                document.getElementById('logged-in').classList.remove('hidden');
                document.getElementById('username').textContent = '@' + state.username;
            } else {
                document.getElementById('logged-out').classList.remove('hidden');
                document.getElementById('logged-in').classList.add('hidden');
            }

            // Folder
            if (state.project_folder) {
                document.getElementById('folder-display').textContent = state.project_folder;
            }

            // gh CLI warning
            if (!state.gh_installed) {
                showStatus('⚠️ GitHub CLI (gh) not installed. Push/Pull will not work.', 'error');
            }
        }

        async function startLogin() {
            document.getElementById('login-start').classList.add('hidden');
            document.getElementById('login-pending').classList.remove('hidden');

            const result = await pywebview.api.start_github_login();

            if (result.success) {
                document.getElementById('user-code').textContent = result.user_code;

                // Start polling
                pollInterval = setInterval(async () => {
                    const pollResult = await pywebview.api.poll_github_login(
                        result.device_code,
                        result.interval
                    );

                    if (pollResult.success) {
                        clearInterval(pollInterval);
                        document.getElementById('logged-out').classList.add('hidden');
                        document.getElementById('logged-in').classList.remove('hidden');
                        document.getElementById('username').textContent = '@' + pollResult.username;
                        document.getElementById('login-start').classList.remove('hidden');
                        document.getElementById('login-pending').classList.add('hidden');
                        refreshCodespaces();
                    } else if (!pollResult.pending) {
                        clearInterval(pollInterval);
                        showStatus('Login failed: ' + pollResult.error, 'error');
                        document.getElementById('login-start').classList.remove('hidden');
                        document.getElementById('login-pending').classList.add('hidden');
                    }
                }, (result.interval || 5) * 1000);
            } else {
                showStatus('Login failed: ' + result.error, 'error');
                document.getElementById('login-start').classList.remove('hidden');
                document.getElementById('login-pending').classList.add('hidden');
            }
        }

        async function logout() {
            await pywebview.api.logout();
            document.getElementById('logged-out').classList.remove('hidden');
            document.getElementById('logged-in').classList.add('hidden');
            document.getElementById('codespace-select').innerHTML = '<option value="">Select a Codespace...</option>';
        }

        async function selectFolder() {
            const result = await pywebview.api.select_folder();
            if (result.success) {
                document.getElementById('folder-display').textContent = result.folder;
            }
        }

        async function refreshCodespaces() {
            const select = document.getElementById('codespace-select');
            select.innerHTML = '<option value="">Loading...</option>';

            const result = await pywebview.api.get_codespaces();

            if (result.success) {
                select.innerHTML = '<option value="">Select a Codespace...</option>';

                if (result.codespaces.length === 0) {
                    select.innerHTML += '<option value="_create">+ Create new Codespace</option>';
                } else {
                    for (const cs of result.codespaces) {
                        const state = cs.state === 'Available' ? '🟢' : '🟡';
                        select.innerHTML += `<option value="${cs.name}">${state} ${cs.name}</option>`;
                    }
                    select.innerHTML += '<option value="_create">+ Create new Codespace</option>';
                }
            } else {
                select.innerHTML = '<option value="">Error loading Codespaces</option>';
                showStatus('Error: ' + result.error, 'error');
            }
        }

        async function selectCodespace() {
            const select = document.getElementById('codespace-select');
            const value = select.value;

            if (value === '_create') {
                showStatus('Creating Codespace...', 'info');
                const result = await pywebview.api.create_codespace();
                if (result.success) {
                    showStatus('Codespace created! Refreshing...', 'success');
                    setTimeout(refreshCodespaces, 2000);
                } else {
                    showStatus('Failed to create: ' + result.error, 'error');
                }
                select.value = '';
            } else if (value) {
                await pywebview.api.select_codespace(value);
                document.getElementById('launch-btn').disabled = false;
            } else {
                document.getElementById('launch-btn').disabled = true;
            }
        }

        async function launchCodespace() {
            const result = await pywebview.api.launch_codespace();
            if (!result.success) {
                showStatus('Error: ' + result.error, 'error');
            }
        }

        async function pushMetadata() {
            const btn = document.getElementById('push-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Pushing...';

            const result = await pywebview.api.push_metadata();

            btn.disabled = false;
            btn.innerHTML = '📤 Push';

            if (result.success) {
                showStatus('✅ Metadata pushed successfully!', 'success');
            } else {
                showStatus('❌ ' + result.error, 'error');
            }
        }

        async function pullScripts() {
            const btn = document.getElementById('pull-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Pulling...';

            const result = await pywebview.api.pull_scripts();

            btn.disabled = false;
            btn.innerHTML = '📥 Pull';

            if (result.success) {
                showStatus(`✅ Pulled ${result.files.length} script(s)!`, 'success');
            } else {
                showStatus('❌ ' + result.error, 'error');
            }
        }

        async function runScripts() {
            const btn = document.getElementById('run-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Running...';

            const result = await pywebview.api.run_scripts();

            btn.disabled = false;
            btn.innerHTML = '▶️ Run Scripts';

            if (result.success) {
                const succeeded = result.results.filter(r => r.success).length;
                const total = result.results.length;
                showStatus(`✅ Ran ${succeeded}/${total} scripts. Check output_folder.`, 'success');
            } else {
                showStatus('❌ ' + result.error, 'error');
            }
        }

        function showStatus(message, type) {
            const statusDiv = document.getElementById('sync-status');
            statusDiv.innerHTML = `<div class="status-message ${type}">${message}</div>`;

            if (type === 'success') {
                setTimeout(() => {
                    statusDiv.innerHTML = '';
                }, 5000);
            }
        }

        // Initialize when pywebview is ready
        window.addEventListener('pywebviewready', init);
    </script>
</body>
</html>
"""


def get_screen_size():
    """Get screen dimensions"""
    try:
        if sys.platform == 'darwin':
            # macOS
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().frame()
            return int(frame.size.width), int(frame.size.height)
        elif sys.platform == 'win32':
            # Windows
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        else:
            # Linux - default
            return 1920, 1080
    except:
        return 1920, 1080


def main():
    api = BridgeAPI()

    # Get screen size and calculate position (bottom-right)
    screen_w, screen_h = get_screen_size()
    window_w, window_h = 420, 620
    x = screen_w - window_w - 40
    y = screen_h - window_h - 80

    window = webview.create_window(
        'VibeFoundry Bridge',
        html=HTML,
        js_api=api,
        width=window_w,
        height=window_h,
        x=x,
        y=y,
        resizable=False,
        on_top=False
    )

    api.set_window(window)

    webview.start()


if __name__ == '__main__':
    main()
