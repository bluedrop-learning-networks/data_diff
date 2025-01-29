import pytest
import json
import re
import polars as pl
from colorama import Fore, Style
from datacompare.comparison_engine import ComparisonResult
from datacompare.report_generator import ReportGenerator

def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

@pytest.fixture
def sample_result():
    return ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': 1}, {'id': 2}]),
        unique_to_source2=pl.DataFrame([{'id': 3}]),
        differences=pl.DataFrame([{
            'id': 4,
            'value_source1': 'A',
            'value_source2': 'B'
        }]),
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
    
    # Test basic summary
    output = strip_ansi(generator.to_console(show_diff=False))
    assert 'Comparison Summary' in output
    assert 'Unique to source 1:' in output
    assert '75.0%' in output
    
    # Test detailed diff
    output = strip_ansi(generator.to_console(show_diff=True))
    assert 'Detailed Differences' in output
    assert 'id=4' in output

def test_detailed_diff_formatting(sample_result):
    """Test the formatting of detailed differences"""
    # Create a result with specific test data
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([
            {'id': '1', 'name': 'Alice', 'value': '100'}
        ]),
        unique_to_source2=pl.DataFrame([
            {'id': '3', 'name': 'Charlie', 'value': '300'}
        ]),
        differences=pl.DataFrame([{
            'id': '2',
            'name_source1': 'Bob',
            'name_source2': 'Bob',
            'value_source1': '200',
            'value_source2': '250'
        }]),
        column_stats={'name': 0.75, 'value': 0.90}
    )
    
    generator = ReportGenerator(result)
    output = generator.to_console(show_diff=True)
    
    output = strip_ansi(output)
    # Check section headers
    assert "Rows Removed (Unique to Source 1):" in output
    assert "Rows Added (Unique to Source 2):" in output
    assert "Modified Rows:" in output
    
    # Check for values without exact formatting
    assert "200" in output
    assert "250" in output
    assert "id=2" in output

def test_color_highlighting(sample_result):
    """Test that color codes are properly applied"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([
            {'id': '1', 'name': 'Alice', 'value': '100'}
        ]),
        unique_to_source2=pl.DataFrame(),
        differences=pl.DataFrame([{
            'id': '2',
            'name_source1': 'Bob',
            'name_source2': 'Bob',
            'value_source1': '200',
            'value_source2': '250'
        }]),
        column_stats={'name': 1.0, 'value': 0.0}
    )
    
    generator = ReportGenerator(result)
    output = generator.to_console(show_diff=True)
    
    # Check for color codes
    assert Fore.RED in output  # Should be used for removed rows and source1 differences
    assert Fore.GREEN in output  # Should be used for added rows and source2 differences
    assert Style.BRIGHT in output  # Should be used for headers
    assert Style.RESET_ALL in output  # Should be used to reset formatting

def test_empty_differences():
    """Test output when there are no differences"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame(schema={'id': pl.Utf8, 'name': pl.Utf8}),
        unique_to_source2=pl.DataFrame(schema={'id': pl.Utf8, 'name': pl.Utf8}),
        differences=pl.DataFrame(),
        column_stats={'name': 1.0}
    )
    
    generator = ReportGenerator(result)
    output = strip_ansi(generator.to_console(show_diff=True))
    
    # Should still show headers but no diff content
    assert "=== Comparison Summary ===" in output
    assert "Rows with differences: 0" in output
    assert "Detailed Differences" not in output  # Should not show diff section if empty

def test_multicolumn_differences():
    """Test handling of rows with multiple column differences"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame(),
        unique_to_source2=pl.DataFrame(),
        differences=pl.DataFrame([{
            'id': '1',
            'name_source1': 'Alice',
            'name_source2': 'Alice',
            'age_source1': '30',
            'age_source2': '31',
            'city_source1': 'NY',
            'city_source2': 'LA'
        }]),
        column_stats={'name': 1.0, 'age': 0.0, 'city': 0.0}
    )
    
    generator = ReportGenerator(result)
    output = generator.to_console(show_diff=True)
    
    # Check that both different columns are highlighted
    assert 'age=' in output and '30' in output
    assert 'age=' in output and '31' in output
    assert 'city=' in output and 'NY' in output
    assert 'city=' in output and 'LA' in output
    assert 'name=' in output and 'Alice' in output  # Should appear without highlighting

def test_text_wrapping():
    long_text = "This is a very long text that should be wrapped across multiple lines"
    wrapped = ReportGenerator._wrap_text(long_text, 20)
    assert len(wrapped) > 1
    assert all(len(line) <= 20 for line in wrapped)

def test_console_output_formatting():
    """Test detailed console output formatting"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': '1', 'name': 'Alice'}]),
        unique_to_source2=pl.DataFrame([{'id': '2', 'name': 'Bob'}]),
        differences=pl.DataFrame([{
            'id': '3',
            'name_source1': 'Charlie',
            'name_source2': 'Charlie',
            'value_source1': '100',
            'value_source2': '200'
        }]),
        column_stats={'name': 1.0, 'value': 0.5}
    )
    
    generator = ReportGenerator(result)
    output = strip_ansi(generator.to_console(show_diff=True))
    
    # Check summary formatting
    assert "=== Comparison Summary ===" in output
    assert "Row Counts:" in output
    assert "Unique to source 1: 1" in output
    assert "Unique to source 2: 1" in output
    assert "Rows with differences: 1" in output
    
    # Check statistics formatting
    assert "Column Statistics:" in output
    assert "Match: 100.0%" in output
    assert "Match: 50.0%" in output
    
    # Check detailed diff formatting
    assert "=== Detailed Differences ===" in output
    assert "Rows Removed (Unique to Source 1):" in output
    assert "Rows Added (Unique to Source 2):" in output
    assert "Modified Rows:" in output
    assert "id=3" in output
    assert "value=100" in output
    assert "value=200" in output

