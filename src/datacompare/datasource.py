import csv
import json
from pathlib import Path
from typing import Iterator, Dict, Any

def detect_file_format(file_path: str) -> str:
    """Detect if a file is CSV or JSONL format.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        'csv' or 'jsonl'
        
    Raises:
        ValueError: If format cannot be determined
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    # Check file extension first
    if path.suffix.lower() in ('.csv'):
        return 'csv'
    if path.suffix.lower() in ('.jsonl', '.ndjson'):
        return 'jsonl'
        
    # If extension doesn't help, peek at content
    with path.open('r') as f:
        first_line = f.readline().strip()
        
        # Check if it looks like JSON
        try:
            json.loads(first_line)
            return 'jsonl'
        except json.JSONDecodeError:
            pass
            
        # Check if it looks like CSV
        if ',' in first_line:
            return 'csv'
            
    raise ValueError(f"Unable to determine format of {file_path}")

class DataSource:
    """Abstract base class for data sources"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError
        
    @property
    def columns(self) -> list[str]:
        raise NotImplementedError

class CSVDataSource(DataSource):
    """CSV file data source"""
    
    def __init__(self, file_path: str, delimiter: str = ','):
        super().__init__(file_path)
        self.delimiter = delimiter
        self._columns = None
        
    @property
    def columns(self) -> list[str]:
        if self._columns is None:
            with open(self.file_path, 'r') as f:
                reader = csv.reader(f, delimiter=self.delimiter)
                self._columns = next(reader)
        return self._columns
        
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        with open(self.file_path, 'r') as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            for row in reader:
                yield row

class JSONLDataSource(DataSource):
    """JSONL file data source"""
    
    def __init__(self, file_path: str):
        super().__init__(file_path)
        self._columns = None
        
    @property
    def columns(self) -> list[str]:
        if self._columns is None:
            # Get columns from first line
            with open(self.file_path, 'r') as f:
                first_line = f.readline()
                first_record = json.loads(first_line)
                self._columns = list(first_record.keys())
        return self._columns
        
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        with open(self.file_path, 'r') as f:
            for line in f:
                yield json.loads(line)

def create_data_source(file_path: str, delimiter: str = ',') -> DataSource:
    """Factory function to create appropriate data source based on file format"""
    format = detect_file_format(file_path)
    if format == 'csv':
        return CSVDataSource(file_path, delimiter)
    elif format == 'jsonl':
        return JSONLDataSource(file_path)
    raise ValueError(f"Unsupported format: {format}")
