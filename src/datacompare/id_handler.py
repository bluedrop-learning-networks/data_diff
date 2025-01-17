from typing import List, Set, Dict, Optional
import re
from collections import Counter

class IDHandler:
    """Handles detection and validation of ID columns"""
    
    COMMON_ID_PATTERNS = [
        r'^id$',
        r'^.*_id$',
        r'^.*id$',
        r'^key$',
        r'^.*_key$',
    ]
    
    def __init__(self, columns: List[str], data_sample: List[Dict]):
        self.columns = columns
        self.data_sample = data_sample
        
    def detect_id_columns(self) -> List[str]:
        """Automatically detect likely ID columns based on name and uniqueness
        
        Returns:
            List of column names that are likely ID columns
        """
        candidates = set()
        
        # Check column names against common patterns
        for col in self.columns:
            if self._matches_id_pattern(col.lower()):
                candidates.add(col)
                
        # Check uniqueness of values
        uniqueness_scores = self._calculate_uniqueness_scores()
        
        # Add columns with high uniqueness (>95%) to candidates
        for col, score in uniqueness_scores.items():
            if score > 0.95:
                candidates.add(col)
                
        return list(candidates)
        
    @staticmethod
    def _matches_id_pattern(column_name: str) -> bool:
        """Check if column name matches common ID patterns"""
        return any(re.match(pattern, column_name) 
                  for pattern in IDHandler.COMMON_ID_PATTERNS)
                  
    def _calculate_uniqueness_scores(self) -> Dict[str, float]:
        """Calculate uniqueness score for each column"""
        if not self.data_sample:
            return {}
            
        scores = {}
        total_rows = len(self.data_sample)
        
        for col in self.columns:
            values = [str(row.get(col)) for row in self.data_sample]
            unique_count = len(set(values))
            scores[col] = unique_count / total_rows
            
        return scores
        
    def validate_id_columns(self, id_columns: List[str]) -> None:
        """Validate specified ID columns
        
        Args:
            id_columns: List of column names to use as IDs
            
        Raises:
            ValueError: If any validation fails
        """
        # Check columns exist
        for col in id_columns:
            if col not in self.columns:
                raise ValueError(f"ID column '{col}' not found in data source")
                
        # Check for null values
        for col in id_columns:
            if self._has_null_values(col):
                raise ValueError(f"ID column '{col}' contains null values")
                
    def _has_null_values(self, column: str) -> bool:
        """Check if column contains any null values"""
        return any(not row.get(column) for row in self.data_sample)
        
    def find_duplicate_ids(self, id_columns: List[str]) -> List[Dict]:
        """Find any duplicate ID combinations
        
        Args:
            id_columns: List of columns that form the composite ID
            
        Returns:
            List of duplicate ID combinations and their counts
        """
        # Create composite keys from all ID columns
        id_combinations = []
        for row in self.data_sample:
            key = tuple(str(row.get(col)) for col in id_columns)
            id_combinations.append(key)
            
        # Find duplicates
        counts = Counter(id_combinations)
        duplicates = []
        
        for id_combo, count in counts.items():
            if count > 1:
                duplicates.append({
                    'id_values': dict(zip(id_columns, id_combo)),
                    'count': count
                })
                
        return duplicates
