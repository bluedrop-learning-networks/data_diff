# data_diff

A command-line tool for comparing two data sources (CSV/JSONL) and identifying differences.

## Installation

1. Clone the repository
2. Create and activate virtual environment:
```bash
uv venv
source .venv/bin/activate  # Unix/Mac
# OR
.\.venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
# Install main dependencies
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

## Usage

Compare two data files (supports CSV and JSONL formats):

```bash
uv run data_diff source.csv target.jsonl
```

### Options

- Compare specific columns using a mapping file:
```bash
uv run data_diff --mapping column-map.json source.csv target.csv
```

- Specify ID columns for matching records:
```bash
uv run data_diff --id-columns id,email source.csv target.csv
```

- Output differences to a file:
```bash
uv run data_diff --output diff-report.txt source.csv target.csv
```

- Show all available options:
```bash
uv run data_diff --help
```

### Column Mapping Format

The mapping file (JSON) specifies how columns correspond between files:

```json
{
    "source_column1": "target_column1",
    "source_column2": "target_column2"
}
```

### Output

The tool will show:
- Added records (in target but not source)
- Removed records (in source but not target)
- Modified records (matching IDs but different values)
- Summary statistics of differences found

## Development

Run tests:
```bash
uv run pytest
```
