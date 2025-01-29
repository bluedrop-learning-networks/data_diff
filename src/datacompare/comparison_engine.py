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
        # Prepare data for comparison by aligning columns
        source2_renamed = self.source2_data.rename(columns={v: k for k, v in self.column_mapping.items()})
        
        # Create merged dataframe for comparison using ID columns
        merged_df = pd.merge(
            self.source1_data, 
            source2_renamed,
            on=self.id_columns,
            how='outer',
            indicator=True,
            suffixes=('_source1', '_source2')
        )
        
        # Find unique rows
        unique_to_source1 = merged_df[merged_df['_merge'] == 'left_only'].drop(columns=['_merge'])
        unique_to_source2 = merged_df[merged_df['_merge'] == 'right_only'].drop(columns=['_merge'])
        
        # Find differences in common rows
        common_rows = merged_df[merged_df['_merge'] == 'both'].drop(columns=['_merge'])
        differences = []
        
        # Compare only specified columns
        columns_to_compare = (self.config.columns_to_compare if self.config.columns_to_compare 
                            else self.column_mapping.keys())
        
        for col in columns_to_compare:
            col_source1 = col
            col_source2 = f"{col}_source2"
            
            # Apply transformations based on config
            s1_values = common_rows[col_source1].astype(str)
            s2_values = common_rows[col_source2].astype(str)
            
            if self.config.trim_strings:
                s1_values = s1_values.str.strip()
                s2_values = s2_values.str.strip()
                
            if not self.config.case_sensitive:
                s1_values = s1_values.str.lower()
                s2_values = s2_values.str.lower()
                
            # Find rows with differences
            diff_mask = (s1_values != s2_values) & \
                       (~(pd.isna(common_rows[col_source1]) & pd.isna(common_rows[col_source2])))
            
            if diff_mask.any():
                diff_rows = common_rows[diff_mask]
                for _, row in diff_rows.iterrows():
                    id_values = {id_col: row[id_col] for id_col in self.id_columns}
                    differences.append({
                        'id': id_values,
                        'source1_value': row.filter(like='_source1').to_dict(),
                        'source2_value': row.filter(like='_source2').to_dict()
                    })
        
        # Calculate column statistics using vectorized operations
        column_stats = self._calculate_column_stats_vectorized(common_rows)
        
        # Create differences DataFrame
        diff_df = pd.DataFrame(differences) if differences else pd.DataFrame(columns=['id', 'source1_value', 'source2_value'])
            
        return ComparisonResult(
            unique_to_source1=unique_df1,
            unique_to_source2=unique_df2,
            differences=diff_df,
            column_stats=column_stats
        )
        
    def _calculate_column_stats_vectorized(self, common_rows: pd.DataFrame) -> Dict[str, float]:
        """Calculate similarity statistics for each column using vectorized operations"""
        if common_rows.empty:
            return {}
            
        stats = {}
        for col in self.column_mapping:
            col_source1 = col
            col_source2 = f"{col}_source2"
            
            s1_values = common_rows[col_source1].astype(str)
            s2_values = common_rows[col_source2].astype(str)
            
            if self.config.trim_strings:
                s1_values = s1_values.str.strip()
                s2_values = s2_values.str.strip()
                
            if not self.config.case_sensitive:
                s1_values = s1_values.str.lower()
                s2_values = s2_values.str.lower()
                
            # Calculate matches including handling of NA values
            na_match = pd.isna(common_rows[col_source1]) & pd.isna(common_rows[col_source2])
            value_match = (s1_values == s2_values)
            total_matches = (na_match | value_match).sum()
            
            stats[col] = total_matches / len(common_rows)
            
        return stats
