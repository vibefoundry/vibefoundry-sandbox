#!/usr/bin/env python3
"""
VibeFoundry Helper - A simple UI for syncing files with GitHub Codespaces

This script provides a graphical interface for:
- Pushing metadata to your Codespace
- Pulling scripts from your Codespace
- Running scripts locally
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import sys
import json
import threading

class VibeFoundryHelper:
    def __init__(self, root):
        self.root = root
        self.root.title("VibeFoundry Helper")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        # Set working directory to where the script is located
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # Config file for remembering settings
        self.config_file = os.path.join(self.script_dir, ".helper_config.json")
        self.config = self.load_config()

        # Codespace info
        self.codespace_name = None
        self.remote_path = "/workspaces/vibefoundry-sandbox"

        self.setup_ui()
        self.check_prerequisites()

    def load_config(self):
        """Load saved configuration."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"project_folder": self.script_dir}

    def save_config(self):
        """Save configuration."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f)
        except:
            pass

    def setup_ui(self):
        """Create the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="VibeFoundry Helper", font=("Helvetica", 18, "bold"))
        title_label.pack(pady=(0, 5))

        # Subtitle
        subtitle_label = ttk.Label(main_frame, text="Sync files with your Codespace", font=("Helvetica", 10))
        subtitle_label.pack(pady=(0, 20))

        # Project folder selection
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(folder_frame, text="Project Folder:").pack(anchor=tk.W)

        folder_select_frame = ttk.Frame(folder_frame)
        folder_select_frame.pack(fill=tk.X, pady=(5, 0))

        self.folder_var = tk.StringVar(value=self.config.get("project_folder", ""))
        self.folder_entry = ttk.Entry(folder_select_frame, textvariable=self.folder_var, state="readonly")
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        browse_btn = ttk.Button(folder_select_frame, text="Browse", command=self.browse_folder)
        browse_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Codespace status
        self.codespace_label = ttk.Label(main_frame, text="Codespace: Checking...", font=("Helvetica", 9))
        self.codespace_label.pack(pady=(0, 20))

        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)

        # Style for bigger buttons
        style = ttk.Style()
        style.configure("Big.TButton", padding=(20, 15), font=("Helvetica", 11))

        # Push Metadata button
        self.push_btn = ttk.Button(
            buttons_frame,
            text="📤  Push Metadata to Codespace",
            style="Big.TButton",
            command=self.push_metadata
        )
        self.push_btn.pack(fill=tk.X, pady=5)

        # Pull Scripts button
        self.pull_btn = ttk.Button(
            buttons_frame,
            text="📥  Pull Scripts from Codespace",
            style="Big.TButton",
            command=self.pull_scripts
        )
        self.pull_btn.pack(fill=tk.X, pady=5)

        # Run Scripts button
        self.run_btn = ttk.Button(
            buttons_frame,
            text="▶️  Run Scripts Locally",
            style="Big.TButton",
            command=self.run_scripts
        )
        self.run_btn.pack(fill=tk.X, pady=5)

        # Status area
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        ttk.Label(status_frame, text="Status:").pack(anchor=tk.W)

        self.status_text = tk.Text(status_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        self.status_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Scrollbar for status
        scrollbar = ttk.Scrollbar(self.status_text, command=self.status_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=scrollbar.set)

    def log_status(self, message, clear=False):
        """Add message to status area."""
        self.status_text.config(state=tk.NORMAL)
        if clear:
            self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update()

    def browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(
            title="Select Project Folder",
            initialdir=self.config.get("project_folder", os.path.expanduser("~"))
        )
        if folder:
            self.folder_var.set(folder)
            self.config["project_folder"] = folder
            self.save_config()
            self.log_status(f"Project folder set to: {folder}", clear=True)

    def check_prerequisites(self):
        """Check if gh CLI is installed and authenticated."""
        def check():
            # Check gh is installed
            try:
                result = subprocess.run(
                    ["gh", "--version"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.log_status("❌ GitHub CLI (gh) not found. Please install it first.")
                    return
            except FileNotFoundError:
                self.log_status("❌ GitHub CLI (gh) not found. Please install it first.")
                self.log_status("   Visit: https://cli.github.com")
                return

            # Check gh is authenticated
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                self.log_status("❌ Not logged in to GitHub CLI.")
                self.log_status("   Run: gh auth login")
                return

            self.log_status("✅ GitHub CLI ready")

            # Find codespace
            self.find_codespace()

        threading.Thread(target=check, daemon=True).start()

    def find_codespace(self):
        """Find the active vibefoundry-sandbox codespace."""
        try:
            result = subprocess.run(
                ["gh", "codespace", "list", "--json", "name,repository,state"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.log_status("❌ Failed to list codespaces")
                return

            codespaces = json.loads(result.stdout)

            # Filter for vibefoundry-sandbox
            matching = [
                cs for cs in codespaces
                if "vibefoundry-sandbox" in cs.get("repository", "")
                and cs.get("state") == "Available"
            ]

            if not matching:
                # Check for any vibefoundry-sandbox codespace (might need to start)
                matching = [
                    cs for cs in codespaces
                    if "vibefoundry-sandbox" in cs.get("repository", "")
                ]

            if matching:
                self.codespace_name = matching[0]["name"]
                state = matching[0].get("state", "Unknown")
                self.codespace_label.config(
                    text=f"Codespace: {self.codespace_name[:30]}... ({state})"
                )
                self.log_status(f"✅ Found Codespace: {self.codespace_name}")
            else:
                self.codespace_label.config(text="Codespace: Not found")
                self.log_status("❌ No vibefoundry-sandbox Codespace found")
                self.log_status("   Create one at: https://codespaces.new/vibefoundry/vibefoundry-sandbox")

        except Exception as e:
            self.log_status(f"❌ Error finding codespace: {e}")

    def set_buttons_state(self, state):
        """Enable or disable all action buttons."""
        self.push_btn.config(state=state)
        self.pull_btn.config(state=state)
        self.run_btn.config(state=state)

    def push_metadata(self):
        """Push metadata folder to Codespace."""
        if not self.codespace_name:
            messagebox.showerror("Error", "No Codespace found. Please create one first.")
            return

        project_folder = self.folder_var.get()
        if not project_folder:
            messagebox.showerror("Error", "Please select a project folder first.")
            return

        meta_folder = os.path.join(project_folder, "app_folder", "meta_data")
        if not os.path.exists(meta_folder):
            # Try alternate location
            meta_folder = os.path.join(project_folder, "meta_data")

        if not os.path.exists(meta_folder):
            messagebox.showerror("Error", f"meta_data folder not found in project folder.")
            return

        def do_push():
            self.set_buttons_state(tk.DISABLED)
            self.log_status("📤 Pushing metadata to Codespace...", clear=True)

            try:
                # Push meta_data folder
                cmd = [
                    "gh", "codespace", "cp",
                    "-c", self.codespace_name,
                    "-r",  # recursive
                    meta_folder,
                    f"remote:{self.remote_path}/meta_data"
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    self.log_status("✅ Metadata pushed successfully!")
                else:
                    self.log_status(f"❌ Push failed: {result.stderr}")

            except Exception as e:
                self.log_status(f"❌ Error: {e}")

            finally:
                self.set_buttons_state(tk.NORMAL)

        threading.Thread(target=do_push, daemon=True).start()

    def pull_scripts(self):
        """Pull scripts folder from Codespace."""
        if not self.codespace_name:
            messagebox.showerror("Error", "No Codespace found. Please create one first.")
            return

        project_folder = self.folder_var.get()
        if not project_folder:
            messagebox.showerror("Error", "Please select a project folder first.")
            return

        def do_pull():
            self.set_buttons_state(tk.DISABLED)
            self.log_status("📥 Pulling scripts from Codespace...", clear=True)

            try:
                # Create local scripts folder if needed
                local_scripts = os.path.join(project_folder, "app_folder", "scripts")
                os.makedirs(local_scripts, exist_ok=True)

                # Pull scripts folder
                cmd = [
                    "gh", "codespace", "cp",
                    "-c", self.codespace_name,
                    "-r",  # recursive
                    f"remote:{self.remote_path}/scripts/",
                    local_scripts
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    # List pulled files
                    files = os.listdir(local_scripts) if os.path.exists(local_scripts) else []
                    py_files = [f for f in files if f.endswith('.py')]
                    self.log_status(f"✅ Scripts pulled successfully!")
                    self.log_status(f"   Found {len(py_files)} Python file(s)")
                    for f in py_files[:5]:  # Show first 5
                        self.log_status(f"   - {f}")
                    if len(py_files) > 5:
                        self.log_status(f"   ... and {len(py_files) - 5} more")
                else:
                    if "no such file or directory" in result.stderr.lower():
                        self.log_status("⚠️ No scripts folder in Codespace yet.")
                        self.log_status("   Ask Claude to create scripts first!")
                    else:
                        self.log_status(f"❌ Pull failed: {result.stderr}")

            except Exception as e:
                self.log_status(f"❌ Error: {e}")

            finally:
                self.set_buttons_state(tk.NORMAL)

        threading.Thread(target=do_pull, daemon=True).start()

    def run_scripts(self):
        """Run Python scripts locally."""
        project_folder = self.folder_var.get()
        if not project_folder:
            messagebox.showerror("Error", "Please select a project folder first.")
            return

        scripts_folder = os.path.join(project_folder, "app_folder", "scripts")
        if not os.path.exists(scripts_folder):
            messagebox.showerror("Error", "No scripts folder found. Pull scripts first!")
            return

        py_files = [f for f in os.listdir(scripts_folder) if f.endswith('.py')]
        if not py_files:
            messagebox.showerror("Error", "No Python scripts found in scripts folder.")
            return

        def do_run():
            self.set_buttons_state(tk.DISABLED)
            self.log_status("▶️ Running scripts...", clear=True)

            # Create output folder if needed
            output_folder = os.path.join(project_folder, "output_folder")
            os.makedirs(output_folder, exist_ok=True)

            for script in py_files:
                script_path = os.path.join(scripts_folder, script)
                self.log_status(f"\n📄 Running {script}...")

                try:
                    result = subprocess.run(
                        [sys.executable, script_path],
                        capture_output=True,
                        text=True,
                        cwd=project_folder,
                        timeout=300  # 5 minute timeout
                    )

                    if result.stdout:
                        for line in result.stdout.strip().split('\n')[:10]:
                            self.log_status(f"   {line}")

                    if result.returncode == 0:
                        self.log_status(f"   ✅ {script} completed")
                    else:
                        self.log_status(f"   ❌ {script} failed")
                        if result.stderr:
                            for line in result.stderr.strip().split('\n')[:5]:
                                self.log_status(f"   {line}")

                except subprocess.TimeoutExpired:
                    self.log_status(f"   ⏱️ {script} timed out (5 min limit)")
                except Exception as e:
                    self.log_status(f"   ❌ Error running {script}: {e}")

            self.log_status(f"\n✅ All scripts finished!")
            self.log_status(f"   Check output_folder for results")
            self.set_buttons_state(tk.NORMAL)

        threading.Thread(target=do_run, daemon=True).start()


def main():
    root = tk.Tk()
    app = VibeFoundryHelper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
