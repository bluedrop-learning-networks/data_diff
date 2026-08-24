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
    # Rows the column stats were computed over, and rows the outer join
    # produced in total. column_stats only sees rows present on both sides,
    # so these are needed to tell "no differences" from "nothing to compare".
    common_row_count: Optional[int] = None
    joined_row_count: Optional[int] = None
    # Per compared column, how the non-agreeing rows break down. A percentage
    # does not say which way a difference runs, and only "lost" is a
    # customer-visible defect. The five buckets partition the common rows.
    column_directions: Optional[Dict[str, Dict[str, int]]] = None
    # Per compared column, how many common rows are non-blank on each side. A
    # column blank everywhere agrees with itself perfectly and proves nothing.
    column_coverage: Optional[Dict[str, Dict[str, int]]] = None
    # Per side, how many key groups hold both a blank and a non-blank value in
    # a compared column. Zero means a self-comparison could not have failed.
    mixed_blank_key_groups: Optional[Dict[str, int]] = None
    # The key the two sides were paired on, so reports can label rows by it
    id_columns: Optional[List[str]] = None


class ComparisonEngine:
    """Handles comparison of two data sources"""

    def __init__(
        self,
        source1_data: pl.DataFrame,
        source2_data: pl.DataFrame,
        id_columns: List[str],
        column_mapping: Dict[str, str],
        config: Optional[ComparisonConfig] = None,
    ):
        self.source1_data = source1_data
        self.source2_data = source2_data
        self.id_columns = id_columns
        self.column_mapping = column_mapping
        self.config = config or ComparisonConfig()

    def _find_unique_rows(self, merged_df: pl.DataFrame, source: int) -> pl.DataFrame:
        """Find rows unique to source 1 or 2"""
        suffix = "" if source == 1 else "_source2"
        other_suffix = "_source2" if source == 1 else ""

        return merged_df.filter(
            pl.all_horizontal(
                [
                    pl.col(f"{c}{other_suffix}").is_null()
                    for c in self.column_mapping.keys()
                    if c not in self.id_columns
                ]
            )
        ).select(
            [
                *[pl.col(f"{c}{suffix}").alias(c) for c in self.id_columns],
                *[
                    pl.col(f"{c}{suffix}").alias(c)
                    for c in self.column_mapping.keys()
                    if c not in self.id_columns
                ],
            ]
        )

    @staticmethod
    def _is_blank(col: str) -> pl.Expr:
        """Null, empty, or whitespace-only"""
        expr = pl.col(col).cast(pl.String, strict=False).str.strip_chars()
        return expr.is_null() | (expr == "")

    def _direction_counts(
        self, common_rows: pl.DataFrame, col: str
    ) -> Dict[str, int]:
        """Split the common rows for one column into direction buckets

        agree uses the same expression as column_stats, so the two always
        agree; the remaining four buckets partition the rest.
        """
        agrees = self._compare_columns(col).fill_null(False)
        blank1 = self._is_blank(col)
        blank2 = self._is_blank(f"{col}_source2")

        counts = common_rows.select(
            agrees.sum().alias("agree"),
            (~agrees & ~blank1 & ~blank2).sum().alias("changed"),
            (~agrees & ~blank1 & blank2).sum().alias("lost"),
            (~agrees & blank1 & ~blank2).sum().alias("gained"),
            (~agrees & blank1 & blank2).sum().alias("blank_both"),
        ).row(0, named=True)

        return {key: int(value) for key, value in counts.items()}

    def _coverage_counts(
        self, common_rows: pl.DataFrame, col: str
    ) -> Dict[str, int]:
        """How many common rows carry a value on each side"""
        counts = common_rows.select(
            (~self._is_blank(col)).sum().alias("source1_non_blank"),
            (~self._is_blank(f"{col}_source2")).sum().alias("source2_non_blank"),
        ).row(0, named=True)

        return {
            **{key: int(value) for key, value in counts.items()},
            "rows": common_rows.height,
        }

    def _count_mixed_blank_key_groups(
        self, df: pl.DataFrame, columns: List[str]
    ) -> int:
        """Key groups holding both a blank and a non-blank value in one column

        A file with none of these cannot exhibit a blank-versus-populated
        pairing, so comparing it against its own copy cannot fail.
        """
        present = [col for col in columns if col in df.columns]
        if not present or df.height == 0:
            return 0

        mixed = df.group_by(self.id_columns).agg(
            [
                (
                    self._is_blank(col).any() & (~self._is_blank(col)).any()
                ).alias(f"__mixed_{index}")
                for index, col in enumerate(present)
            ]
        )
        flags = [f"__mixed_{index}" for index in range(len(present))]

        return int(mixed.select(pl.any_horizontal(flags).sum()).item())

    def _compare_columns(self, col: str) -> pl.Expr:
        """Create comparison expression for a column pair"""
        expr1 = pl.col(col)
        expr2 = pl.col(f"{col}_source2")

        if self.config.trim_strings:
            expr1 = expr1.str.strip_chars()
            expr2 = expr2.str.strip_chars()

        if not self.config.case_sensitive:
            expr1 = expr1.str.to_lowercase()
            expr2 = expr2.str.to_lowercase()

        return (expr1 == expr2) | (expr1.is_null() & expr2.is_null())

    def compare(self) -> ComparisonResult:
        """Perform full comparison of the two data sources"""
        # Start with lazy frames
        lazy1 = self.source1_data.lazy()
        lazy2 = self.source2_data.lazy()

        # Rename columns in source2 lazily
        source2_renamed = lazy2.rename({v: k for k, v in self.column_mapping.items()})

        # Perform outer join
        merged_df = lazy1.join(
            source2_renamed, on=self.id_columns, how="full", suffix="_source2"
        ).collect()

        # Find unique rows
        unique_to_source1 = self._find_unique_rows(merged_df, 1)
        unique_to_source2 = self._find_unique_rows(merged_df, 2)

        # Get common rows
        common_rows = merged_df.filter(
            ~pl.all_horizontal(
                [
                    pl.col(f"{c}_source2").is_null()
                    for c in self.column_mapping.keys()
                    if c not in self.id_columns
                ]
            )
            & ~pl.all_horizontal(
                [
                    pl.col(c).is_null()
                    for c in self.column_mapping.keys()
                    if c not in self.id_columns
                ]
            )
        )

        # Determine columns to compare
        columns_to_compare = (
            self.config.columns_to_compare
            if self.config.columns_to_compare
            else [
                col for col in self.column_mapping.keys() if col not in self.id_columns
            ]
        )

        # Calculate column stats. None when nothing paired up: a match
        # percentage over zero rows does not exist.
        column_stats = {
            col: (
                common_rows.select(self._compare_columns(col)).mean().item()
                if common_rows.height > 0
                else None
            )
            for col in columns_to_compare
        }

        column_directions = {
            col: self._direction_counts(common_rows, col)
            for col in columns_to_compare
        }
        column_coverage = {
            col: self._coverage_counts(common_rows, col)
            for col in columns_to_compare
        }
        mixed_blank_key_groups = {
            "source1": self._count_mixed_blank_key_groups(
                self.source1_data, columns_to_compare
            ),
            "source2": self._count_mixed_blank_key_groups(
                source2_renamed.collect(), columns_to_compare
            ),
        }

        # Find differences
        diff_conditions = []
        for col in columns_to_compare:
            expr1 = pl.col(col)
            expr2 = pl.col(f"{col}_source2")

            if self.config.trim_strings:
                expr1 = expr1.str.strip_chars()
                expr2 = expr2.str.strip_chars()

            if not self.config.case_sensitive:
                expr1 = expr1.str.to_lowercase()
                expr2 = expr2.str.to_lowercase()

            diff_conditions.append(
                ~((expr1 == expr2) | (expr1.is_null() & expr2.is_null()))
            )

        diff_rows = common_rows.filter(pl.any_horizontal(diff_conditions))

        # Process differences in batch
        differences_df = (
            diff_rows.select(
                [
                    *self.id_columns,
                    *[
                        pl.col(col).alias(f"{col}_source1")
                        for col in columns_to_compare
                    ],
                    *[pl.col(f"{col}_source2") for col in columns_to_compare],
                ]
            )
            if diff_rows.height > 0
            else pl.DataFrame()
        )

        return ComparisonResult(
            unique_to_source1=unique_to_source1,
            unique_to_source2=unique_to_source2,
            differences=differences_df,
            column_stats=column_stats,
            common_row_count=common_rows.height,
            joined_row_count=merged_df.height,
            column_directions=column_directions,
            column_coverage=column_coverage,
            mixed_blank_key_groups=mixed_blank_key_groups,
            id_columns=list(self.id_columns),
        )
