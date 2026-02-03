#!/bin/bash
# VibeFoundry CodeSpace Bridge Launcher for Mac

cd "$(dirname "$0")"

# Check if pywebview is installed
python3 -c "import webview" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip3 install pywebview
fi

python3 bridge.py
