import pytest
import json
import re
import polars as pl
from colorama import Fore, Style
from data_diff.comparison_engine import ComparisonResult
from data_diff.report_generator import ReportGenerator

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

@pytest.fixture
def scoped_result():
    """A result where the column stats cover only some of the joined rows"""
    return ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': '3', 'value': '300'}]),
        unique_to_source2=pl.DataFrame([{'id': '4', 'value': '400'}]),
        differences=pl.DataFrame(),
        column_stats={'value': 1.0},
        common_row_count=2,
        joined_row_count=4,
    )

def test_summary_reports_stats_scope(scoped_result):
    summary = ReportGenerator(scoped_result).generate_summary()

    assert summary['stats_scope']['rows_compared'] == 2
    assert summary['stats_scope']['joined_rows'] == 4
    assert summary['stats_scope']['rows_excluded_as_unique'] == 2

def test_console_states_stats_scope(scoped_result):
    output = strip_ansi(ReportGenerator(scoped_result).to_console(show_diff=False))

    assert 'Column statistics computed over 2 of 4 joined rows' in output
    assert '2 excluded as unique to one side' in output

def test_json_includes_stats_scope(scoped_result):
    report = json.loads(ReportGenerator(scoped_result).to_json())

    assert report['summary']['stats_scope']['rows_compared'] == 2
    assert report['summary']['stats_scope']['rows_excluded_as_unique'] == 2

def test_csv_includes_stats_scope(scoped_result, tmp_path):
    out = tmp_path / 'report.csv'
    ReportGenerator(scoped_result).to_csv(str(out))
    content = out.read_text()

    assert 'rows_compared' in content
    assert 'rows_excluded_as_unique' in content

def test_stats_scope_omitted_when_unknown(sample_result):
    """Hand-built results without the counts must still render"""
    summary = ReportGenerator(sample_result).generate_summary()
    assert 'stats_scope' not in summary

    output = strip_ansi(ReportGenerator(sample_result).to_console(show_diff=False))
    assert 'Column statistics computed over' not in output

def test_summary_reports_duplicate_ids_per_side(scoped_result):
    generator = ReportGenerator(
        scoped_result,
        id_duplicates={
            'source1': [],
            'source2': [{'id_values': {'id': '2'}, 'count': 3}],
        },
    )
    summary = generator.generate_summary()

    assert summary['id_uniqueness']['source1']['duplicate_key_groups'] == 0
    assert summary['id_uniqueness']['source2']['duplicate_key_groups'] == 1
    assert summary['id_uniqueness']['source2']['duplicate_rows'] == 3

    output = strip_ansi(generator.to_console(show_diff=False))
    assert 'ID Uniqueness' in output
    assert 'source2: 1 duplicate key group(s)' in output
    assert 'artefact' in output

def test_id_uniqueness_omitted_when_not_checked(scoped_result):
    summary = ReportGenerator(scoped_result).generate_summary()
    assert 'id_uniqueness' not in summary

@pytest.fixture
def directional_result():
    return ComparisonResult(
        unique_to_source1=pl.DataFrame(),
        unique_to_source2=pl.DataFrame(),
        differences=pl.DataFrame(),
        column_stats={'filled': 0.624, 'empty': 1.0},
        common_row_count=10,
        joined_row_count=10,
        column_directions={
            'filled': {
                'agree': 6, 'changed': 0, 'lost': 0,
                'gained': 4, 'blank_both': 0,
            },
            'empty': {
                'agree': 10, 'changed': 0, 'lost': 0,
                'gained': 0, 'blank_both': 0,
            },
        },
        column_coverage={
            'filled': {'source1_non_blank': 6, 'source2_non_blank': 10, 'rows': 10},
            'empty': {'source1_non_blank': 0, 'source2_non_blank': 0, 'rows': 10},
        },
        mixed_blank_key_groups={'source1': 0, 'source2': 0},
    )

def test_summary_reports_direction_and_coverage(directional_result):
    summary = ReportGenerator(directional_result).generate_summary()
    filled = summary['column_statistics']['filled']

    assert filled['directions']['lost'] == 0
    assert filled['directions']['gained'] == 4
    assert filled['coverage']['source2_non_blank'] == 10
    assert filled['vacuous'] is False

def test_summary_flags_a_vacuous_column(directional_result):
    summary = ReportGenerator(directional_result).generate_summary()

    assert summary['column_statistics']['empty']['vacuous'] is True
    assert ReportGenerator(directional_result).vacuous_columns() == ['empty']

