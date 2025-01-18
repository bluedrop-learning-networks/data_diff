import pytest
import json
import re
import pandas as pd
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
        unique_to_source1=pd.DataFrame([{'id': 1}, {'id': 2}]),
        unique_to_source2=pd.DataFrame([{'id': 3}]),
        differences=pd.DataFrame([{
            'id': {'id': 4},  # Dictionary structure for id
            'source1_value': {'id': 4, 'value': 'A'},
            'source2_value': {'id': 4, 'value': 'B'}
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
        unique_to_source1=pd.DataFrame([
            {'id': '1', 'name': 'Alice', 'value': '100'}
        ]),
        unique_to_source2=pd.DataFrame([
            {'id': '3', 'name': 'Charlie', 'value': '300'}
        ]),
        differences=pd.DataFrame([{
            'id': {'id': '2'},
            'source1_value': {'id': '2', 'name': 'Bob', 'value': '200'},
            'source2_value': {'id': '2', 'name': 'Bob', 'value': '250'}
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
        unique_to_source1=pd.DataFrame([
            {'id': '1', 'name': 'Alice', 'value': '100'}
        ]),
        unique_to_source2=pd.DataFrame([]),
        differences=pd.DataFrame([{
            'id': {'id': '2'},
            'source1_value': {'id': '2', 'name': 'Bob', 'value': '200'},
            'source2_value': {'id': '2', 'name': 'Bob', 'value': '250'}
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
        unique_to_source1=pd.DataFrame(columns=['id', 'name']),
        unique_to_source2=pd.DataFrame(columns=['id', 'name']),
        differences=pd.DataFrame(columns=['id', 'source1_value', 'source2_value']),
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
        unique_to_source1=pd.DataFrame(),
        unique_to_source2=pd.DataFrame(),
        differences=pd.DataFrame([{
            'id': {'id': '1'},
            'source1_value': {'id': '1', 'name': 'Alice', 'age': '30', 'city': 'NY'},
            'source2_value': {'id': '1', 'name': 'Alice', 'age': '31', 'city': 'LA'}
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
