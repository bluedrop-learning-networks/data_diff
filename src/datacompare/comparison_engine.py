from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
import difflib
import pandas as pd
import numpy as np

@dataclass
class ComparisonConfig:
    """Configuration for comparison operations"""
    case_sensitive: bool = True
    trim_strings: bool = False
    columns_to_compare: Optional[List[str]] = None

@dataclass
class ComparisonResult:
    """Results of a data comparison"""
    unique_to_source1: pd.DataFrame
    unique_to_source2: pd.DataFrame
    differences: pd.DataFrame
    column_stats: Dict[str, float]

class ComparisonEngine:
    """Handles comparison of two data sources"""
    
    def __init__(self, 
                 source1_data: pd.DataFrame,
                 source2_data: pd.DataFrame,
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
        source1_index = self._create_index(self.source1_data, is_source2=False)
        source2_index = self._create_index(self.source2_data, is_source2=True)
        
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
                # The diff already contains source1_value and source2_value
                diff_row = {'id': dict(zip(self.id_columns, id_))}
                diff_row.update(diff)  # Add the source1_value and source2_value directly
                differences.append(diff_row)
    
        # Convert results to DataFrames
        columns1 = self.source1_data.columns if hasattr(self.source1_data, 'columns') else list(self.source1_data[0].keys())
        columns2 = self.source2_data.columns if hasattr(self.source2_data, 'columns') else list(self.source2_data[0].keys())
        
        unique_df1 = pd.DataFrame(unique_rows1, columns=columns1) if unique_rows1 else pd.DataFrame(columns=columns1)
        unique_df2 = pd.DataFrame(unique_rows2, columns=columns2) if unique_rows2 else pd.DataFrame(columns=columns2)
        diff_df = pd.DataFrame(differences) if differences else pd.DataFrame(columns=['id', 'source1_value', 'source2_value'])
    
        # Calculate column statistics
        column_stats = self._calculate_column_stats(source1_index, source2_index, common_ids)
            
        return ComparisonResult(
            unique_to_source1=unique_df1,
            unique_to_source2=unique_df2,
            differences=diff_df,
            column_stats=column_stats
        )
        
    def _create_index(self, data: pd.DataFrame, is_source2: bool = False) -> Dict[Tuple, Dict]:
        """Create an index of rows based on ID columns
        
        Args:
            data: DataFrame to index
            is_source2: Whether this is the second data source (affects column mapping)
        """
        index = {}
        # Reset the index to make sure we process all rows
        data = data.reset_index(drop=True)
        
        for _, row in data.iterrows():
            # For source2, map ID columns using column mapping if present
            if is_source2:
                id_values = []
                for id_col in self.id_columns:
                    mapped_col = self.column_mapping.get(id_col, id_col)
                    id_values.append(str(row[mapped_col]))
                key = tuple(id_values)
            else:
                key = tuple(str(row[col]) for col in self.id_columns)
                
            # Convert row to dict, ensuring all values are stored as strings
            index[key] = {col: str(val) if pd.notna(val) else val 
                         for col, val in row.items()}
        return index
        
    def _compare_rows(self, row1: Dict, row2: Dict) -> Optional[Dict]:
        """Compare two rows and return differences"""
        differences = {}
        
        columns_to_compare = (self.config.columns_to_compare if self.config.columns_to_compare 
                            else self.column_mapping.keys())
        
        has_differences = False
        for source1_col in columns_to_compare:
            source2_col = self.column_mapping[source1_col]
            
            value1 = row1.get(source1_col)
            value2 = row2.get(source2_col)
            
            # Handle None/NaN equality
            if pd.isna(value1) and pd.isna(value2):
                continue
                
            # Convert to string only if both values are not None/NaN
            if not pd.isna(value1) and not pd.isna(value2):
                value1 = str(value1)
                value2 = str(value2)
                
                if self.config.trim_strings:
                    value1 = value1.strip()
                    value2 = value2.strip()
                    
                if not self.config.case_sensitive:
                    value1 = value1.lower()
                    value2 = value2.lower()
        
            if value1 != value2:
                has_differences = True
                
        if has_differences:
            differences = {
                'source1_value': row1,
                'source2_value': row2
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
                value1 = row1.get(source1_col)
                value2 = row2.get(source2_col)
                
                # Consider None and np.nan as equal
                if pd.isna(value1) and pd.isna(value2):
                    matches[source1_col] += 1
                    continue
                    
                if not pd.isna(value1) and not pd.isna(value2):
                    value1 = str(value1)
                    value2 = str(value2)
                    
                    if self.config.trim_strings:
                        value1 = value1.strip()
                        value2 = value2.strip()
                        
                    if not self.config.case_sensitive:
                        value1 = value1.lower()
                        value2 = value2.lower()
                        
                    if value1 == value2:
                        matches[source1_col] += 1
                    
        return {col: matches[col] / total for col in matches}
