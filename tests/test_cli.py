import re
import sys

import pytest
from data_diff import main, parse_args


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text"""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)


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
    assert "ID Uniqueness" in strip_ansi(captured.out)
    assert "source2" in strip_ansi(captured.out)


def test_unique_ids_on_both_sides_report_as_unique(monkeypatch, capsys, tmp_path):
    source1 = tmp_path / "s1.csv"
    source1.write_text("id,name\n1,Alice\n2,Bob\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("id,name\n1,Alice\n2,Bob\n")

    run_cli(monkeypatch, [str(source1), str(source2), "--id-columns=id", "--no-diff"])

    captured = capsys.readouterr()
    assert "unique on both sides" in strip_ansi(captured.out)


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


@pytest.fixture
def differing_key_names(tmp_path):
    """The same two rows, keyed under a different column name per side"""
    source1 = tmp_path / "s1.csv"
    source1.write_text("registrationId,amount\nR1,10\nR2,20\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("identifier,amount\nR1,10\nR2,25\n")
    return source1, source2


def test_exact_pairing_on_differing_key_names(
    monkeypatch, capsys, differing_key_names
):
    """Without this the caller falls back to an unstable business key"""
    source1, source2 = differing_key_names
    run_cli(
        monkeypatch,
        [
            str(source1),
            str(source2),
            "--left-key",
            "registrationId",
            "--right-key",
            "identifier",
            "--no-diff",
        ],
    )

    output = strip_ansi(capsys.readouterr().out)
    assert "Unique to source 1: 0" in output
    assert "Unique to source 2: 0" in output
    assert "Rows with differences: 1" in output


def test_business_key_pairing_loses_rows_exact_pairing_keeps(
    monkeypatch, capsys, tmp_path
):
    """The business key is neither unique nor stable across the two sides"""
    source1 = tmp_path / "s1.csv"
    source1.write_text("registrationId,name,amount\nR1,Alice,10\nR2,Alice,20\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("identifier,name,amount\nR9,Alice,10\nR8,Alice,20\n")

    # Pairing on the business key cannot tell the two Alices apart
    run_cli(monkeypatch, [str(source1), str(source2), "--id-columns=name", "--no-diff"])
    business = capsys.readouterr()
    assert "duplicate key group(s)" in strip_ansi(business.out)

    # The real identity pairs them exactly
    run_cli(
        monkeypatch,
        [
            str(source1),
            str(source2),
            "--left-key",
            "registrationId",
            "--right-key",
            "identifier",
            "--no-diff",
        ],
    )
    exact = strip_ansi(capsys.readouterr().out)
    assert "Unique to source 1: 2" in exact
    assert "Unique to source 2: 2" in exact
    assert "Key is unique on both sides" in exact


def test_composite_exact_key(monkeypatch, capsys, tmp_path):
    source1 = tmp_path / "s1.csv"
    source1.write_text("regId,part,amount\nR1,a,10\nR1,b,20\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("ident,segment,amount\nR1,a,10\nR1,b,25\n")

    run_cli(
        monkeypatch,
        [
            str(source1),
            str(source2),
            "--left-key",
            "regId",
            "--left-key",
            "part",
            "--right-key",
            "ident",
            "--right-key",
            "segment",
            "--no-diff",
        ],
    )

    output = strip_ansi(capsys.readouterr().out)
    assert "Rows with differences: 1" in output
    assert "Key is unique on both sides" in output


def test_exact_key_must_be_unique(monkeypatch, capsys, tmp_path):
    """Uniqueness is asserted, so a violation must fail loudly"""
    source1 = tmp_path / "s1.csv"
    source1.write_text("regId,amount\nR1,10\nR1,20\n")
    source2 = tmp_path / "s2.csv"
    source2.write_text("ident,amount\nR1,10\nR1,20\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(
            monkeypatch,
            [
                str(source1),
                str(source2),
                "--left-key",
                "regId",
                "--right-key",
                "ident",
                "--no-diff",
            ],
        )
    assert exc.value.code == 1
    assert "must be unique on both sides" in capsys.readouterr().err


def test_exact_key_flags_must_be_paired(monkeypatch, capsys, differing_key_names):
    source1, source2 = differing_key_names
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            [str(source1), str(source2), "--left-key", "registrationId"],
        )
    assert "must be given together" in capsys.readouterr().err


def test_exact_key_counts_must_match(monkeypatch, capsys, differing_key_names):
    source1, source2 = differing_key_names
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            [
                str(source1),
                str(source2),
                "--left-key",
                "registrationId",
                "--left-key",
                "amount",
                "--right-key",
                "identifier",
            ],
        )
    assert "pair up in the order given" in capsys.readouterr().err


def test_exact_key_rejects_id_columns(monkeypatch, capsys, differing_key_names):
    source1, source2 = differing_key_names
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            [
                str(source1),
                str(source2),
                "--id-columns=registrationId",
                "--left-key",
                "registrationId",
                "--right-key",
                "identifier",
            ],
        )
    assert "cannot be combined" in capsys.readouterr().err


def test_exact_key_missing_column(monkeypatch, capsys, differing_key_names):
    source1, source2 = differing_key_names
    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            [
                str(source1),
                str(source2),
                "--left-key",
                "nope",
                "--right-key",
                "identifier",
            ],
        )
    assert "not found in source1" in capsys.readouterr().err
