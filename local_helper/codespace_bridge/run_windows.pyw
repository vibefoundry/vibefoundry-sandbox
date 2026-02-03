# VibeFoundry CodeSpace Bridge Launcher for Windows
# Double-click this file to run (no console window)

import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Check if pywebview is installed
try:
    import webview
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])

# Run the bridge
exec(open("bridge.py").read())
