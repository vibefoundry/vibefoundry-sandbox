# VibeFoundry IDE + Sandbox

A complete data science workflow environment with a local IDE and GitHub Codespace integration.

## Components

### Local IDE (`vibefoundry`)
A pip-installable desktop application that provides:
- File browser with Excel/CSV viewing (virtual scrolling for large datasets)
- Script runner with live output
- Automatic sync with GitHub Codespaces
- Terminal access to remote codespace

### Codespace Sync Server (`app_folder/sync_server.py`)
Runs in a GitHub Codespace to:
- Sync scripts and data between local machine and codespace
- Provide terminal access via WebSocket
- Keep the codespace alive during active sessions

## Quick Start

### 1. Install the IDE locally

```bash
pip install -e .
```

### 2. Launch a Codespace

Click "Code" > "Codespaces" > "Create codespace on main" in this repo.

The sync server starts automatically on port 8787.

### 3. Run the IDE

```bash
vibefoundry
```

Then:
1. Open your project folder (should contain `input_folder`, `output_folder`, `app_folder`)
2. Paste your codespace sync URL (shown in the codespace terminal)
3. Start syncing scripts and running them in the codespace

## Project Structure

```
vibefoundry-sandbox/
├── src/vibefoundry/          # Python package (local IDE)
│   ├── server.py             # FastAPI backend
│   ├── cli.py                # Command-line entry point
│   └── static/               # Built React frontend
├── frontend/                 # React frontend source
├── app_folder/               # Codespace working directory
│   ├── sync_server.py        # Sync server for codespace
│   ├── scripts/              # Python scripts
│   └── meta_data/            # Data metadata
├── input_folder/             # Input data files (local only)
├── output_folder/            # Script output files
└── .devcontainer/            # Codespace configuration
```

## Development

### Build the frontend

```bash
cd frontend
npm install
npm run build
```

### Run locally in dev mode

```bash
# Terminal 1: Frontend dev server
cd frontend && npm run dev

# Terminal 2: Python backend
python -m vibefoundry.cli
```

## How Sync Works

1. The local IDE monitors your project folder
2. Scripts in `app_folder/scripts/` are synced to the codespace
3. You can run scripts in the codespace via the terminal
4. Output files are synced back to your local machine
5. Metadata is generated from your local data files and pushed to the codespace

This lets you work with large data files locally while running compute in the codespace.
