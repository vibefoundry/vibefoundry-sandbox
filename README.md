# VibeFoundry Sandbox

A pre-configured Codespace for vibe coding with Claude Code.

## Quick Start

1. Click the button below to launch a Codespace
2. Wait for the environment to load (Claude Code is pre-installed)
3. Upload your metadata files to `meta_data/`
4. Run `claude` in the terminal to start vibe coding
5. Download your output files when done

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/YOUR-ORG/vibefoundry-sandbox)

## Workflow

1. **Upload metadata** - Drag your `input_metadata.txt` into the `meta_data/` folder
2. **Start Claude Code** - Run `claude` in the terminal
3. **Prompt with context** - Claude Code will read `CLAUDE.md` and understand your data structure
4. **Generate scripts** - Ask Claude to create Python scripts in `scripts/`
5. **Run your code** - Execute the scripts in the Codespace
6. **Download results** - Right-click your output folder and download

## Files

- `CLAUDE.md` - Context file that tells Claude Code how to work
- `metadatafarmer.py` - Run this locally to generate metadata from your CSV files
- `meta_data/` - Upload your metadata files here
