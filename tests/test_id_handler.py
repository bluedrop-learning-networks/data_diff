import pytest
from datacompare.id_handler import IDHandler

@pytest.fixture
def sample_data():
    return [
        {'id': '1', 'name': 'Alice', 'order_id': 'A1'},
        {'id': '2', 'name': 'Bob', 'order_id': 'A2'},
        {'id': '3', 'name': 'Charlie', 'order_id': 'A3'},
    ]

def test_detect_id_columns():
    columns = ['id', 'name', 'customer_id', 'price']
    data = [
        {'id': '1', 'name': 'A', 'customer_id': 'C1', 'price': '10'},
        {'id': '2', 'name': 'B', 'customer_id': 'C2', 'price': '10'},
    ]
    
    handler = IDHandler(columns, data)
    id_cols = handler.detect_id_columns()
    
    assert 'id' in id_cols
    assert 'customer_id' in id_cols
    assert 'name' in id_cols  # Should be detected due to uniqueness
    assert 'price' not in id_cols  # Not unique, not ID pattern

def test_validate_id_columns(sample_data):
    handler = IDHandler(['id', 'name', 'order_id'], sample_data)
    
    # Valid case
    errors = handler.validate_id_columns(['id', 'order_id'])
    assert len(errors) == 0
    
    # Invalid column
    errors = handler.validate_id_columns(['invalid_col'])
    assert len(errors) == 1
    assert isinstance(errors[0], FatalIDValidationError)
    assert "not found in data source" in errors[0].message
        
    # Null values
    data_with_null = sample_data + [{'id': None, 'name': 'Dave', 'order_id': 'A4'}]
    handler = IDHandler(['id', 'name', 'order_id'], data_with_null)
    errors = handler.validate_id_columns(['id'])
    assert len(errors) == 1
    assert isinstance(errors[0], WarningIDValidationError)
    assert "contains null values" in errors[0].message

    # Multiple errors
    errors = handler.validate_id_columns(['id', 'invalid_col'])
    assert len(errors) == 2
    assert any(isinstance(e, FatalIDValidationError) for e in errors)
    assert any(isinstance(e, WarningIDValidationError) for e in errors)

def test_find_duplicate_ids():
    data = [
        {'id': '1', 'region': 'A'},
        {'id': '1', 'region': 'B'},  # Duplicate id
        {'id': '2', 'region': 'A'},
    ]
    
    handler = IDHandler(['id', 'region'], data)
    duplicates = handler.find_duplicate_ids(['id'])
    
    assert len(duplicates) == 1
    assert duplicates[0]['id_values'] == {'id': '1'}
    assert duplicates[0]['count'] == 2