def test_csv_output_structure(tmp_path):
    """Test CSV output structure and content"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': '1', 'name': 'Alice'}]),
        unique_to_source2=pl.DataFrame([{'id': '2', 'name': 'Bob'}]),
        differences=pl.DataFrame([{
            'id': '3',
            'name_source1': 'Charlie',
            'name_source2': 'Charlie',
            'value_source1': '100',
            'value_source2': '200'
        }]),
        column_stats={'name': 1.0, 'value': 0.5}
    )
    
    output_file = tmp_path / "report.csv"
    generator = ReportGenerator(result)
    generator.to_csv(str(output_file))
    
    # Read and check CSV content
    with open(output_file) as f:
        content = f.readlines()
        
    # Check headers and sections
    assert "=== Comparison Summary ===" in content[0]
    assert "Row Counts" in ''.join(content)
    assert "Column Statistics" in ''.join(content)
    
    # Check data rows
    csv_content = ''.join(content)
    assert "unique_to_source1,1" in csv_content
    assert "unique_to_source2,1" in csv_content
    assert "name,100.0%" in csv_content
    assert "value,50.0%" in csv_content
    
    # Check detailed differences
    assert "Modified Rows" in csv_content
    assert "id=3" in csv_content
    assert "100" in csv_content
    assert "200" in csv_content

def test_json_output_structure(tmp_path):
    """Test JSON output structure and content"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': '1', 'name': 'Alice'}]),
        unique_to_source2=pl.DataFrame([{'id': '2', 'name': 'Bob'}]),
        differences=pl.DataFrame([{
            'id': '3',
            'name_source1': 'Charlie',
            'name_source2': 'Charlie',
            'value_source1': '100',
            'value_source2': '200'
        }]),
        column_stats={'name': 1.0, 'value': 0.5}
    )
    
    # Test string output
    generator = ReportGenerator(result)
    json_str = generator.to_json()
    data = json.loads(json_str)
    
    # Check structure
    assert 'summary' in data
    assert 'details' in data
    assert 'row_counts' in data['summary']
    assert 'column_statistics' in data['summary']
    assert 'unique_to_source1' in data['details']
    assert 'unique_to_source2' in data['details']
    assert 'differences' in data['details']
    
    # Check content
    assert data['summary']['row_counts']['unique_to_source1'] == 1
    assert data['summary']['row_counts']['unique_to_source2'] == 1
    assert data['summary']['column_statistics']['name']['match_percentage'] == '100.0%'
    assert len(data['details']['differences']) == 1
    assert data['details']['differences'][0]['changes']['value']['source1'] == '100'
    assert data['details']['differences'][0]['changes']['value']['source2'] == '200'
    
    # Test file output
    output_file = tmp_path / "report.json"
    generator.to_json(str(output_file))
    assert output_file.exists()
    
    with open(output_file) as f:
        file_data = json.load(f)
        assert file_data == data  # Should match string output

def test_empty_report_handling():
    """Test handling of empty comparison results"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame(schema={'id': pl.Utf8, 'name': pl.Utf8}),
        unique_to_source2=pl.DataFrame(schema={'id': pl.Utf8, 'name': pl.Utf8}),
        differences=pl.DataFrame(),
        column_stats={}
    )
    
    generator = ReportGenerator(result)
    
    # Test console output
    console_output = strip_ansi(generator.to_console())
    assert "Unique to source 1: 0" in console_output
    assert "Unique to source 2: 0" in console_output
    assert "Rows with differences: 0" in console_output
    
    # Test JSON output
    json_data = json.loads(generator.to_json())
    assert json_data['summary']['row_counts']['unique_to_source1'] == 0
    assert json_data['summary']['row_counts']['unique_to_source2'] == 0
    assert len(json_data['details']['differences']) == 0

def test_csv_output(sample_result, tmp_path):
    generator = ReportGenerator(sample_result)
    output_file = tmp_path / "report.csv"
    
    generator.to_csv(str(output_file))
    assert output_file.exists()
    
    with output_file.open() as f:
        content = f.read()
        assert 'Row Counts' in content
        assert 'Column Statistics' in content
