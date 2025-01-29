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
        """Generate formatted console report with optional colorized diff
        
        Args:
            show_diff: Whether to include detailed diffs after the summary
            
        Returns:
            Formatted string with ANSI color codes
        """
        output = []
        
        # Add summary section
        output.extend(self._generate_summary_section())
        
        # Add detailed diff section if requested
        if show_diff and (self.result.differences.height > 0 or 
                         self.result.unique_to_source1.height > 0 or 
                         self.result.unique_to_source2.height > 0):
            output.extend(['', f"{Style.BRIGHT}=== Detailed Differences ==={Style.RESET_ALL}"])
            output.append(self._generate_detailed_diff())
        
        return '\n'.join(output)

    def _generate_summary_section(self) -> List[str]:
        """Generate the summary section of the report"""
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
        
        return output
        
    def _generate_detailed_diff(self) -> str:
        """Generate a detailed diff report showing added, removed, and changed rows"""
        output = []
        term_width = shutil.get_terminal_size().columns
        col_width = min(40, (term_width - 10) // 2)  # Leave room for separators

        # Show removed rows (unique to source 1)
        if self.result.unique_to_source1.height > 0:
            output.extend(['', f"{Style.BRIGHT}Rows Removed (Unique to Source 1):{Style.RESET_ALL}"])
            for row in self.result.unique_to_source1.iter_rows(named=True):
                output.append(f"{Fore.RED}- {dict(row)}{Style.RESET_ALL}")

        # Show added rows (unique to source 2)
        if self.result.unique_to_source2.height > 0:
            output.extend(['', f"{Style.BRIGHT}Rows Added (Unique to Source 2):{Style.RESET_ALL}"])
            for row in self.result.unique_to_source2.iter_rows(named=True):
                output.append(f"{Fore.GREEN}+ {dict(row)}{Style.RESET_ALL}")

        # Show modified rows
        if self.result.differences.height > 0:
            output.extend(['', f"{Style.BRIGHT}Modified Rows:{Style.RESET_ALL}"])
            
            for row in self.result.differences.iter_rows(named=True):
                id_parts = []
                for id_col in self.result.unique_to_source1.columns:
                    if id_col in row:
                        id_parts.append(f"{id_col}={row[id_col]}")
                id_str = ', '.join(id_parts)
                output.append(f"\n{Style.BRIGHT}ID: {id_str}{Style.RESET_ALL}")
                
                # Find which columns have differences
                diff_cols = set()
                for col in self.result.column_stats.keys():
                    if row.get(f"{col}_source1") != row.get(f"{col}_source2"):
                        diff_cols.add(col)

                # Format source1 values with red highlighting for changes
                source1_parts = []
                source2_parts = []
                for col in self.result.column_stats.keys():
                    val1 = row.get(f"{col}_source1")
                    val2 = row.get(f"{col}_source2")
                    if col in diff_cols:
                        source1_parts.append(f"{col}={Fore.RED}{val1}{Style.RESET_ALL}")
                        source2_parts.append(f"{col}={Fore.GREEN}{val2}{Style.RESET_ALL}")
                    else:
                        source1_parts.append(f"{col}={val1}")
                        source2_parts.append(f"{col}={val2}")
                output.append(f"- {', '.join(source1_parts)}")
                output.append(f"+ {', '.join(source2_parts)}")

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
        """Generate JSON report with detailed results
        
        Args:
            output_file: Optional path to output JSON file
            
        Returns:
            JSON string if no output_file specified
        """
        # Create detailed report structure
        report = {
            'summary': self.generate_summary(),
            'details': {
                'unique_to_source1': self.result.unique_to_source1.to_dicts(),
                'unique_to_source2': self.result.unique_to_source2.to_dicts(),
                'differences': []
            }
        }
        
        # Add detailed differences
        for row in self.result.differences.iter_rows(named=True):
            diff_entry = {
                'id': row['id'],
                'changes': {}
            }
            
            # Calculate specific changes
            for col in self.result.column_stats.keys():
                val1 = row.get(f"{col}_source1")
                val2 = row.get(f"{col}_source2")
                if val1 != val2:
                    diff_entry['changes'][col] = {
                        'source1': val1,
                        'source2': val2
                    }
                    
            report['details']['differences'].append(diff_entry)
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        else:
            return json.dumps(report, indent=2)
            
    def to_csv(self, output_file: str) -> None:
        """Generate CSV report with detailed results
        
        Args:
            output_file: Path to output CSV file
        """
        summary = self.generate_summary()
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write summary section
            writer.writerow(['=== Comparison Summary ==='])
            writer.writerow([])
            
            # Write row counts
            writer.writerow(['Row Counts'])
            for key, value in summary['row_counts'].items():
                writer.writerow([key, value])
            writer.writerow([])
            
            # Write column statistics
            writer.writerow(['Column Statistics'])
            writer.writerow(['Column', 'Match %', 'Difference %'])
            for col, stats in summary['column_statistics'].items():
                writer.writerow([
                    col,
                    stats['match_percentage'],
                    stats['difference_percentage']
                ])
            writer.writerow([])
            
            # Write differences if any exist
            if self.result.differences.height > 0:
                writer.writerow(['=== Detailed Differences ==='])
                writer.writerow([])
                
                # Write modified rows
                writer.writerow(['Modified Rows'])
                writer.writerow(['ID', 'Column', 'Source 1 Value', 'Source 2 Value'])
                for row in self.result.differences.iter_rows(named=True):
                    id_str = f"id={row['id']}"
                    for col in self.result.column_stats.keys():
                        val1 = row.get(f"{col}_source1")
                        val2 = row.get(f"{col}_source2")
                        if val1 != val2:
                            writer.writerow([
                                id_str,
                                col,
                                val1,
                                val2
                            ])
