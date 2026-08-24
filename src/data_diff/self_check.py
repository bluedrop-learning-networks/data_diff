"""Positive controls for the comparison itself

Six zeroes is what a working comparison of a file with its own copy emits,
and also what a broken detector emits. These controls compare a file with
its own copy, then with a copy carrying a known number of injected losses,
and check the tool reports exactly that many.
"""

import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from colorama import Fore, Style

from .datasource import create_data_source, detect_file_format

# How many losses to inject when the file has room for them
INJECTED_LOSSES = 3


def _write_copy(rows: List[Dict], columns: List[str], path: Path, fmt: str,
                delimiter: str) -> None:
    """Write rows back out in the format they were read from"""
    if fmt == "jsonl":
        with path.open("w") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        return

    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def _pick_injection_column(generator) -> Optional[Tuple[str, int]]:
    """The compared column with the most values to blank out"""
    coverage = generator.result.column_coverage or {}
    candidates = [
        (col, counts["source1_non_blank"])
        for col, counts in coverage.items()
        if counts["source1_non_blank"] > 0
    ]
    if not candidates:
        return None

    return max(candidates, key=lambda pair: pair[1])


def _inject_losses(path: str, column: str, count: int, delimiter: str,
                   target: Path) -> int:
    """Blank `column` on up to `count` rows that currently carry a value"""
    fmt = detect_file_format(path)
    source = create_data_source(path, delimiter)
    columns = list(source.columns)
    rows = list(source)

    injected = 0
    for row in rows:
        if injected >= count:
            break
        value = row.get(column)
        if value is not None and str(value).strip() != "":
            row[column] = ""
            injected += 1

    _write_copy(rows, columns, target, fmt, delimiter)

    return injected


def run_self_check(args, compare) -> int:
    """Run the controls and return the process exit code

    compare is the (path1, path2, args) -> (generator, duplicates) callable,
    passed in so this module does not import the CLI back.
    """
    if args.source2:
        print(
            "Error: --self-check takes a single file; source2 was also given",
            file=sys.stderr,
        )
        return 1

    output = []
    failures = []

    # Control 1: a file compared with its own copy must show nothing at all
    identity, duplicates = compare(args.source1, args.source1, args)
    result = identity.result

    gates = {
        "unique_to_source1": len(result.unique_to_source1),
        "unique_to_source2": len(result.unique_to_source2),
        "differences": len(result.differences),
        "duplicate_key_groups": sum(len(dups) for dups in duplicates.values()),
    }
    for column, directions in (result.column_directions or {}).items():
        for direction in ("changed", "lost", "gained"):
            gates[f"{column}.{direction}"] = directions[direction]

    output.append(f"{Style.BRIGHT}Identity control (file vs its own copy)"
                  f"{Style.RESET_ALL}")
    for gate, value in gates.items():
        if value:
            failures.append(f"identity control: {gate} reported {value}, expected 0")
            output.append(f"  {Fore.RED}{gate}: {value} (expected 0)"
                          f"{Style.RESET_ALL}")
    if not failures:
        output.append(f"  {Fore.GREEN}all {len(gates)} gates read zero"
                      f"{Style.RESET_ALL}")

    # What that zero is worth: a file with no key group holding both a blank
    # and a populated value cannot exhibit the failure mode at all
    mixed = result.mixed_blank_key_groups or {}
    vacuous = identity.vacuous_columns()
    output.append("")
    output.append(f"{Style.BRIGHT}Non-vacuity{Style.RESET_ALL}")
    output.append(
        f"  key groups mixing blank and non-blank values: "
        f"{mixed.get('source1', 0)}"
    )
    output.append(f"  rows compared: {result.common_row_count}")
    if vacuous:
        output.append(
            f"  {Fore.YELLOW}columns blank on every row (vacuous): "
            f"{', '.join(vacuous)}{Style.RESET_ALL}"
        )

    # Control 2: inject a known number of losses and require exactly that many
    output.append("")
    output.append(f"{Style.BRIGHT}Loss-injection control{Style.RESET_ALL}")
    picked = _pick_injection_column(identity)
    if picked is None:
        failures.append(
            "loss-injection control: no compared column carries a value, so "
            "this file cannot express a loss and a clean result proves nothing"
        )
        output.append(
            f"  {Fore.RED}no compared column carries a value; a loss cannot "
            f"be injected{Style.RESET_ALL}"
        )
    else:
        column, available = picked
        wanted = min(INJECTED_LOSSES, available)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / f"injected{Path(args.source1).suffix or '.csv'}"
            injected = _inject_losses(
                args.source1, column, wanted, args.delimiter, target
            )
            mutated, _ = compare(args.source1, str(target), args)

        reported = (mutated.result.column_directions or {}).get(column, {}).get(
            "lost", 0
        )
        output.append(
            f"  blanked {column} on {injected} row(s); tool reported "
            f"{reported} lost"
        )
        if reported != injected:
            failures.append(
                f"loss-injection control: injected {injected} losses in "
                f"{column} but the tool reported {reported}"
            )
            output.append(
                f"  {Fore.RED}expected {injected}, got {reported}{Style.RESET_ALL}"
            )
        else:
            output.append(f"  {Fore.GREEN}detector reports exactly the injected "
                          f"count{Style.RESET_ALL}")

        stray = len(mutated.result.unique_to_source1) + len(
            mutated.result.unique_to_source2
        )
        if stray:
            failures.append(
                f"loss-injection control: blanking a value moved {stray} row(s) "
                f"out of the paired set"
            )

    output.append("")
    if failures:
        output.append(f"{Fore.RED}{Style.BRIGHT}SELF-CHECK FAILED"
                      f"{Style.RESET_ALL}")
        for failure in failures:
            output.append(f"{Fore.RED}  - {failure}{Style.RESET_ALL}")
    else:
        output.append(f"{Fore.GREEN}{Style.BRIGHT}SELF-CHECK PASSED"
                      f"{Style.RESET_ALL}")

    print("\n".join(output))

    return 1 if failures else 0