def test_console_shows_direction_and_vacuity(directional_result):
    output = strip_ansi(ReportGenerator(directional_result).to_console(show_diff=False))

    assert 'Lost: 0' in output
    assert 'Gained: 4' in output
    assert 'Non-blank rows: source1=6, source2=10 of 10 compared' in output
    assert '(0 non-blank rows: vacuous)' in output
    assert 'Non-Vacuity:' in output
    assert 'proves little' in output

def test_json_carries_direction_coverage_and_vacuity(directional_result):
    report = json.loads(ReportGenerator(directional_result).to_json())
    columns = report['summary']['column_statistics']

    assert columns['filled']['directions']['gained'] == 4
    assert columns['empty']['vacuous'] is True
    assert report['summary']['mixed_blank_key_groups'] == {
        'source1': 0, 'source2': 0
    }

def test_csv_carries_direction_and_coverage(directional_result, tmp_path):
    out = tmp_path / 'report.csv'
    ReportGenerator(directional_result).to_csv(str(out))
    content = out.read_text()

    assert 'Lost' in content
    assert 'Mixed Blank Key Groups' in content

def test_column_stats_render_without_direction(sample_result):
    """Hand-built results without the new fields still render"""
    summary = ReportGenerator(sample_result).generate_summary()

    assert 'directions' not in summary['column_statistics']['name']
    assert 'vacuous' not in summary['column_statistics']['name']
    assert ReportGenerator(sample_result).vacuous_columns() == []

def test_undefined_percentage_renders_without_crashing():
    """Nothing paired up: the report used to raise TypeError on None"""
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': '1'}]),
        unique_to_source2=pl.DataFrame([{'id': '2'}]),
        differences=pl.DataFrame(),
        column_stats={'value': None},
        common_row_count=0,
        joined_row_count=2,
    )
    generator = ReportGenerator(result)

    summary = generator.generate_summary()
    assert summary['column_statistics']['value']['match_percentage'] == 'n/a'

    output = strip_ansi(generator.to_console(show_diff=False))
    assert 'Column statistics computed over 0 of 2 joined rows' in output
    assert 'n/a' in output

def test_trust_warnings_name_each_untrustworthy_state():
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame([{'id': '1'}]),
        unique_to_source2=pl.DataFrame(),
        differences=pl.DataFrame(),
        column_stats={'empty': 1.0},
        common_row_count=2,
        joined_row_count=3,
        column_coverage={
            'empty': {'source1_non_blank': 0, 'source2_non_blank': 0, 'rows': 2}
        },
    )
    generator = ReportGenerator(
        result,
        id_duplicates={
            'source1': [],
            'source2': [{'id_values': {'id': '2'}, 'count': 2}],
        },
    )
    warnings = generator.trust_warnings()

    assert any('not unique in source2' in w for w in warnings)
    assert any('excluded from every column percentage' in w for w in warnings)
    assert any('vacuous' in w for w in warnings)

    summary = generator.generate_summary()
    assert summary['trustworthy'] is False
    assert summary['has_differences'] is True

    output = strip_ansi(generator.to_console(show_diff=False))
    assert 'should not be quoted as evidence' in output

def test_clean_comparison_has_no_trust_warnings():
    result = ComparisonResult(
        unique_to_source1=pl.DataFrame(),
        unique_to_source2=pl.DataFrame(),
        differences=pl.DataFrame(),
        column_stats={'value': 1.0},
        common_row_count=2,
        joined_row_count=2,
        column_coverage={
            'value': {'source1_non_blank': 2, 'source2_non_blank': 2, 'rows': 2}
        },
    )
    generator = ReportGenerator(result, id_duplicates={'source1': [], 'source2': []})

    assert generator.trust_warnings() == []
    assert generator.has_differences() is False
    assert 'No trust warnings' in strip_ansi(generator.to_console(show_diff=False))


def test_exit_codes_are_on_by_default_and_can_be_opted_out():
    """The untrustworthy state is the one that otherwise reads as success, so it
    must not depend on the caller remembering a flag."""
    from data_diff.cli import parse_args

    assert parse_args(["a.csv", "b.csv"]).exit_code is True
    assert parse_args(["a.csv", "b.csv", "--exit-code"]).exit_code is True
    assert parse_args(["a.csv", "b.csv", "--no-exit-code"]).exit_code is False
