# data_diff

A command-line tool for comparing two data sources (CSV/JSONL) and identifying differences.

## Read this first: two ways this tool will mislead you

**1. A per-column percentage covers only the rows that paired up.**

Column statistics are computed over rows present on *both* sides of the join.
Rows that exist on one side only are counted separately and are excluded from
every percentage. So `Rows with differences: 0` does not mean "no differences",
it means "no differences among the rows I could pair". A report that had
genuinely lost 50 values read as clean this way: the lost rows had moved keys,
so they were unique-to-source-1 and never entered the column statistics.

Every run now prints the scope, and you should read it before quoting anything:

```
Column statistics computed over 2 of 4 joined rows (2 excluded as unique to one side)
```

**2. A clean self-comparison proves nothing unless the file can express the failure.**

A file compared with its own copy shows zero differences. So does a broken
detector. And a column blank on every row of both sides scores 100.0% while
covering no data at all. Use `--self-check`, which injects a known number of
losses and requires the tool to report exactly that many, and read the
non-vacuity count it prints beside the result.

Related: a percentage does not say which way a difference runs. `62.4%` was once
read as damage when the split was 0 lost and 242,113 *gained* — the new side
filling values the old side left blank. Read the direction counts, not the
percentage.

## Dependencies

- uv (https://docs.astral.sh/uv/getting-started/installation/)

Everything else is declared in `pyproject.toml`; `uv run` installs it.

## Usage

Compare two data files (supports CSV and JSONL formats):

```bash
uv run data_diff source.csv target.jsonl
```

### Pairing the two sides

The single most important choice is what identifies a row. Options, best first:

- **An exact key whose column name differs per side.** Use this whenever both
  sides carry the same real identity under different names. It asserts
  uniqueness and fails loudly if the key is not unique.

  ```bash
  uv run data_diff old.csv new.csv \
      --left-key registrationId --right-key identifier
  ```

  Repeat both flags, in matching order, for a composite key.

- **Identically named ID columns:**

  ```bash
  uv run data_diff --id-columns id,email source.csv target.csv
  ```

- **Auto-detected ID columns** (whatever looks unique and ID-shaped) if you pass
  neither. Convenient, rarely what you want for a migration comparison.

A business key is usually neither unique nor stable across the two sides. On one
dataset, business-key pairing reported 851 rows unique to source1 and 828 to
source2 where exact pairing on the real identity reported 23 and 0.

Repeating `--id-columns` or `--compare-columns` is an error rather than silently
keeping the last occurrence.

### Trust and exit codes

Duplicate keys make the join pair rows cartesian-style, which invents
per-column differences — on one file this turned an identical column into a
reported 80.5% match. Both sides are checked and the finding appears in the
report body, not just on stderr.

```bash
uv run data_diff old.csv new.csv --id-columns id --strict-ids   # duplicates are fatal
uv run data_diff old.csv new.csv --id-columns id --exit-code    # differences reach $?
```

With `--exit-code`:

| Code | Meaning |
| ---- | ------- |
| 0    | No differences, no trust warnings |
| 1    | The run failed (bad arguments, missing file, unreadable input) |
| 2    | Differences found |
| 3    | The comparison cannot be trusted: non-unique key, a vacuous column, or rows excluded from the column statistics |

Without the flag the process exits 0 in all three of those cases, which is how
this tool ends up quoted as evidence of no loss. Pass it in any script.

### Self-check

```bash
uv run data_diff source.csv --self-check --id-columns id
```

Compares the file with its own copy and requires every gate to read zero, then
blanks a compared column on a known number of rows and requires exactly that
many losses to be reported. Exits non-zero if either control fails, including
when the file has no populated compared column and therefore *cannot* fail.

### Output

```bash
uv run data_diff old.csv new.csv --id-columns id --output-format json
uv run data_diff old.csv new.csv --id-columns id --output-format csv --output-file report.csv
uv run data_diff old.csv new.csv --id-columns id --no-diff   # summary only
```

The JSON summary carries everything the console shows: `stats_scope`,
`id_uniqueness`, `mixed_blank_key_groups`, `trust_warnings`, `trustworthy`,
`has_differences`, and per column the match percentage, `directions`,
`coverage` and `vacuous`.

Every compared column reports:

- `Match` / `Diff` — percentage over the *paired* rows only (`n/a` when nothing
  paired), flagged `(0 non-blank rows: vacuous)` when the column is blank on
  both sides throughout
- `Agree` / `Changed` / `Lost` / `Gained` / `Blank both` — counts that partition
  the paired rows. Only **Lost** (a value on the old side, blank on the new one)
  is a customer-visible defect; `Gained` is usually an improvement
- `Non-blank rows` per side, so you can see whether the percentage covers
  anything at all

### Other options

- `--compare-columns a,b` — restrict which columns are compared
- `--delimiter ';'` — CSV delimiter
- `--case-sensitive` / `--no-trim` — comparison strictness
- `uv run data_diff --help` — everything

### Column mapping format

Only needed when column names differ and you are not using
`--left-key`/`--right-key`:

```json
{
    "source1": "old.csv",
    "source2": "new.csv",
    "column_mapping": {
        "source_column1": "target_column1",
        "source_column2": "target_column2"
    }
}
```

`column_mapping` also defines which columns are considered at all, so it must
list every column you want compared.

## Development

Run tests:

```bash
uv run --extra dev pytest
```

## Exit codes

Exit codes are on by default. `--no-exit-code` restores the old always-zero behaviour.

| code | meaning |
|---|---|
| 0 | no differences |
| 1 | the run failed (bad arguments, unreadable input, `--strict-ids` violation) |
| 2 | differences found |
| 3 | **the comparison cannot be trusted** — a non-unique key, a column blank on every row, or rows excluded from the column statistics because their key did not pair |

Code 3 is the one worth wiring into a check. It is the state that otherwise reads as
success, and it is how this tool ends up quoted as evidence that nothing was lost.
