import sys
from typing import List, Optional
import argparse
from pathlib import Path
import pandas as pd

from .datasource import create_data_source
from .column_mapper import ColumnMapper
from .id_handler import IDHandler, FatalIDValidationError
from .comparison_engine import ComparisonEngine, ComparisonConfig
from .report_generator import ReportGenerator

def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description='Compare two data sources and identify differences'
    )
    parser.add_argument('source1', help='Path to first data source')
    parser.add_argument('source2', help='Path to second data source')
    parser.add_argument('--mapping', help='Path to mapping configuration file')
    parser.add_argument('--id-columns', help='Comma-separated list of ID columns')
    parser.add_argument('--compare-columns', help='Comma-separated list of columns to compare')
    parser.add_argument('--delimiter', default=',', help='Delimiter for CSV files (default: ,)')
    parser.add_argument('--case-sensitive', action='store_true', help='Enable case-sensitive comparison')
    parser.add_argument('--no-trim', action='store_true', help='Disable string trimming')
    parser.add_argument('--output-format', 
                       choices=['console', 'json', 'csv'], 
                       default='console',
                       help='Output format (default: console)')
    parser.add_argument('--output-file', help='Path to output file')
    parser.add_argument('--no-diff', action='store_true', help='Hide detailed differences in console output')
    return parser.parse_args(args)

def main():
    try:
        args = parse_args()

        # Create data sources
        source1 = create_data_source(args.source1, args.delimiter)
        source2 = create_data_source(args.source2, args.delimiter)

        # Handle column mapping
        mapper = ColumnMapper(source1.columns, source2.columns)
        if args.mapping:
            config = ColumnMapper.load_mapping_config(args.mapping)
            column_mapping = config['column_mapping']
            mapper.validate_mapping(column_mapping)
        else:
            column_mapping = mapper.auto_map_columns()

        # Get data samples for ID detection
        sample1 = list(source1)  # TODO: Consider taking just first N rows for large files
        sample2 = list(source2)

        # Handle ID columns
        id_handler = IDHandler(source1.columns, sample1)
        if args.id_columns:
            id_columns = args.id_columns.split(',')
            validation_errors = id_handler.validate_id_columns(id_columns)
            
            # Handle validation errors
            has_fatal = False
            for error in validation_errors:
                if isinstance(error, FatalIDValidationError):
                    has_fatal = True
                print(f"Error: {error.message}", file=sys.stderr)
                
            if has_fatal:
                sys.exit(1)
        else:
            id_columns = id_handler.detect_id_columns()
            if not id_columns:
                print("Error: No suitable ID columns found. Please specify with --id-columns", file=sys.stderr)
                sys.exit(1)

        # Check for duplicate IDs
        duplicates = id_handler.find_duplicate_ids(id_columns)
        if duplicates:
            print("Warning: Duplicate IDs found:", file=sys.stderr)
            for dup in duplicates:
                print(f"  {dup['id_values']}: {dup['count']} occurrences", file=sys.stderr)

        # Create comparison config
        config = ComparisonConfig(
            case_sensitive=args.case_sensitive,
            trim_strings=not args.no_trim,
            columns_to_compare=args.compare_columns.split(',') if args.compare_columns else None
        )

        # Convert list data to DataFrames
        df1 = pd.DataFrame(sample1)
        df2 = pd.DataFrame(sample2)

        # Run comparison
        engine = ComparisonEngine(
            source1_data=df1,
            source2_data=df2,
            id_columns=id_columns,
            column_mapping=column_mapping,
            config=config
        )
        result = engine.compare()

        # Generate report
        generator = ReportGenerator(result)
        if args.output_format == 'console':
            print(generator.to_console(show_diff=not args.no_diff))
        elif args.output_format == 'json':
            if args.output_file:
                generator.to_json(args.output_file)
            else:
                print(generator.to_json())
        elif args.output_format == 'csv':
            if not args.output_file:
                raise ValueError("--output-file is required for CSV output")
            generator.to_csv(args.output_file)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
