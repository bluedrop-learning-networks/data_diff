from typing import Dict, Optional, List
import json
import csv
from dataclasses import asdict
import shutil
from colorama import init, Fore, Style
from .comparison_engine import ComparisonResult

init(strip=False)  # Initialize colorama


class ReportGenerator:
    """Generates comparison reports in various formats"""

    def __init__(
        self,
        result: ComparisonResult,
        id_duplicates: Optional[Dict[str, List[Dict]]] = None,
    ):
        self.result = result
        # {"source1": [...], "source2": [...]} as returned by IDHandler.
        # None means uniqueness was never checked.
        self.id_duplicates = id_duplicates

    def generate_summary(self) -> Dict:
        """Generate a summary of comparison results"""
        summary = {
            "row_counts": {
                "unique_to_source1": len(self.result.unique_to_source1),
                "unique_to_source2": len(self.result.unique_to_source2),
                "differences": len(self.result.differences),
            },
            "column_statistics": {
                col: self._column_summary(col, score)
                for col, score in self.result.column_stats.items()
            },
        }

        scope = self._stats_scope()
        if scope:
            summary["stats_scope"] = scope

        uniqueness = self._id_uniqueness()
        if uniqueness:
            summary["id_uniqueness"] = uniqueness

        if self.result.mixed_blank_key_groups is not None:
            summary["mixed_blank_key_groups"] = self.result.mixed_blank_key_groups

        return summary

    def _id_uniqueness(self) -> Optional[Dict]:
        """Per-side duplicate-key counts

        Duplicate keys make the join pair rows cartesian-style, which invents
        per-column differences, so this belongs in the report rather than in a
        stderr warning nobody keeps.
        """
        if self.id_duplicates is None:
            return None

        uniqueness = {}
        for side, duplicates in self.id_duplicates.items():
            uniqueness[side] = {
                "duplicate_key_groups": len(duplicates),
                "duplicate_rows": sum(dup["count"] for dup in duplicates),
                "examples": [dup["id_values"] for dup in duplicates[:5]],
            }
        return uniqueness

    NOT_APPLICABLE = "n/a"

    def _column_summary(self, col: str, score: Optional[float]) -> Dict:
        """Per-column stats, with direction and coverage where available

        score is None when nothing was paired up, in which case a match
        percentage does not exist and must not be invented.
        """
        if score is None:
            stats = {
                "match_percentage": self.NOT_APPLICABLE,
                "difference_percentage": self.NOT_APPLICABLE,
            }
        else:
            stats = {
                "match_percentage": f"{score*100:.1f}%",
                "difference_percentage": f"{(1-score)*100:.1f}%",
            }

        if self.result.column_directions and col in self.result.column_directions:
            stats["directions"] = self.result.column_directions[col]

        if self.result.column_coverage and col in self.result.column_coverage:
            coverage = self.result.column_coverage[col]
            stats["coverage"] = coverage
            stats["vacuous"] = (
                coverage["source1_non_blank"] == 0
                and coverage["source2_non_blank"] == 0
            )

        return stats

    def vacuous_columns(self) -> List[str]:
        """Compared columns that were blank on every row of both sides"""
        if not self.result.column_coverage:
            return []

        return [
            col
            for col, coverage in self.result.column_coverage.items()
            if coverage["source1_non_blank"] == 0
            and coverage["source2_non_blank"] == 0
        ]

    def _stats_scope(self) -> Optional[Dict]:
        """How many rows the column statistics were computed over

        The percentages in column_statistics only cover rows present on both
        sides, so a reader needs these counts to tell "no differences" from
        "nothing was paired up".
        """
        if self.result.common_row_count is None:
            return None

        return {
            "rows_compared": self.result.common_row_count,
            "joined_rows": self.result.joined_row_count,
            "rows_excluded_as_unique": len(self.result.unique_to_source1)
            + len(self.result.unique_to_source2),
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
        if show_diff and (
            self.result.differences.height > 0
            or self.result.unique_to_source1.height > 0
            or self.result.unique_to_source2.height > 0
        ):
            output.extend(
                ["", f"{Style.BRIGHT}=== Detailed Differences ==={Style.RESET_ALL}"]
            )
            output.append(self._generate_detailed_diff())

        return "\n".join(output)

    def _generate_summary_section(self) -> List[str]:
        """Generate the summary section of the report"""
        summary = self.generate_summary()
        output = []

        output.append(f"{Style.BRIGHT}=== Comparison Summary ==={Style.RESET_ALL}\n")

        # Row counts
        output.append(f"{Style.BRIGHT}Row Counts:{Style.RESET_ALL}")
        output.append(
            f"  Unique to source 1: {Fore.YELLOW}{summary['row_counts']['unique_to_source1']}{Style.RESET_ALL}"
        )
        output.append(
            f"  Unique to source 2: {Fore.YELLOW}{summary['row_counts']['unique_to_source2']}{Style.RESET_ALL}"
        )
        output.append(
            f"  Rows with differences: {Fore.YELLOW}{summary['row_counts']['differences']}{Style.RESET_ALL}\n"
        )

        # ID uniqueness
        if "id_uniqueness" in summary:
            output.append(f"{Style.BRIGHT}ID Uniqueness:{Style.RESET_ALL}")
            if any(
                side["duplicate_key_groups"]
                for side in summary["id_uniqueness"].values()
            ):
                for side, stats in summary["id_uniqueness"].items():
                    groups = stats["duplicate_key_groups"]
                    color = Fore.RED if groups else Fore.GREEN
                    output.append(
                        f"  {side}: {color}{groups} duplicate key group(s) "
                        f"covering {stats['duplicate_rows']} rows{Style.RESET_ALL}"
                    )
                    for example in stats["examples"]:
                        output.append(f"    e.g. {example}")
                output.append(
                    f"  {Fore.RED}Duplicate keys pair rows cartesian-style; "
                    f"per-column differences below may be an artefact"
                    f"{Style.RESET_ALL}"
                )
            else:
                output.append(
                    f"  {Fore.GREEN}Key is unique on both sides{Style.RESET_ALL}"
                )
            output.append("")

        # Column statistics
        output.append(f"{Style.BRIGHT}Column Statistics:{Style.RESET_ALL}")
        if "stats_scope" in summary:
            scope = summary["stats_scope"]
            output.append(
                f"  {Fore.CYAN}Column statistics computed over "
                f"{scope['rows_compared']} of {scope['joined_rows']} joined rows "
                f"({scope['rows_excluded_as_unique']} excluded as unique to one "
                f"side){Style.RESET_ALL}"
            )
        for col, stats in summary["column_statistics"].items():
            if stats["match_percentage"] == self.NOT_APPLICABLE:
                color = Fore.YELLOW
            else:
                match_pct = float(stats["match_percentage"].rstrip("%"))
                color = (
                    Fore.GREEN
                    if match_pct >= 90
                    else (Fore.YELLOW if match_pct >= 70 else Fore.RED)
                )

            output.append(f"  {col}:")
            vacuous_note = (
                f" {Fore.RED}(0 non-blank rows: vacuous){Style.RESET_ALL}"
                if stats.get("vacuous")
                else ""
            )
            output.append(
                f"    Match: {color}{stats['match_percentage']}{Style.RESET_ALL}"
                f"{vacuous_note}"
            )
            output.append(
                f"    Diff:  {color}{stats['difference_percentage']}{Style.RESET_ALL}"
            )

            if "directions" in stats:
                directions = stats["directions"]
                lost_color = Fore.RED if directions["lost"] else Fore.GREEN
                output.append(
                    f"    Agree: {directions['agree']}  "
                    f"Changed: {directions['changed']}  "
                    f"{lost_color}Lost: {directions['lost']}{Style.RESET_ALL}  "
                    f"Gained: {directions['gained']}  "
                    f"Blank both: {directions['blank_both']}"
                )

            if "coverage" in stats:
                coverage = stats["coverage"]
                output.append(
                    f"    Non-blank rows: source1={coverage['source1_non_blank']}, "
                    f"source2={coverage['source2_non_blank']} "
                    f"of {coverage['rows']} compared"
                )

        if self.result.mixed_blank_key_groups is not None:
            mixed = self.result.mixed_blank_key_groups
            output.append("")
            output.append(f"{Style.BRIGHT}Non-Vacuity:{Style.RESET_ALL}")
            output.append(
                f"  Key groups mixing blank and non-blank values in a compared "
                f"column: source1={mixed['source1']}, source2={mixed['source2']}"
            )
            if not any(mixed.values()):
                output.append(
                    f"  {Fore.YELLOW}No key group can express a blank-versus-"
                    f"populated pairing; a clean result here proves little"
                    f"{Style.RESET_ALL}"
                )

        return output

    def _generate_detailed_diff(self) -> str:
        """Generate a detailed diff report showing added, removed, and changed rows"""
        output = []
        term_width = shutil.get_terminal_size().columns
        col_width = min(40, (term_width - 10) // 2)  # Leave room for separators

        # Show removed rows (unique to source 1)
        if self.result.unique_to_source1.height > 0:
            output.extend(
                [
                    "",
                    f"{Style.BRIGHT}Rows Removed (Unique to Source 1):{Style.RESET_ALL}",
                ]
            )
            for row in self.result.unique_to_source1.iter_rows(named=True):
                output.append(f"{Fore.RED}- {dict(row)}{Style.RESET_ALL}")

        # Show added rows (unique to source 2)
        if self.result.unique_to_source2.height > 0:
            output.extend(
                ["", f"{Style.BRIGHT}Rows Added (Unique to Source 2):{Style.RESET_ALL}"]
            )
            for row in self.result.unique_to_source2.iter_rows(named=True):
                output.append(f"{Fore.GREEN}+ {dict(row)}{Style.RESET_ALL}")

        # Show modified rows
        if self.result.differences.height > 0:
            output.extend(["", f"{Style.BRIGHT}Modified Rows:{Style.RESET_ALL}"])

            for row in self.result.differences.iter_rows(named=True):
                id_parts = []
                for id_col in self.result.unique_to_source1.columns:
                    if id_col in row:
                        id_parts.append(f"{id_col}={row[id_col]}")
                id_str = ", ".join(id_parts)
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
                        source2_parts.append(
                            f"{col}={Fore.GREEN}{val2}{Style.RESET_ALL}"
                        )
                    else:
                        source1_parts.append(f"{col}={val1}")
                        source2_parts.append(f"{col}={val2}")
                output.append(f"- {', '.join(source1_parts)}")
                output.append(f"+ {', '.join(source2_parts)}")

        return "\n".join(output)

    @staticmethod
    def _wrap_text(text: str, width: int) -> List[str]:
        """Wrap text to fit within specified width"""
        lines = []
        while text:
            if len(text) <= width:
                lines.append(text)
                break
            # Find last space within width
            space_idx = text.rfind(" ", 0, width)
            if space_idx == -1:  # No space found, force break at width
                lines.append(text[:width])
                text = text[width:]
            else:
                lines.append(text[:space_idx])
                text = text[space_idx + 1 :]
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
            "summary": self.generate_summary(),
            "details": {
                "unique_to_source1": self.result.unique_to_source1.to_dicts(),
                "unique_to_source2": self.result.unique_to_source2.to_dicts(),
                "differences": [],
            },
        }

        # Add detailed differences
        for row in self.result.differences.iter_rows(named=True):
            diff_entry = {"id": row["id"], "changes": {}}

            # Calculate specific changes
            for col in self.result.column_stats.keys():
                val1 = row.get(f"{col}_source1")
                val2 = row.get(f"{col}_source2")
                if val1 != val2:
                    diff_entry["changes"][col] = {"source1": val1, "source2": val2}

            report["details"]["differences"].append(diff_entry)

        if output_file:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
        else:
            return json.dumps(report, indent=2)

    def to_csv(self, output_file: str) -> None:
        """Generate CSV report with detailed results

        Args:
            output_file: Path to output CSV file
        """
        summary = self.generate_summary()

        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f)

            # Write summary section
            writer.writerow(["=== Comparison Summary ==="])
            writer.writerow([])

            # Write row counts
            writer.writerow(["Row Counts"])
            for key, value in summary["row_counts"].items():
                writer.writerow([key, value])
            writer.writerow([])

            # Write ID uniqueness
            if "id_uniqueness" in summary:
                writer.writerow(["ID Uniqueness"])
                writer.writerow(
                    ["Side", "Duplicate Key Groups", "Duplicate Rows"]
                )
                for side, stats in summary["id_uniqueness"].items():
                    writer.writerow(
                        [
                            side,
                            stats["duplicate_key_groups"],
                            stats["duplicate_rows"],
                        ]
                    )
                writer.writerow([])

            # Write the scope the column statistics cover
            if "stats_scope" in summary:
                writer.writerow(["Column Statistics Scope"])
                for key, value in summary["stats_scope"].items():
                    writer.writerow([key, value])
                writer.writerow([])

            # Write column statistics
            writer.writerow(["Column Statistics"])
            writer.writerow(
                [
                    "Column",
                    "Match %",
                    "Difference %",
                    "Agree",
                    "Changed",
                    "Lost",
                    "Gained",
                    "Blank Both",
                    "Source1 Non-blank",
                    "Source2 Non-blank",
                    "Rows Compared",
                    "Vacuous",
                ]
            )
            for col, stats in summary["column_statistics"].items():
                directions = stats.get("directions", {})
                coverage = stats.get("coverage", {})
                writer.writerow(
                    [
                        col,
                        stats["match_percentage"],
                        stats["difference_percentage"],
                        directions.get("agree", ""),
                        directions.get("changed", ""),
                        directions.get("lost", ""),
                        directions.get("gained", ""),
                        directions.get("blank_both", ""),
                        coverage.get("source1_non_blank", ""),
                        coverage.get("source2_non_blank", ""),
                        coverage.get("rows", ""),
                        stats.get("vacuous", ""),
                    ]
                )
            writer.writerow([])

            if "mixed_blank_key_groups" in summary:
                writer.writerow(["Non-Vacuity"])
                writer.writerow(["Side", "Mixed Blank Key Groups"])
                for side, count in summary["mixed_blank_key_groups"].items():
                    writer.writerow([side, count])
                writer.writerow([])

            # Write differences if any exist
            if self.result.differences.height > 0:
                writer.writerow(["=== Detailed Differences ==="])
                writer.writerow([])

                # Write modified rows
                writer.writerow(["Modified Rows"])
                writer.writerow(["ID", "Column", "Source 1 Value", "Source 2 Value"])
                for row in self.result.differences.iter_rows(named=True):
                    id_str = f"id={row['id']}"
                    for col in self.result.column_stats.keys():
                        val1 = row.get(f"{col}_source1")
                        val2 = row.get(f"{col}_source2")
                        if val1 != val2:
                            writer.writerow([id_str, col, val1, val2])
