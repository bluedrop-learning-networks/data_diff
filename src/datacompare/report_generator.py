from typing import Dict, Optional, List
import json
import csv
from dataclasses import asdict
import shutil
from colorama import init, Fore, Style
from .comparison_engine import ComparisonResult

init()  # Initialize colorama

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
        
    def to_console(self, show_diff: bool = True) -> str:
        """Generate a formatted console report with optional colorized diff
        
        Args:
            show_diff: Whether to include detailed diffs after the summary
        """
        summary = self.generate_summary()
        
        output = []
        output.append(f"{Style.BRIGHT}=== Comparison Summary ==={Style.RESET_ALL}\n")
        
        # Row counts
        output.append(f"{Style.BRIGHT}Row Counts:{Style.RESET_ALL}")
        output.append(f"  Unique to source 1: {Fore.YELLOW}{summary['row_counts']['unique_to_source1']}{Style.RESET_ALL}")
        output.append(f"  Unique to source 2: {Fore.YELLOW}{summary['row_counts']['unique_to_source2']}{Style.RESET_ALL}")
        output.append(f"  Rows with differences: {Fore.YELLOW}{summary['row_counts']['differences']}{Style.RESET_ALL}\n")
        
        # Column statistics
        output.append(f"{Style.BRIGHT}Column Statistics:{Style.RESET_ALL}")
        for col, stats in summary['column_statistics'].items():
            match_pct = float(stats['match_percentage'].rstrip('%'))
            color = Fore.GREEN if match_pct >= 90 else (Fore.YELLOW if match_pct >= 70 else Fore.RED)
            
            output.append(f"  {col}:")
            output.append(f"    Match: {color}{stats['match_percentage']}{Style.RESET_ALL}")
            output.append(f"    Diff:  {color}{stats['difference_percentage']}{Style.RESET_ALL}")
            
        if show_diff and not self.result.differences.empty:
            output.extend(['', f"{Style.BRIGHT}=== Detailed Differences ==={Style.RESET_ALL}"])
            output.append(self._generate_detailed_diff())
            
        return '\n'.join(output)
        
    def _generate_detailed_diff(self) -> str:
        """Generate a detailed diff report with side-by-side comparison"""
        output = []
        term_width = shutil.get_terminal_size().columns
        col_width = min(40, (term_width - 10) // 2)  # Leave room for separators
        
        # Header
        header = f"{'Source 1':<{col_width}} | {'Source 2':<{col_width}}"
        separator = '-' * (col_width * 2 + 3)
        output.extend(['', header, separator])
        
        # Process each difference
        for _, row in self.result.differences.iterrows():
            id_str = ' '.join(f"{k}={v}" for k, v in row['id'].items())
            output.append(f"\n{Style.BRIGHT}ID: {id_str}{Style.RESET_ALL}")
            
            source1_val = str(row['source1_value'])
            source2_val = str(row['source2_value'])
            
            # Wrap long values
            source1_lines = self._wrap_text(source1_val, col_width)
            source2_lines = self._wrap_text(source2_val, col_width)
            
            # Ensure both sides have same number of lines
            max_lines = max(len(source1_lines), len(source2_lines))
            source1_lines.extend([''] * (max_lines - len(source1_lines)))
            source2_lines.extend([''] * (max_lines - len(source2_lines)))
            
            # Output side by side with color
            for s1, s2 in zip(source1_lines, source2_lines):
                line = f"{Fore.RED}{s1:<{col_width}}{Style.RESET_ALL} | {Fore.GREEN}{s2:<{col_width}}{Style.RESET_ALL}"
                output.append(line)
                
        return '\n'.join(output)
        
    @staticmethod
    def _wrap_text(text: str, width: int) -> List[str]:
        """Wrap text to fit within specified width"""
        lines = []
        while text:
            if len(text) <= width:
                lines.append(text)
                break
            # Find last space within width
            space_idx = text.rfind(' ', 0, width)
            if space_idx == -1:  # No space found, force break at width
                lines.append(text[:width])
                text = text[width:]
            else:
                lines.append(text[:space_idx])
                text = text[space_idx + 1:]
        return lines
        
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
