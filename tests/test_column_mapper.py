import pytest
from datacompare.column_mapper import ColumnMapper

def test_exact_column_matching():
    source1_cols = ['id', 'name', 'price']
    source2_cols = ['id', 'name', 'price']
    
    mapper = ColumnMapper(source1_cols, source2_cols)
    mapping = mapper.auto_map_columns()
    
    assert mapping == {
        'id': 'id',
        'name': 'name',
        'price': 'price'
    }

def test_similar_column_matching():
    source1_cols = ['id', 'product_name', 'price']
    source2_cols = ['product_id', 'name', 'cost']
    
    mapper = ColumnMapper(source1_cols, source2_cols)
    mapping = mapper.auto_map_columns()
    
    assert mapping['id'] == 'product_id'
    assert mapping['product_name'] == 'name'
    assert mapping['price'] == 'cost'

def test_load_valid_config(tmp_path):
    config_file = tmp_path / "mapping.json"
    config_file.write_text('''
    {
        "source1": "file1.csv",
        "source2": "file2.csv",
        "column_mapping": {
            "id": "product_id",
            "name": "product_name"
        }
    }
    ''')
    
    config = ColumnMapper.load_mapping_config(str(config_file))
    assert 'column_mapping' in config
    assert config['column_mapping']['id'] == 'product_id'

def test_validate_mapping():
    source1_cols = ['id', 'name', 'price']
    source2_cols = ['product_id', 'product_name', 'cost']
    
    mapper = ColumnMapper(source1_cols, source2_cols)
    
    valid_mapping = {
        'id': 'product_id',
        'name': 'product_name',
        'price': 'cost'
    }
    mapper.validate_mapping(valid_mapping)  # Should not raise
    
    invalid_mapping = {
        'id': 'invalid_col'
    }
    with pytest.raises(ValueError):
        mapper.validate_mapping(invalid_mapping)
