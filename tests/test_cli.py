import sys

import pytest
from data_diff import main, parse_args


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


@pytest.fixture
def duplicate_in_source2(tmp_path):
    """source1 has a unique key; source2 repeats one"""
    source1 = tmp_path / "s1.csv"
    source1.write_text("id,name\n1,Alice\n2,Bob\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("id,name\n1,Alice\n2,Bob\n2,Bob\n")
    return source1, source2


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["data_diff", *argv])
    main()


def test_duplicate_ids_in_source2_are_reported(
    monkeypatch, capsys, duplicate_in_source2
):
    source1, source2 = duplicate_in_source2
    run_cli(monkeypatch, [str(source1), str(source2), "--id-columns=id", "--no-diff"])

    captured = capsys.readouterr()
    assert "source2" in captured.err
    # and it must reach the report a human reads, not just stderr
    assert "ID Uniqueness" in captured.out
    assert "source2" in captured.out


def test_unique_ids_on_both_sides_report_as_unique(monkeypatch, capsys, tmp_path):
    source1 = tmp_path / "s1.csv"
    source1.write_text("id,name\n1,Alice\n2,Bob\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("id,name\n1,Alice\n2,Bob\n")

    run_cli(monkeypatch, [str(source1), str(source2), "--id-columns=id", "--no-diff"])

    captured = capsys.readouterr()
    assert "unique on both sides" in captured.out


def test_strict_ids_exits_non_zero(monkeypatch, capsys, duplicate_in_source2):
    source1, source2 = duplicate_in_source2
    with pytest.raises(SystemExit) as exc:
        run_cli(
            monkeypatch,
            [
                str(source1),
                str(source2),
                "--id-columns=id",
                "--no-diff",
                "--strict-ids",
            ],
        )
    assert exc.value.code == 1


def test_duplicate_ids_are_not_fatal_by_default(
    monkeypatch, capsys, duplicate_in_source2
):
    """Default stays non-fatal so existing callers keep working"""
    source1, source2 = duplicate_in_source2
    run_cli(monkeypatch, [str(source1), str(source2), "--id-columns=id", "--no-diff"])
