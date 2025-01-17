import pytest
import json
import pandas as pd
from datacompare.comparison_engine import ComparisonResult
from datacompare.report_generator import ReportGenerator

@pytest.fixture
def sample_result():
    return ComparisonResult(
        unique_to_source1=pd.DataFrame([{'id': 1}, {'id': 2}]),
        unique_to_source2=pd.DataFrame([{'id': 3}]),
        differences=pd.DataFrame([{'id': 4, 'source1_value': 'A', 'source2_value': 'B'}]),
        column_stats={'name': 0.75, 'value': 0.90}
    )

def test_generate_summary(sample_result):
    generator = ReportGenerator(sample_result)
    summary = generator.generate_summary()
    
    assert summary['row_counts']['unique_to_source1'] == 2
    assert summary['row_counts']['unique_to_source2'] == 1
    assert summary['row_counts']['differences'] == 1
    
    assert summary['column_statistics']['name']['match_percentage'] == '75.0%'
    assert summary['column_statistics']['value']['match_percentage'] == '90.0%'

def test_console_output(sample_result):
    generator = ReportGenerator(sample_result)
    output = generator.to_console()
    
    assert 'Comparison Summary' in output
    assert 'Unique to source 1: 2' in output
    assert 'Match: 75.0%' in output

def test_json_output(sample_result, tmp_path):
    generator = ReportGenerator(sample_result)
    
    # Test string output
    json_str = generator.to_json()
    data = json.loads(json_str)
    assert data['row_counts']['unique_to_source1'] == 2
    
    # Test file output
    output_file = tmp_path / "report.json"
    generator.to_json(str(output_file))
    assert output_file.exists()
    
    with output_file.open() as f:
        data = json.load(f)
        assert data['row_counts']['unique_to_source1'] == 2

def test_csv_output(sample_result, tmp_path):
    generator = ReportGenerator(sample_result)
    output_file = tmp_path / "report.csv"
    
    generator.to_csv(str(output_file))
    assert output_file.exists()
    
    with output_file.open() as f:
        content = f.read()
        assert 'Row Counts' in content
        assert 'Column Statistics' in content
