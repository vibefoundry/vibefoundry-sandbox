# VibeFoundry CodeSpace Bridge

A native desktop app for syncing files between your local machine and GitHub Codespaces.

## Features

- 🔐 GitHub OAuth login (no need for separate `gh auth login`)
- 📂 Project folder selection
- 🚀 Launch Codespaces directly from the app
- 📤 Push metadata to Codespace
- 📥 Pull scripts from Codespace
- ▶️ Run scripts locally

## Requirements

- Python 3.8+
- GitHub CLI (`gh`) - for file sync operations
- `pywebview` - installed automatically on first run

## Installation

### Mac

1. Install GitHub CLI:
   ```bash
   brew install gh
   ```

2. Double-click `run_mac.command` to launch

### Windows

1. Install GitHub CLI from https://cli.github.com

2. Double-click `run_windows.pyw` to launch

## First Time Setup

1. Click "Login with GitHub"
2. Enter the code shown on github.com
3. Select your project folder
4. Select or create a Codespace
5. You're ready to sync!

## Usage

1. **Push Metadata** - Uploads `meta_data/` folder to your Codespace
2. **Pull Scripts** - Downloads `scripts/` folder from your Codespace
3. **Run Scripts** - Executes all Python scripts locally
4. **Launch** - Opens your Codespace in the browser
