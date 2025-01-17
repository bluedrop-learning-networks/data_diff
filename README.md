# datacompare

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

Basic comparison:
```bash
uv python -m datacompare file1.csv file2.jsonl
```

With mapping configuration:
```bash
uv python -m datacompare --mapping mapping.json file1.csv file2.csv
```

For more options:
```bash
uv python -m datacompare --help
```

## Development

Run tests:
```bash
uv pip run pytest
```
