====================================
VibeFoundry Helper - Quick Start
====================================

This tool helps you sync files between your local computer and GitHub Codespaces.


FIRST TIME SETUP
----------------

1. Install GitHub CLI:
   - Mac: brew install gh
   - Windows: https://cli.github.com

2. Login to GitHub CLI (run this in terminal once):
   gh auth login

3. Create a Codespace:
   Visit: https://codespaces.new/vibefoundry/vibefoundry-sandbox


HOW TO RUN
----------

Mac:     Double-click "run_mac.command"
         (If blocked, right-click → Open → Open Anyway)

Windows: Double-click "run_windows.pyw"

Or run from terminal:
   python vibefoundry_helper.py


HOW TO USE
----------

1. Click "Browse" to select your project folder
   (The folder containing input_folder, output_folder, app_folder)

2. Click "Push Metadata" to upload your metadata to the Codespace

3. Do your work in Codespace with Claude Code

4. Click "Pull Scripts" to download the scripts Claude created

5. Click "Run Scripts" to execute them locally on your data


FOLDER STRUCTURE
----------------

Your project folder should look like this:

project_folder/
├── input_folder/      ← Your CSV data files
├── output_folder/     ← Results will appear here
└── app_folder/
    ├── meta_data/     ← Metadata files to push
    └── scripts/       ← Scripts will be pulled here


TROUBLESHOOTING
---------------

"gh not found"
  → Install GitHub CLI: https://cli.github.com

"Not logged in"
  → Run: gh auth login

"No Codespace found"
  → Create one: https://codespaces.new/vibefoundry/vibefoundry-sandbox

"No scripts folder"
  → Ask Claude to create scripts in the Codespace first!
