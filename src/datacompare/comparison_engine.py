from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
import difflib
import polars as pl

@dataclass
class ComparisonConfig:
    """Configuration for comparison operations"""
    case_sensitive: bool = True
    trim_strings: bool = False
    columns_to_compare: Optional[List[str]] = None

@dataclass
class ComparisonResult:
    """Results of a data comparison"""
    unique_to_source1: pl.DataFrame
    unique_to_source2: pl.DataFrame
    differences: pl.DataFrame
    column_stats: Dict[str, float]

class ComparisonEngine:
    """Handles comparison of two data sources"""
    
    def __init__(self, 
                 source1_data: pl.DataFrame,
                 source2_data: pl.DataFrame,
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
        # Rename columns in source2 to match source1
        source2_renamed = self.source2_data.rename(
            {v: k for k, v in self.column_mapping.items()}
        )

        # Prepare join expressions for ID columns
        join_on = self.id_columns

        # Perform outer join
        merged_df = self.source1_data.join(
            source2_renamed,
            on=join_on,
            how="full",
            suffix="_source2"
        )

        # Find unique rows
        unique_to_source1 = merged_df.filter(
            pl.all_horizontal([pl.col(f"{c}_source2").is_null() for c in self.column_mapping.keys() if c not in self.id_columns])
        )
        unique_to_source2 = merged_df.filter(
            pl.all_horizontal([pl.col(c).is_null() for c in self.column_mapping.keys() if c not in self.id_columns])
        )

        # Get common rows
        common_rows = merged_df.filter(
            ~pl.all_horizontal([pl.col(f"{c}_source2").is_null() for c in self.column_mapping.keys() if c not in self.id_columns]) &
            ~pl.all_horizontal([pl.col(c).is_null() for c in self.column_mapping.keys() if c not in self.id_columns])
        )

        # Determine columns to compare
        columns_to_compare = (self.config.columns_to_compare if self.config.columns_to_compare 
                            else [col for col in self.column_mapping.keys() if col not in self.id_columns])

        # Compare values and collect differences
        differences = []
        column_stats = {}

        for col in columns_to_compare:
            expr1 = pl.col(col).cast(pl.Utf8)
            expr2 = pl.col(f"{col}_source2").cast(pl.Utf8)

            if self.config.trim_strings:
                expr1 = expr1.str.strip_chars()
                expr2 = expr2.str.strip_chars()

            if not self.config.case_sensitive:
                expr1 = expr1.str.to_lowercase()
                expr2 = expr2.str.to_lowercase()

            # Calculate matches including null handling
            matches = common_rows.select([
                (expr1.is_null() & expr2.is_null()) | (expr1 == expr2)
            ]).to_series()
            
            column_stats[col] = matches.mean()

            # Find differences
            diff_mask = ~matches
            if diff_mask.any():
                diff_rows = common_rows.filter(diff_mask)
                
                for row in diff_rows.iter_rows(named=True):
                    id_values = {id_col: row[id_col] for id_col in self.id_columns}
                    source1_values = {col: row[col]}
                    source2_values = {col: row[f"{col}_source2"]}
                    
                    differences.append({
                        **id_values,
                        **{f"{k}_source1": v for k, v in source1_values.items()},
                        **{f"{k}_source2": v for k, v in source2_values.items()}
                    })

        # Create differences DataFrame
        differences_df = pl.DataFrame(differences) if differences else pl.DataFrame()

        return ComparisonResult(
            unique_to_source1=unique_to_source1.select([c for c in self.source1_data.columns]),
            unique_to_source2=unique_to_source2.select([c for c in self.source1_data.columns]),
            differences=differences_df,
            column_stats=column_stats
        )
        
