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
        
        # Find unique rows more efficiently
        unique_to_source1 = merged_df[merged_df['_merge'] == 'left_only'].drop(columns=['_merge'])
        unique_to_source2 = merged_df[merged_df['_merge'] == 'right_only'].drop(columns=['_merge'])
        
        # Get common rows
        common_rows = merged_df[merged_df['_merge'] == 'both'].drop(columns=['_merge'])
        
        # Compare only specified columns
        columns_to_compare = (self.config.columns_to_compare if self.config.columns_to_compare 
                         else [col for col in self.column_mapping.keys() if col not in self.id_columns])

        # Create comparison mask for all columns at once
        comparison_mask = pd.DataFrame(index=common_rows.index)
        
        for col in columns_to_compare:
            col_source1 = col if col in self.id_columns else f"{col}_source1"
            col_source2 = col if col in self.id_columns else f"{col}_source2"
            
            s1_values = common_rows[col_source1].astype(str)
            s2_values = common_rows[col_source2].astype(str)
            
            if self.config.trim_strings:
                s1_values = s1_values.str.strip()
                s2_values = s2_values.str.strip()
                
            if not self.config.case_sensitive:
                s1_values = s1_values.str.lower()
                s2_values = s2_values.str.lower()
            
            comparison_mask[col] = ~(s1_values == s2_values)
        
        # Find rows with any differences
        diff_mask = comparison_mask.any(axis=1)
        
        # Create differences DataFrame more efficiently
        differences = []
        if diff_mask.any():
            diff_rows = common_rows[diff_mask]
            for idx, row in diff_rows.iterrows():
                id_values = {id_col: row[id_col] for id_col in self.id_columns}
                diff_cols = comparison_mask.columns[comparison_mask.loc[idx]]
                
                source1_values = {}
                source2_values = {}
                for col in diff_cols:
                    col_source1 = col if col in self.id_columns else f"{col}_source1"
                    col_source2 = col if col in self.id_columns else f"{col}_source2"
                    source1_values[col] = row[col_source1]
                    source2_values[col] = row[col_source2]
                
                differences.append({
                    'id': id_values,
                    'source1_value': source1_values,
                    'source2_value': source2_values
                })
        
        # Calculate column stats using vectorized operations
        column_stats = {}
        for col in columns_to_compare:
            col_source1 = col if col in self.id_columns else f"{col}_source1"
            col_source2 = col if col in self.id_columns else f"{col}_source2"
            
            s1_values = common_rows[col_source1].astype(str)
            s2_values = common_rows[col_source2].astype(str)
            
            if self.config.trim_strings:
                s1_values = s1_values.str.strip()
                s2_values = s2_values.str.strip()
                
            if not self.config.case_sensitive:
                s1_values = s1_values.str.lower()
                s2_values = s2_values.str.lower()
            
            # Handle NA values specially
            na_match = pd.isna(common_rows[col_source1]) & pd.isna(common_rows[col_source2])
            value_match = (s1_values == s2_values)
            matches = na_match | value_match
            column_stats[col] = matches.mean()

        return ComparisonResult(
            unique_to_source1=unique_to_source1,
            unique_to_source2=unique_to_source2,
            differences=pd.DataFrame(differences) if differences else pd.DataFrame(columns=['id', 'source1_value', 'source2_value']),
            column_stats=column_stats
        )
        
    def _calculate_column_stats_vectorized(self, common_rows: pd.DataFrame) -> Dict[str, float]:
        """Calculate similarity statistics for each column using vectorized operations"""
        if common_rows.empty:
            return {}
            
        stats = {}
        for col in self.column_mapping:
            # ID columns don't get suffixes during merge
            if col in self.id_columns:
                col_source1 = col
                col_source2 = col
            else:
                col_source1 = f"{col}_source1"
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
