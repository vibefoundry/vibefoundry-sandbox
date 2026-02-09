# Project Context

You are working inside a **virtual environment** in `app_folder/`. The raw data files are stored locally on the user's machine and are not directly accessible to you.

## CRITICAL: Never Run Scripts

**DO NOT run Python scripts.** You can only write them. The user will run the scripts locally where the data exists.

## CRITICAL: Folder Access Rules

**NEVER access `../input_folder/` or `../output_folder/` directly.**

- Do NOT read files from input_folder
- Do NOT list files in input_folder or output_folder
- Do NOT browse or explore those directories

## How to Understand the Data

When asked ANY question about the data (what's in it, what columns exist, what the data looks like, etc.):

1. **Read `meta_data/input_metadata.txt`** - This contains descriptions of all available files, their columns, data types, and sample values
2. Use this metadata to understand what data is available without accessing the raw files

## Answering Questions About Data

When asked a question that requires analyzing the data (e.g., "What are the top 10 states for sales?", "Which customers are most likely to churn?", "Show me the monthly trends"):

**ALWAYS respond with a Python script** that:
1. Reads the relevant input file(s)
2. Performs the analysis
3. **Saves the result as a CSV to output_folder** (REQUIRED)

**Whenever you create a Python script to answer a question, always ensure that it has a dataframe output saved to the output_folder.** This is how the user sees the results.

Do NOT attempt to answer data questions directly - you cannot see the raw data. Instead, write a script that will produce the answer when the user runs it.

## Creating Graphs

When a user asks for a graph or visualization, create a Python script that outputs:
1. **A PNG image** of the graph saved to `output_folder/`
2. **A CSV file** with the underlying data that supports the graph

### CRITICAL: Preventing Labels from Getting Cut Off

**ALWAYS follow these rules to ensure labels are fully visible:**

1. **Use `bbox_inches='tight'`** in `savefig()` - This automatically expands the saved image to include all labels
2. **Use `plt.tight_layout()`** before saving - Adjusts subplot params to fit the figure
3. **Add padding with `pad_inches`** - Extra margin around the figure
4. **Rotate long x-axis labels** - Use `plt.xticks(rotation=45, ha='right')` for long category names
5. **Use adequate figure size** - `figsize=(12, 8)` or larger for complex charts

### Graph Template (Use This Exactly)

```python
import os
import pandas as pd
import matplotlib.pyplot as plt

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
INPUT_FOLDER = os.path.join(PROJECT_DIR, "input_folder")
OUTPUT_FOLDER = os.path.join(PROJECT_DIR, "output_folder")

# Read and process data
df = pd.read_csv(os.path.join(INPUT_FOLDER, "your_file.csv"))
chart_data = df.groupby("category")["value"].sum().reset_index()

# Save the underlying data as CSV
chart_data.to_csv(os.path.join(OUTPUT_FOLDER, "chart_data.csv"), index=False)

# Create figure with good size
fig, ax = plt.subplots(figsize=(12, 8))

# Create the chart
ax.bar(chart_data["category"], chart_data["value"])

# Add labels and title
ax.set_title("Your Chart Title", fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel("Category", fontsize=12)
ax.set_ylabel("Value", fontsize=12)

# Rotate x-axis labels if they're long (IMPORTANT for readability)
plt.xticks(rotation=45, ha='right')

# Ensure everything fits - BOTH of these are important
plt.tight_layout()

# Save with bbox_inches='tight' to prevent ANY label cutoff
plt.savefig(
    os.path.join(OUTPUT_FOLDER, "chart.png"),
    dpi=150,
    bbox_inches='tight',  # CRITICAL: expands image to fit all labels
    pad_inches=0.3,       # Extra padding around edges
    facecolor='white'     # White background
)
plt.close()

print(f"Saved chart to {os.path.join(OUTPUT_FOLDER, 'chart.png')}")
print(f"Saved data to {os.path.join(OUTPUT_FOLDER, 'chart_data.csv')}")
```

### Common Graph Types

**Line Chart:**
```python
ax.plot(x_data, y_data, marker='o', linewidth=2)
```

**Bar Chart:**
```python
ax.bar(categories, values)
# For horizontal: ax.barh(categories, values)
```

**Pie Chart:**
```python
ax.pie(values, labels=labels, autopct='%1.1f%%')
ax.axis('equal')  # Equal aspect ratio for circular pie
```

**Scatter Plot:**
```python
ax.scatter(x_data, y_data, alpha=0.6)
```

## Folder Structure

```
project_folder/
├── input_folder/      <- DO NOT ACCESS (local data)
├── output_folder/     <- Scripts save results here
└── app_folder/        <- You are here
    ├── meta_data/     <- Read this to understand available data
    └── scripts/       <- Save Python scripts here
```

## Script Template

**ALWAYS use this template** so scripts work from any directory:

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

# Perform analysis
result = df.groupby("column").sum()

# ALWAYS save result to output folder
result.to_csv(os.path.join(OUTPUT_FOLDER, "result.csv"), index=False)
print(f"Saved result to {os.path.join(OUTPUT_FOLDER, 'result.csv')}")
```

**NEVER use relative paths like `../input_folder/`** - they break when scripts are run from different directories.

## Refreshing Metadata

Run `python metadatafarmer.py` to refresh metadata after new files are added.

The metadata files contain:
- Absolute paths for each file
- File names and row counts
- Column names and data types
- Sample values
