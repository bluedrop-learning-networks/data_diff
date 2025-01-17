import pytest
from pathlib import Path
from datacompare.datasource import (
    detect_file_format,
    create_data_source,
    CSVDataSource,
    JSONLDataSource
)

@pytest.fixture
def sample_csv(tmp_path):
    file = tmp_path / "test.csv"
    content = "id,name,value\n1,test,100\n2,test2,200"
    file.write_text(content)
    return str(file)

@pytest.fixture
def sample_jsonl(tmp_path):
    file = tmp_path / "test.jsonl"
    content = '{"id": 1, "name": "test", "value": 100}\n{"id": 2, "name": "test2", "value": 200}'
    file.write_text(content)
    return str(file)

def test_detect_csv_by_extension(sample_csv):
    assert detect_file_format(sample_csv) == 'csv'

def test_detect_jsonl_by_extension(sample_jsonl):
    assert detect_file_format(sample_jsonl) == 'jsonl'

def test_detect_csv_by_content(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("a,b,c\n1,2,3")
    assert detect_file_format(str(file)) == 'csv'

def test_detect_jsonl_by_content(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text('{"a": 1}\n{"b": 2}')
    assert detect_file_format(str(file)) == 'jsonl'

def test_csv_data_source(sample_csv):
    ds = CSVDataSource(sample_csv)
    assert ds.columns == ['id', 'name', 'value']
    rows = list(ds)
    assert len(rows) == 2
    assert rows[0]['name'] == 'test'

def test_jsonl_data_source(sample_jsonl):
    ds = JSONLDataSource(sample_jsonl)
    assert ds.columns == ['id', 'name', 'value']
    rows = list(ds)
    assert len(rows) == 2
    assert rows[0]['name'] == 'test'

def test_csv_custom_delimiter(tmp_path):
    file = tmp_path / "test.csv"
    file.write_text("id;name;value\n1;test;100")
    ds = CSVDataSource(str(file), delimiter=';')
    rows = list(ds)
    assert rows[0]['name'] == 'test'

def test_factory_creates_correct_source(sample_csv, sample_jsonl):
    csv_ds = create_data_source(sample_csv)
    jsonl_ds = create_data_source(sample_jsonl)
    assert isinstance(csv_ds, CSVDataSource)
    assert isinstance(jsonl_ds, JSONLDataSource)
