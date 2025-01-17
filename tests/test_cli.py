import pytest
from datacompare import parse_args


def test_basic_cli_args():
    # Test with minimum required arguments
    test_args = ["file1.csv", "file2.csv"]
    args = parse_args(test_args)
    assert args.source1 == "file1.csv"
    assert args.source2 == "file2.csv"
    assert args.output_format == "console"


def test_optional_args():
    # Test with optional arguments
    test_args = [
        "file1.csv",
        "file2.csv",
        "--mapping=map.json",
        "--id-columns=id,order_id",
        "--output-format=json",
        "--output-file=result.json",
    ]
    args = parse_args(test_args)
    assert args.mapping == "map.json"
    assert args.id_columns == "id,order_id"
    assert args.output_format == "json"
    assert args.output_file == "result.json"
