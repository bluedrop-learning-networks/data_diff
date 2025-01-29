import pytest
import polars as pl
import numpy as np
from datacompare.comparison_engine import ComparisonEngine, ComparisonConfig

@pytest.fixture
def basic_data():
    """Create two simple dataframes for testing"""
    source1 = pl.DataFrame({
        'id': ['1', '2', '3'],
        'name': ['Alice', 'Bob', 'Charlie'],
        'value': ['100', '200', '300']
    })
    
    source2 = pl.DataFrame({
        'id': ['1', '2', '4'],
        'name': ['Alice', 'Bob', 'David'],
        'value': ['100', '250', '400']  # Value different for id=2
    })
    
    return source1, source2

@pytest.fixture
def large_data():
    """Create larger dataframes for performance testing"""
    size = 10000
    source1 = pl.DataFrame({
        'id': range(size),
        'name': [f'Name{i}' for i in range(size)],
        'value': np.random.randint(1, 1000, size).tolist()
    })
    
    # Create source2 with some differences
    source2 = source1.clone()
    source2 = source2.with_columns(
        pl.when(pl.col('id') % 2 == 0)
        .then(pl.col('value') + 1)
        .otherwise(pl.col('value'))
        .alias('value')
    )
    
    # Add some new rows unique to source2
    new_rows = pl.DataFrame({
        'id': range(size, size + 100),
        'name': [f'Name{i}' for i in range(size, size + 100)],
        'value': np.random.randint(1, 1000, 100).tolist()
    })
    
    # Sample 90% of rows and concatenate with new rows
    source2 = pl.concat([
        source2.sample(fraction=0.9, seed=42),
        new_rows
    ])
    
    return source1, source2

def test_basic_comparison(basic_data):
    """Test basic comparison functionality"""
    source1, source2 = basic_data
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'}
    )
    
    result = engine.compare()
    
    # Check unique rows
    assert len(result.unique_to_source1) == 1  # Charlie
    assert len(result.unique_to_source2) == 1  # David
    
    # Check differences
    assert len(result.differences) == 1  # Bob's value changed
    diff_row = result.differences.iloc[0]
    assert diff_row['id']['id'] == '2'
    assert diff_row['source1_value']['value'] == '200'
    assert diff_row['source2_value']['value'] == '250'
    
    # Check column stats
    assert result.column_stats['name'] == 1.0  # All names match
    assert result.column_stats['value'] == 0.5  # Half of values match

def test_case_insensitive_comparison():
    """Test case-insensitive string comparison"""
    source1 = pl.DataFrame({
        'id': ['1'],
        'name': ['Alice']
    })
    
    source2 = pl.DataFrame({
        'id': ['1'],
        'name': ['ALICE']
    })
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name'},
        config=ComparisonConfig(case_sensitive=False)
    )
    
    result = engine.compare()
    assert len(result.differences) == 0
    assert result.column_stats['name'] == 1.0

def test_string_trimming():
    """Test string trimming functionality"""
    source1 = pl.DataFrame({
        'id': ['1'],
        'name': ['Alice  ']
    })
    
    source2 = pl.DataFrame({
        'id': ['1'],
        'name': ['  Alice']
    })
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name'},
        config=ComparisonConfig(trim_strings=True)
    )
    
    result = engine.compare()
    assert len(result.differences) == 0
    assert result.column_stats['name'] == 1.0

def test_column_selection():
    """Test comparing only selected columns"""
    source1 = pl.DataFrame({
        'id': ['1'],
        'name': ['Alice'],
        'value': ['100']
    })
    
    source2 = pl.DataFrame({
        'id': ['1'],
        'name': ['Alice'],
        'value': ['200']  # Different value
    })
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'},
        config=ComparisonConfig(columns_to_compare=['name'])  # Only compare name
    )
    
    result = engine.compare()
    assert len(result.differences) == 0  # Value difference ignored

def test_large_dataset_performance(large_data):
    """Test performance with larger datasets"""
    source1, source2 = large_data
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'}
    )
    
    result = engine.compare()
    
    # Basic sanity checks
    assert not result.unique_to_source1.empty
    assert not result.unique_to_source2.empty
    assert not result.differences.empty
    assert all(0 <= v <= 1 for v in result.column_stats.values())

def test_missing_values():
    """Test handling of missing/null values"""
    source1 = pl.DataFrame({
        'id': ['1', '2'],
        'value': ['100', None]
    })
    
    source2 = pl.DataFrame({
        'id': ['1', '2'],
        'value': ['100', None]
    })
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'value': 'value'}
    )
    
    result = engine.compare()
    assert result.column_stats['value'] == 1.0  # None and np.nan should be considered equal

def test_chunked_reading(tmp_path):
    """Test reading and comparing data in chunks"""
    # Create test CSV files
    file1 = tmp_path / "source1.csv"
    file2 = tmp_path / "source2.csv"
    
    pl.DataFrame({
        'id': range(1000),
        'value': range(1000)
    }).write_csv(file1)
        
    pl.DataFrame({
        'id': range(1000),
        'value': range(1000)
    }).write_csv(file2)
        
    # Read in chunks
    chunks1 = [pl.scan_csv(file1).fetch(n_rows=100) for _ in range(10)]
    chunks2 = [pl.scan_csv(file2).fetch(n_rows=100) for _ in range(10)]
    
    all_results = []
    for df1, df2 in zip(chunks1, chunks2):
        engine = ComparisonEngine(
            source1_data=df1,
            source2_data=df2,
            id_columns=['id'],
            column_mapping={'value': 'value'}
        )
        all_results.append(engine.compare())
    
    # Verify all chunks were processed
    assert len(all_results) == 10  # 1000 rows / 100 chunk size
    
    # Verify results
    for result in all_results:
        assert result.unique_to_source1.empty
        assert result.unique_to_source2.empty
        assert result.differences.empty
        assert result.column_stats['value'] == 1.0

def test_different_column_names():
    """Test comparison with different column names"""
    source1 = pd.DataFrame({
        'id': ['1'],
        'first_name': ['Alice']
    })
    
    source2 = pd.DataFrame({
        'id': ['1'],
        'name': ['Alice']
    })
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'first_name': 'name'}
    )
    
    result = engine.compare()
    assert len(result.differences) == 0
    assert result.column_stats['first_name'] == 1.0

def test_mapped_id_columns():
    """Test comparison with different ID column names"""
    source1 = pd.DataFrame({
        'customer_id': ['1', '2', '3'],
        'name': ['Alice', 'Bob', 'Charlie']
    })
    
    source2 = pd.DataFrame({
        'id': ['1', '2', '3'],
        'name': ['Alice', 'Bob', 'Charlie']
    })
    
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['customer_id'],
        column_mapping={'customer_id': 'id', 'name': 'name'}
    )
    
    result = engine.compare()
    assert len(result.unique_to_source1) == 0
    assert len(result.unique_to_source2) == 0
    assert len(result.differences) == 0
    assert result.column_stats['name'] == 1.0
