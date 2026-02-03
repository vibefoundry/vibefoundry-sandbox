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
2. **Write Python scripts** that reference `../input_folder/` and `../output_folder/` in code
3. **Save scripts to `scripts/`**
4. **Run the scripts** - the scripts will access the folders, not you

## Metadata

Run `python metadatafarmer.py` to refresh metadata after new files are added.

The metadata files contain:
- File names
- Row counts
- Column names and data types
