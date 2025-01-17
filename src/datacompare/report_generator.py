from typing import Dict, Optional
import json
import csv
from dataclasses import asdict
from .comparison_engine import ComparisonResult

class ReportGenerator:
    """Generates comparison reports in various formats"""
    
    def __init__(self, result: ComparisonResult):
        self.result = result
        
    def generate_summary(self) -> Dict:
        """Generate a summary of comparison results"""
        return {
            "row_counts": {
                "unique_to_source1": len(self.result.unique_to_source1),
                "unique_to_source2": len(self.result.unique_to_source2),
                "differences": len(self.result.differences)
            },
            "column_statistics": {
                col: {
                    "match_percentage": f"{score*100:.1f}%",
                    "difference_percentage": f"{(1-score)*100:.1f}%"
                }
                for col, score in self.result.column_stats.items()
            }
        }
        
    def to_console(self) -> str:
        """Generate a formatted console report"""
        summary = self.generate_summary()
        
        output = []
        output.append("=== Comparison Summary ===\n")
        
        # Row counts
        output.append("Row Counts:")
        output.append(f"  Unique to source 1: {summary['row_counts']['unique_to_source1']}")
        output.append(f"  Unique to source 2: {summary['row_counts']['unique_to_source2']}")
        output.append(f"  Rows with differences: {summary['row_counts']['differences']}\n")
        
        # Column statistics
        output.append("Column Statistics:")
        for col, stats in summary['column_statistics'].items():
            output.append(f"  {col}:")
            output.append(f"    Match: {stats['match_percentage']}")
            output.append(f"    Diff:  {stats['difference_percentage']}")
            
        return "\n".join(output)
        
    def to_json(self, output_file: Optional[str] = None) -> Optional[str]:
        """Generate JSON report"""
        summary = self.generate_summary()
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2)
        else:
            return json.dumps(summary, indent=2)
            
    def to_csv(self, output_file: str) -> None:
        """Generate CSV report"""
        summary = self.generate_summary()
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write row counts
            writer.writerow(['Row Counts'])
            for key, value in summary['row_counts'].items():
                writer.writerow([key, value])
            writer.writerow([])  # Empty row for spacing
            
            # Write column statistics
            writer.writerow(['Column Statistics'])
            writer.writerow(['Column', 'Match %', 'Difference %'])
            for col, stats in summary['column_statistics'].items():
                writer.writerow([
                    col,
                    stats['match_percentage'],
                    stats['difference_percentage']
                ])
