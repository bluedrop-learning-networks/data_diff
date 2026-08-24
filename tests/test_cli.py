import pytest
from data_diff import parse_args


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


def test_repeated_id_columns_is_an_error():
    # Repeating the flag used to silently keep only the last occurrence,
    # which quietly changed which key the comparison paired rows on.
    test_args = ["file1.csv", "file2.csv", "--id-columns=id", "--id-columns=region"]
    with pytest.raises(SystemExit):
        parse_args(test_args)


def test_repeated_compare_columns_is_an_error():
    test_args = [
        "file1.csv",
        "file2.csv",
        "--compare-columns=name",
        "--compare-columns=amount",
    ]
    with pytest.raises(SystemExit):
        parse_args(test_args)


def test_single_occurrence_still_accepted():
    args = parse_args(
        ["file1.csv", "file2.csv", "--id-columns=id,region", "--compare-columns=name"]
    )
    assert args.id_columns == "id,region"
    assert args.compare_columns == "name"
