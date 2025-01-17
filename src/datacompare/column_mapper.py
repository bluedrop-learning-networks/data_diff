from typing import Dict, List, Optional
from difflib import SequenceMatcher
import json
from pathlib import Path

class ColumnMapper:
    """Handles mapping columns between two data sources"""
    
    def __init__(self, source1_columns: List[str], source2_columns: List[str]):
        self.source1_columns = source1_columns
        self.source2_columns = source2_columns
        
    def auto_map_columns(self) -> Dict[str, str]:
        """Automatically map columns based on name similarity
        
        Returns:
            Dict mapping source1 column names to source2 column names
        """
        mappings = {}
        
        # Convert to lowercase for comparison
        s1_cols = [col.lower() for col in self.source1_columns]
        s2_cols = [col.lower() for col in self.source2_columns]
        
        # Try exact matches first
        for idx1, col1 in enumerate(s1_cols):
            if col1 in s2_cols:
                idx2 = s2_cols.index(col1)
                mappings[self.source1_columns[idx1]] = self.source2_columns[idx2]
                
        # For remaining columns, use similarity matching
        unmapped_s1 = [col for col in self.source1_columns if col not in mappings]
        used_s2 = [col for col in self.source2_columns if col in mappings.values()]
        
        for col1 in unmapped_s1:
            best_match = None
            best_score = 0.0
            
            for col2 in self.source2_columns:
                if col2 in used_s2:
                    continue
                    
                score = SequenceMatcher(None, 
                                      col1.lower(), 
                                      col2.lower()).ratio()
                if score > best_score and score > 0.6:  # Threshold for similarity
                    best_score = score
                    best_match = col2
                    
            if best_match:
                mappings[col1] = best_match
                used_s2.append(best_match)
                
        return mappings

    @staticmethod
    def load_mapping_config(config_path: str) -> Dict:
        """Load column mapping configuration from a JSON file
        
        Args:
            config_path: Path to JSON config file
            
        Returns:
            Dict containing mapping configuration
            
        Raises:
            ValueError: If config file is invalid
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        with path.open('r') as f:
            config = json.load(f)
            
        # Validate config structure
        required_keys = ['source1', 'source2', 'column_mapping']
        if not all(key in config for key in required_keys):
            raise ValueError("Config must contain 'source1', 'source2', and 'column_mapping'")
            
        return config

    def validate_mapping(self, mapping: Dict[str, str]) -> None:
        """Validate a column mapping
        
        Args:
            mapping: Dict mapping source1 columns to source2 columns
            
        Raises:
            ValueError: If mapping is invalid
        """
        # Check all source columns exist
        for col in mapping:
            if col not in self.source1_columns:
                raise ValueError(f"Source column '{col}' not found in source1")
                
        # Check all target columns exist
        for col in mapping.values():
            if col not in self.source2_columns:
                raise ValueError(f"Target column '{col}' not found in source2")
