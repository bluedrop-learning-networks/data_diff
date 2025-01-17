from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
import difflib

@dataclass
class ComparisonConfig:
    """Configuration for comparison operations"""
    case_sensitive: bool = True
    trim_strings: bool = False
    columns_to_compare: Optional[List[str]] = None

@dataclass
class ComparisonResult:
    """Results of a data comparison"""
    unique_to_source1: List[Dict]
    unique_to_source2: List[Dict]
    differences: List[Dict]
    column_stats: Dict[str, float]

class ComparisonEngine:
    """Handles comparison of two data sources"""
    
    def __init__(self, 
                 source1_data: List[Dict], 
                 source2_data: List[Dict],
                 id_columns: List[str],
                 column_mapping: Dict[str, str],
                 config: Optional[ComparisonConfig] = None):
        self.source1_data = source1_data
        self.source2_data = source2_data
        self.id_columns = id_columns
        self.column_mapping = column_mapping
        self.config = config or ComparisonConfig()
        
    def compare(self) -> ComparisonResult:
        """Perform full comparison of the two data sources"""
        # Create indexes for faster lookup
        source1_index = self._create_index(self.source1_data)
        source2_index = self._create_index(self.source2_data)
        
        # Find unique and common IDs
        source1_ids = set(source1_index.keys())
        source2_ids = set(source2_index.keys())
        
        unique_to_source1 = source1_ids - source2_ids
        unique_to_source2 = source2_ids - source1_ids
        common_ids = source1_ids & source2_ids
        
        # Collect results
        unique_rows1 = [source1_index[id_] for id_ in unique_to_source1]
        unique_rows2 = [source2_index[id_] for id_ in unique_to_source2]
        differences = []
        
        # Compare common rows
        for id_ in common_ids:
            row1 = source1_index[id_]
            row2 = source2_index[id_]
            
            if diff := self._compare_rows(row1, row2):
                differences.append({
                    'id': dict(zip(self.id_columns, id_)),
                    'differences': diff
                })
                
        # Calculate column statistics
        column_stats = self._calculate_column_stats(
            source1_index, source2_index, common_ids)
            
        return ComparisonResult(
            unique_to_source1=unique_rows1,
            unique_to_source2=unique_rows2,
            differences=differences,
            column_stats=column_stats
        )
        
    def _create_index(self, data: List[Dict]) -> Dict[Tuple, Dict]:
        """Create an index of rows based on ID columns"""
        index = {}
        for row in data:
            key = tuple(str(row.get(col)) for col in self.id_columns)
            index[key] = row
        return index
        
    def _compare_rows(self, row1: Dict, row2: Dict) -> Optional[Dict[str, Dict]]:
        """Compare two rows and return differences"""
        differences = {}
        
        # Determine which columns to compare
        columns_to_compare = (self.config.columns_to_compare if self.config.columns_to_compare 
                            else self.column_mapping.keys())
        
        for source1_col in columns_to_compare:
            source2_col = self.column_mapping[source1_col]
            
            value1 = str(row1.get(source1_col, ''))
            value2 = str(row2.get(source2_col, ''))
            
            if self.config.trim_strings:
                value1 = value1.strip()
                value2 = value2.strip()
                
            if not self.config.case_sensitive:
                value1 = value1.lower()
                value2 = value2.lower()
                
            if value1 != value2:
                differences[source1_col] = {
                    'source1': row1.get(source1_col),
                    'source2': row2.get(source2_col)
                }
                
        return differences if differences else None
        
    def _calculate_column_stats(self, 
                              source1_index: Dict[Tuple, Dict],
                              source2_index: Dict[Tuple, Dict],
                              common_ids: Set[Tuple]) -> Dict[str, float]:
        """Calculate similarity statistics for each column"""
        if not common_ids:
            return {}
            
        matches = {col: 0 for col in self.column_mapping}
        total = len(common_ids)
        
        for id_ in common_ids:
            row1 = source1_index[id_]
            row2 = source2_index[id_]
            
            for source1_col, source2_col in self.column_mapping.items():
                value1 = str(row1.get(source1_col, ''))
                value2 = str(row2.get(source2_col, ''))
                
                if self.config.trim_strings:
                    value1 = value1.strip()
                    value2 = value2.strip()
                    
                if not self.config.case_sensitive:
                    value1 = value1.lower()
                    value2 = value2.lower()
                    
                if value1 == value2:
                    matches[source1_col] += 1
                    
        return {col: matches[col] / total for col in matches}
