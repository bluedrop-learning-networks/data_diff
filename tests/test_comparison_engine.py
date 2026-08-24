import pytest
import polars as pl
import numpy as np
from data_diff.comparison_engine import ComparisonEngine, ComparisonConfig

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
    diff_row = result.differences.row(0, named=True)
    assert diff_row['id'] == '2'
    assert diff_row['value_source1'] == '200'
    assert diff_row['value_source2'] == '250'
    
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
    assert result.unique_to_source1.height > 0
    assert result.unique_to_source2.height > 0
    assert result.differences.height > 0
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
    chunks1 = [pl.scan_csv(file1).collect().head(100) for _ in range(10)]
    chunks2 = [pl.scan_csv(file2).collect().head(100) for _ in range(10)]
    
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
        assert result.unique_to_source1.height == 0
        assert result.unique_to_source2.height == 0
        assert result.differences.height == 0
        assert result.column_stats['value'] == 1.0

def test_different_column_names():
    """Test comparison with different column names"""
    source1 = pl.DataFrame({
        'id': ['1'],
        'first_name': ['Alice']
    })
    
    source2 = pl.DataFrame({
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
    source1 = pl.DataFrame({
        'customer_id': ['1', '2', '3'],
        'name': ['Alice', 'Bob', 'Charlie']
    })
    
    source2 = pl.DataFrame({
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

def test_stats_scope_counts(basic_data):
    """Column stats cover only the paired rows, and the result says how many"""
    source1, source2 = basic_data
    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'}
    )

    result = engine.compare()

    # id 1 and 2 pair up; id 3 and id 4 are unique to one side each
    assert result.common_row_count == 2
    assert result.joined_row_count == 4

def test_stats_exclude_rows_whose_key_moved():
    """A value lost on a moved key must not read as a clean comparison

    The column stats can only see paired rows, so they report a perfect
    match here. The row accounting is the only thing that tells the reader
    the stats covered 1 of 3 rows.
    """
    source1 = pl.DataFrame({
        'id': ['1', '2'],
        'name': ['Alice', 'Bob'],
        'value': ['100', '200']
    })
    source2 = pl.DataFrame({
        'id': ['1', '99'],
        'name': ['Alice', 'Bob'],
        'value': ['100', '']  # same person, moved key, value dropped
    })

    engine = ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'name': 'name', 'value': 'value'}
    )
    result = engine.compare()

    assert result.column_stats['value'] == 1.0
    assert len(result.differences) == 0
    assert result.common_row_count == 1
    assert result.joined_row_count == 3

@pytest.fixture
def directional_data():
    """Two frames exercising each direction bucket once"""
    source1 = pl.DataFrame({
        'id': ['1', '2', '3', '4', '5'],
        'value': ['same', 'old', 'dropped', '', ''],
    })
    source2 = pl.DataFrame({
        'id': ['1', '2', '3', '4', '5'],
        'value': ['same', 'new', '', 'filled', '   '],
    })
    return source1, source2

def _engine(source1, source2, **kwargs):
    return ComparisonEngine(
        source1_data=source1,
        source2_data=source2,
        id_columns=['id'],
        column_mapping={'value': 'value'},
        **kwargs
    )

def test_direction_counts_split_by_direction(directional_data):
    """A match percentage cannot say which way a difference runs"""
    result = _engine(*directional_data).compare()
    directions = result.column_directions['value']

    assert directions['agree'] == 1      # 'same'
    assert directions['changed'] == 1    # old -> new
    assert directions['lost'] == 1       # dropped -> blank
    assert directions['gained'] == 1     # blank -> filled
    assert directions['blank_both'] == 1  # '' vs '   ', untrimmed by default

def test_blank_both_folds_into_agree_when_trimming(directional_data):
    result = _engine(
        *directional_data, config=ComparisonConfig(trim_strings=True)
    ).compare()
    directions = result.column_directions['value']

    assert directions['agree'] == 2
    assert directions['blank_both'] == 0

def test_direction_buckets_partition_the_common_rows(directional_data):
    result = _engine(*directional_data).compare()
    directions = result.column_directions['value']

    assert sum(directions.values()) == result.common_row_count

def test_direction_agree_matches_column_stats(directional_data):
    """The agree bucket must not contradict the published percentage"""
    result = _engine(*directional_data).compare()
    directions = result.column_directions['value']

    expected = result.column_stats['value'] * result.common_row_count
    assert directions['agree'] == pytest.approx(expected)

def test_gained_only_column_is_not_damage():
    """The new side filling blanks reads as a low match percentage"""
    source1 = pl.DataFrame({'id': ['1', '2', '3'], 'value': ['', '', 'keep']})
    source2 = pl.DataFrame({'id': ['1', '2', '3'], 'value': ['a', 'b', 'keep']})

    result = _engine(source1, source2).compare()

    assert result.column_stats['value'] < 0.5
    assert result.column_directions['value']['lost'] == 0
    assert result.column_directions['value']['gained'] == 2

def test_coverage_counts_expose_a_vacuous_column():
    """A column blank on every row agrees with itself and proves nothing"""
    source1 = pl.DataFrame({'id': ['1', '2'], 'value': ['', '']})
    source2 = pl.DataFrame({'id': ['1', '2'], 'value': ['', '']})

    result = _engine(source1, source2).compare()

    assert result.column_stats['value'] == 1.0
    assert result.column_coverage['value']['source1_non_blank'] == 0
    assert result.column_coverage['value']['source2_non_blank'] == 0
    assert result.column_coverage['value']['rows'] == 2

def test_coverage_counts_per_side(directional_data):
    result = _engine(*directional_data).compare()
    coverage = result.column_coverage['value']

    assert coverage['source1_non_blank'] == 3
    assert coverage['source2_non_blank'] == 3
    assert coverage['rows'] == 5

def test_mixed_blank_key_groups_detects_expressible_failure():
    """A key group holding both a blank and a value can express a loss"""
    source1 = pl.DataFrame({
        'id': ['1', '1', '2'],
        'value': ['set', '', 'set'],
    })
    result = _engine(source1, source1.clone()).compare()

    assert result.mixed_blank_key_groups['source1'] == 1
    assert result.mixed_blank_key_groups['source2'] == 1

def test_mixed_blank_key_groups_zero_when_not_expressible():
    source1 = pl.DataFrame({'id': ['1', '2'], 'value': ['a', 'b']})
    result = _engine(source1, source1.clone()).compare()

    assert result.mixed_blank_key_groups == {'source1': 0, 'source2': 0}
