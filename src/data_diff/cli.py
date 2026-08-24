import sys
from typing import List, Optional
import argparse
from pathlib import Path
import polars as pl

from .datasource import create_data_source
from .column_mapper import ColumnMapper
from .id_handler import IDHandler, FatalIDValidationError, WarningIDValidationError
from .comparison_engine import ComparisonEngine, ComparisonConfig
from .report_generator import ReportGenerator
from .self_check import run_self_check


class SingleUseArgument(argparse.Action):
    """Reject a flag passed more than once.

    argparse's default is to keep only the last occurrence, which silently
    changes which columns are used without any hint in the output.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(
                f"{option_string} was given more than once; pass a single "
                "comma-separated list instead of repeating the flag"
            )
        setattr(namespace, self.dest, values)


# Exit codes used with --exit-code. 1 stays reserved for a failed run.
EXIT_NO_DIFFERENCES = 0
EXIT_ERROR = 1
EXIT_DIFFERENCES = 2
EXIT_UNTRUSTED = 3


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Compare two data sources and identify differences"
    )
    parser.add_argument("source1", help="Path to first data source")
    parser.add_argument(
        "source2", nargs="?", help="Path to second data source"
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Run the positive controls on source1 alone: compare it with "
        "its own copy, then with a copy carrying a known number of injected "
        "losses, and check the tool reports exactly that many",
    )
    parser.add_argument("--mapping", help="Path to mapping configuration file")
    parser.add_argument(
        "--id-columns",
        action=SingleUseArgument,
        help="Comma-separated list of ID columns",
    )
    parser.add_argument(
        "--compare-columns",
        action=SingleUseArgument,
        help="Comma-separated list of columns to compare",
    )
    parser.add_argument(
        "--delimiter", default=",", help="Delimiter for CSV files (default: ,)"
    )
    parser.add_argument(
        "--case-sensitive", action="store_true", help="Enable case-sensitive comparison"
    )
    parser.add_argument(
        "--left-key",
        action="append",
        metavar="COLUMN",
        help="Unique key column in source1, paired in order with --right-key. "
        "Repeat both for a composite key. Replaces --id-columns and asserts "
        "uniqueness on both sides",
    )
    parser.add_argument(
        "--right-key",
        action="append",
        metavar="COLUMN",
        help="Unique key column in source2 corresponding to --left-key",
    )
    parser.add_argument(
        "--exit-code",
        action="store_true",
        help=f"Exit {EXIT_DIFFERENCES} when differences are found and "
        f"{EXIT_UNTRUSTED} when the comparison cannot be trusted (non-unique "
        f"key, vacuous column, rows excluded from the column statistics). "
        f"Without this the process exits 0 in all three cases",
    )
    parser.add_argument(
        "--strict-ids",
        action="store_true",
        help="Exit non-zero if the ID columns are not unique on either side "
        "(default: report and continue)",
    )
    parser.add_argument(
        "--no-trim", action="store_true", help="Disable string trimming"
    )
    parser.add_argument(
        "--output-format",
        choices=["console", "json", "csv"],
        default="console",
        help="Output format (default: console)",
    )
    parser.add_argument("--output-file", help="Path to output file")
    parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Hide detailed differences in console output",
    )
    return parser.parse_args(args)


def fail(message: str) -> None:
    """Report a usage problem and stop, without a traceback"""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(EXIT_ERROR)


def resolve_exact_keys(args, source1, source2, column_mapping):
    """Pair the two sides on a declared key whose names differ per side

    Returns (id_columns, column_mapping). The key pair is folded into the
    column mapping so the engine renames source2's key to source1's name
    before joining.
    """
    if not (args.left_key and args.right_key):
        fail("--left-key and --right-key must be given together")
    if len(args.left_key) != len(args.right_key):
        fail(
            f"--left-key was given {len(args.left_key)} time(s) but --right-key "
            f"{len(args.right_key)}; they pair up in the order given"
        )
    if args.id_columns:
        fail("--id-columns cannot be combined with --left-key/--right-key")

    for left, right in zip(args.left_key, args.right_key):
        if left not in source1.columns:
            fail(f"--left-key column '{left}' not found in source1")
        if right not in source2.columns:
            fail(f"--right-key column '{right}' not found in source2")
        if (
            left != right
            and left in source2.columns
            and left not in column_mapping.values()
        ):
            fail(
                f"source2 already has a column named '{left}', so renaming "
                f"'{right}' to it would collide; map it with --mapping instead"
            )

        column_mapping = {
            key: value
            for key, value in column_mapping.items()
            if key != left and value != right
        }
        column_mapping[left] = right

    return list(args.left_key), column_mapping


def run_comparison(path1: str, path2: str, args):
    """Compare two files and return (report generator, per-side duplicates)"""
    # Create data sources
    source1 = create_data_source(path1, args.delimiter)
    source2 = create_data_source(path2, args.delimiter)

    # Handle column mapping
    mapper = ColumnMapper(source1.columns, source2.columns)
    if args.mapping:
        config = ColumnMapper.load_mapping_config(args.mapping)
        column_mapping = config["column_mapping"]
        mapper.validate_mapping(column_mapping)
    else:
        column_mapping = mapper.auto_map_columns()

    # Get data samples for ID detection
    sample1 = list(
        source1
    )  # TODO: Consider taking just first N rows for large files
    sample2 = list(source2)

    # Handle ID columns
    id_handler = IDHandler(source1.columns, sample1)
    id_handler2 = IDHandler(source2.columns, sample2)
    exact_pairing = bool(args.left_key or args.right_key)
    if exact_pairing:
        id_columns, column_mapping = resolve_exact_keys(
            args, source1, source2, column_mapping
        )
    elif args.id_columns:
        id_columns = args.id_columns.split(",")
        validation_errors = id_handler.validate_id_columns(id_columns)

        # Handle validation errors
        has_fatal = False
        for error in validation_errors:
            if isinstance(error, FatalIDValidationError):
                has_fatal = True
            prefix = (
                "Warning: "
                if isinstance(error, WarningIDValidationError)
                else "Error: "
            )
            print(f"{prefix}{error.message}", file=sys.stderr)

        if has_fatal:
            sys.exit(EXIT_ERROR)
    else:
        id_columns = id_handler.detect_id_columns()
        if not id_columns:
            print(
                "Error: No suitable ID columns found. Please specify with --id-columns",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERROR)

    # The ID columns carry source2's own names
    id_columns_source2 = [column_mapping.get(col, col) for col in id_columns]

    # A missing ID column on source2 would fail the join later with a much
    # less obvious message
    source2_errors = [
        error
        for error in id_handler2.validate_id_columns(id_columns_source2)
        if isinstance(error, FatalIDValidationError)
    ]
    if source2_errors:
        for error in source2_errors:
            print(f"Error: {error.message} (source2)", file=sys.stderr)
        sys.exit(EXIT_ERROR)

    # Check for duplicate IDs on both sides. Unequal group sizes between the
    # sides are what make pairing invent per-column differences, so a check
    # of source1 alone can miss the cause entirely.
    id_duplicates = {
        "source1": id_handler.find_duplicate_ids(id_columns),
        "source2": id_handler2.find_duplicate_ids(id_columns_source2),
    }
    for side, duplicates in id_duplicates.items():
        if duplicates:
            print(f"Warning: Duplicate IDs found in {side}:", file=sys.stderr)
            for dup in duplicates:
                print(
                    f"  {dup['id_values']}: {dup['count']} occurrences",
                    file=sys.stderr,
                )

    # An exact key asserts uniqueness, so a violation is a bad assertion
    # rather than something to warn about and carry on from
    if exact_pairing and any(id_duplicates.values()):
        fail(
            "--left-key/--right-key must be unique on both sides; see the "
            "duplicates reported above"
        )

    # Create comparison config
    config = ComparisonConfig(
        case_sensitive=args.case_sensitive,
        trim_strings=not args.no_trim,
        columns_to_compare=args.compare_columns.split(",")
        if args.compare_columns
        else None,
    )

    # Convert list data to DataFrames
    df1 = pl.DataFrame(sample1)
    df2 = pl.DataFrame(sample2)

    # Run comparison
    engine = ComparisonEngine(
        source1_data=df1,
        source2_data=df2,
        id_columns=id_columns,
        column_mapping=column_mapping,
        config=config,
    )
    result = engine.compare()

    return ReportGenerator(result, id_duplicates=id_duplicates), id_duplicates


def main():
    try:
        args = parse_args()

        if args.self_check:
            sys.exit(run_self_check(args, run_comparison))

        if not args.source2:
            fail("source2 is required unless --self-check is given")

        generator, id_duplicates = run_comparison(args.source1, args.source2, args)

        if args.output_format == "console":
            print(generator.to_console(show_diff=not args.no_diff))
        elif args.output_format == "json":
            if args.output_file:
                generator.to_json(args.output_file)
            else:
                print(generator.to_json())
        elif args.output_format == "csv":
            if not args.output_file:
                raise ValueError("--output-file is required for CSV output")
            generator.to_csv(args.output_file)

        if args.strict_ids and any(id_duplicates.values()):
            print(
                "Error: --strict-ids: the ID columns are not unique",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERROR)

        if args.exit_code:
            if generator.trust_warnings():
                sys.exit(EXIT_UNTRUSTED)
            if generator.has_differences():
                sys.exit(EXIT_DIFFERENCES)
            sys.exit(EXIT_NO_DIFFERENCES)

    except Exception as e:
        import traceback
        print(f"Error: {str(e)}", file=sys.stderr)
        print("\nTraceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
