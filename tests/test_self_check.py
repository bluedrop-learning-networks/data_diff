import re
import sys

import pytest
from data_diff import main


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text"""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["data_diff", *argv])
    main()


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_self_check_passes_on_a_sound_file(monkeypatch, capsys, tmp_path):
    source = write(tmp_path, "s.csv", "id,value\n1,a\n2,b\n3,c\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [source, "--self-check", "--id-columns=id"])

    output = strip_ansi(capsys.readouterr().out)
    assert exc.value.code == 0
    assert "SELF-CHECK PASSED" in output
    assert "gates read zero" in output


def test_self_check_reports_the_injected_count(monkeypatch, capsys, tmp_path):
    """Six zeroes is also what a broken detector emits"""
    source = write(tmp_path, "s.csv", "id,value\n1,a\n2,b\n3,c\n")

    with pytest.raises(SystemExit):
        run_cli(monkeypatch, [source, "--self-check", "--id-columns=id"])

    output = strip_ansi(capsys.readouterr().out)
    assert "blanked value on 3 row(s); tool reported 3 lost" in output


def test_self_check_fails_when_a_loss_cannot_be_expressed(
    monkeypatch, capsys, tmp_path
):
    """A file with nothing to lose cannot fail, so passing proves nothing"""
    source = write(tmp_path, "s.csv", "id,value\n1,\n2,\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [source, "--self-check", "--id-columns=id"])

    output = strip_ansi(capsys.readouterr().out)
    assert exc.value.code == 1
    assert "SELF-CHECK FAILED" in output
    assert "cannot express a loss" in output
    assert "vacuous" in output


def test_self_check_catches_a_detector_firing_on_a_copy(
    monkeypatch, capsys, tmp_path
):
    """A non-unique key makes pairing cartesian and invents losses"""
    source = write(tmp_path, "s.csv", "id,value\n1,a\n1,\n2,c\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [source, "--self-check", "--id-columns=id"])

    output = strip_ansi(capsys.readouterr().out)
    assert exc.value.code == 1
    assert "SELF-CHECK FAILED" in output
    assert "identity control" in output


def test_self_check_reports_non_vacuity_count(monkeypatch, capsys, tmp_path):
    source = write(tmp_path, "s.csv", "id,part,value\n1,a,set\n1,b,\n2,a,set\n")

    with pytest.raises(SystemExit):
        run_cli(
            monkeypatch,
            [source, "--self-check", "--id-columns=id,part", "--compare-columns=value"],
        )

    output = strip_ansi(capsys.readouterr().out)
    assert "key groups mixing blank and non-blank values: 0" in output


def test_self_check_rejects_a_second_file(monkeypatch, capsys, tmp_path):
    source1 = write(tmp_path, "s1.csv", "id,value\n1,a\n")
    source2 = write(tmp_path, "s2.csv", "id,value\n1,a\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [source1, source2, "--self-check", "--id-columns=id"])

    assert exc.value.code == 1
    assert "takes a single file" in capsys.readouterr().err


def test_source2_still_required_without_self_check(monkeypatch, capsys, tmp_path):
    source = write(tmp_path, "s.csv", "id,value\n1,a\n")

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [source, "--id-columns=id"])

    assert exc.value.code == 1
    assert "source2 is required" in capsys.readouterr().err


def test_self_check_works_on_jsonl(monkeypatch, capsys, tmp_path):
    source = write(
        tmp_path,
        "s.jsonl",
        '{"id": "1", "value": "a"}\n{"id": "2", "value": "b"}\n',
    )

    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [source, "--self-check", "--id-columns=id"])

    assert exc.value.code == 0
    assert "SELF-CHECK PASSED" in strip_ansi(capsys.readouterr().out)
