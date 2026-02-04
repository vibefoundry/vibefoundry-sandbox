# Project Context

You are working inside `app_folder/`.

## IMPORTANT: Folder Access Rules

**NEVER access `../input_folder/` or `../output_folder/` directly.**

- Do NOT read files from input_folder
- Do NOT list files in input_folder or output_folder
- Do NOT browse or explore those directories

Instead, read `meta_data/input_metadata.txt` to understand what data is available.

## Folder Structure

```
project_folder/
├── input_folder/      <- DO NOT ACCESS
├── output_folder/     <- DO NOT ACCESS
└── app_folder/        <- You are here - stay here
    ├── meta_data/     <- Read this for file info
    └── scripts/       <- Save Python scripts here
```

## How to Work

1. **Read `meta_data/input_metadata.txt`** to see available files, columns, and data types
2. **Write Python scripts** using the template below
3. **Save scripts to `scripts/`**
4. **Run the scripts** - the scripts will access the folders, not you

## IMPORTANT: Script Template

**ALWAYS use this template** for scripts so they work from any directory:

```python
import os
import pandas as pd

# Get absolute paths (works from any directory)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
INPUT_FOLDER = os.path.join(PROJECT_DIR, "input_folder")
OUTPUT_FOLDER = os.path.join(PROJECT_DIR, "output_folder")

# Read input files using absolute paths
df = pd.read_csv(os.path.join(INPUT_FOLDER, "your_file.csv"))

# Save output files using absolute paths
df.to_csv(os.path.join(OUTPUT_FOLDER, "result.csv"), index=False)
```

**NEVER use relative paths like `../input_folder/`** - they break when scripts are run from different directories.

## Metadata

Run `python metadatafarmer.py` to refresh metadata after new files are added.

The metadata files contain:
- File names
- Row counts
- Column names and data types
