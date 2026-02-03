# VibeFoundry Helper Launcher for Windows
# Double-click this file to run the helper (no console window)

import os
import sys

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run the main helper
exec(open("vibefoundry_helper.py").read())
