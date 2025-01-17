import pytest
from datacompare.comparison_engine import ComparisonEngine, ComparisonConfig

@pytest.fixture
def basic_data():
    source1 = [
        {'id': '1', 'name': 'Alice', 'value': '100'},
        {'id': '2', 'name': 'Bob', 'value': '200'},
        {'id': '3', 'name': 'Charlie', 'value': '300'},
    ]
    
    source2 = [
        {'id': '1', 'name': 'Alice', 'value': '100'},
        {'id': '2', 'name': 'Bob', 'value': '250'},  # Different value
        {'id': '4', 'name': 'David', 'value': '400'},  # Unique to source2
    ]
    
    return source1, source2

def test_basic_comparison(basic_data):
    source1, source2 = basic_data
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'}
    )
    
    result = engine.compare()
    
    assert len(result.unique_to_source1) == 1  # ID 3
    assert len(result.unique_to_source2) == 1  # ID 4
    assert len(result.differences) == 1  # ID 2 has different value
    
def test_case_insensitive_comparison():
    source1 = [{'id': '1', 'name': 'Alice'}]
    source2 = [{'id': '1', 'name': 'ALICE'}]
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name'},
        config=ComparisonConfig(case_sensitive=False)
    )
    
    result = engine.compare()
    assert not result.differences  # Should match case-insensitively

def test_string_trimming():
    source1 = [{'id': '1', 'name': 'Alice  '}]
    source2 = [{'id': '1', 'name': '  Alice'}]
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name'},
        config=ComparisonConfig(trim_strings=True)
    )
    
    result = engine.compare()
    assert not result.differences  # Should match after trimming

def test_column_stats(basic_data):
    source1, source2 = basic_data
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'}
    )
    
    result = engine.compare()
    
    # For common IDs (1 and 2):
    # - name matches 2/2 times (100%)
    # - value matches 1/2 times (50%)
    assert result.column_stats['name'] == 1.0
    assert result.column_stats['value'] == 0.5

def test_column_selection():
    source1 = [{'id': '1', 'name': 'Alice', 'value': '100'}]
    source2 = [{'id': '1', 'name': 'Alice', 'value': '200'}]
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'},
        config=ComparisonConfig(columns_to_compare=['name'])  # Only compare name
    )
    
    result = engine.compare()
    assert not result.differences  # Should ignore value difference
