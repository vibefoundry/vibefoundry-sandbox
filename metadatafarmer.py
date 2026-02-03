import os
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FOLDER = os.path.join(BASE_DIR, 'input_folder')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output_folder')
META_DATA_FOLDER = os.path.join(BASE_DIR, 'app_folder', 'meta_data')


def get_csv_metadata(filepath, base_folder):
    """Extract metadata from a single CSV file."""
    stat = os.stat(filepath)
    df_sample = pd.read_csv(filepath, nrows=100)
    row_count = sum(1 for _ in open(filepath, 'r', encoding='utf-8')) - 1

    # Get relative path from base folder
    rel_path = os.path.relpath(filepath, base_folder)

    columns_info = []
    for col in df_sample.columns:
        dtype = str(df_sample[col].dtype)
        columns_info.append(f"    - {col} ({dtype})")

    return {
        'filepath': rel_path,
        'file_size_mb': round(stat.st_size / (1024 * 1024), 2),
        'row_count': row_count,
        'column_count': len(df_sample.columns),
        'columns': columns_info
    }


def format_file_metadata(meta):
    """Format metadata for a single file as readable text."""
    lines = [
        f"File: {meta['filepath']}",
        f"  Size: {meta['file_size_mb']} MB",
        f"  Rows: {meta['row_count']:,}",
        f"  Columns ({meta['column_count']}):",
    ]
    lines.extend(meta['columns'])
    return '\n'.join(lines)


def scan_folder(folder_path):
    """Recursively scan a folder and return formatted metadata for all CSV files."""
    if not os.path.exists(folder_path):
        return f"Folder does not exist: {folder_path}"

    csv_files = []
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith('.csv'):
                csv_files.append(os.path.join(root, filename))

    if not csv_files:
        return "No CSV files found."

    results = []
    for filepath in sorted(csv_files):
        rel_path = os.path.relpath(filepath, folder_path)
        try:
            meta = get_csv_metadata(filepath, folder_path)
            results.append(format_file_metadata(meta))
            print(f"  Scanned: {rel_path}")
        except Exception as e:
            results.append(f"File: {rel_path}\n  Error: {e}")
            print(f"  Error scanning {rel_path}: {e}")

    return '\n\n'.join(results)


def main():
    os.makedirs(META_DATA_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("Scanning input_folder...")
    input_content = scan_folder(INPUT_FOLDER)
    input_meta_path = os.path.join(META_DATA_FOLDER, 'input_metadata.txt')
    with open(input_meta_path, 'w') as f:
        f.write(f"Input Folder Metadata\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"{'=' * 50}\n\n")
        f.write(input_content)
    print(f"Saved: {input_meta_path}\n")

    print("Scanning output_folder...")
    output_content = scan_folder(OUTPUT_FOLDER)
    output_meta_path = os.path.join(META_DATA_FOLDER, 'output_metadata.txt')
    with open(output_meta_path, 'w') as f:
        f.write(f"Output Folder Metadata\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"{'=' * 50}\n\n")
        f.write(output_content)
    print(f"Saved: {output_meta_path}\n")

    print("Metadata farming complete.")


if __name__ == '__main__':
    main()
