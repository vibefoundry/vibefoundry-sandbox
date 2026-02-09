# VibeFoundry Sandbox

GitHub Codespace environment for running Claude Code with VibeFoundry IDE.

## Structure

```
├── app_folder/           # Working directory for Claude
│   ├── sync_server.py    # HTTP server for browser sync
│   ├── metadatafarmer.py # Metadata generation
│   ├── meta_data/        # File metadata for Claude
│   └── scripts/          # User scripts
├── input_folder/         # Input data files
└── output_folder/        # Script outputs
```

## Usage

This repo is used as a Codespace that connects to the VibeFoundry IDE desktop app.

1. Create a Codespace from this repo
2. Start the sync server: `cd app_folder && python sync_server.py`
3. Connect from VibeFoundry IDE using the forwarded port URL
