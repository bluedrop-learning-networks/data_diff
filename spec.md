**Specification: data_diff CLI Tool**

**2. Objective:**

Provide a robust and user-friendly command-line interface for comparing two data sources, identifying differences in rows and columns, and summarizing data similarities and discrepancies.

**4. Supported Data Formats:**

*   CSV (Comma Separated Values) - with a header row.
*   JSONL (JSON Lines)

**5. Key Features:**

*   **Data Source Ingestion:**
    *   Accept two data source files as input (specified by file paths).
    *   Automatically detect file format (CSV or JSONL).
    *   Handle large datasets efficiently (up to 1 million rows).
    *   Support specifying delimiters in CSV (other than a comma).

*   **Column Mapping:**
    *   **Automatic Mapping:** Intelligently attempt to map columns/properties between the two sources based on:
        *   Header names (CSV) or property names (JSONL).
        *   Data similarity (using techniques like string similarity measures).
    *   **Manual Mapping:** Allow users to specify a custom mapping through a configuration file (e.g., JSON or YAML) or command-line arguments. Example config:

            ```json
            {
              "source1": "file1.csv",
              "source2": "file2.jsonl",
              "id_columns": ["id"],
              "column_mapping": {
                "id": "product_id",
                "name": "product_name",
                "price": "cost"
              }
            }
            ```

*   **Unique Identifier Identification:**
    *   **Automatic Detection:** Attempt to guess the unique identifier column(s) based on data uniqueness and potentially column names (e.g., "id", "key").
    *   **Manual Specification:** Allow users to explicitly define the unique identifier column(s) via the configuration file or command-line arguments.

*   **Comparison & Analysis:**
    *   **Row Comparison:**
        *   Identify rows present in source 1 but not in source 2 (based on the unique identifier).
        *   Identify rows present in source 2 but not in source 1. (based on the unique identifier).
        *   Identify rows with matching unique identifiers but differences in other columns.
        *   Identify if the unique identifier is not unique within either of the sources.
    *   **Column Comparison:**
        *   Calculate and display the percentage of matching values for each mapped column pair.
        *   Highlight columns with the highest and lowest similarity.
    *   **Column Selection/Exclusion:**
        *   Allow users to select or exclude specific columns for comparison when analyzing rows with matching IDs.
    *   **Value-level comparison:**
        *   Allow users to specify a case-insensitive comparison for strings.
        *   Allow users to specify that string should be trimmed before comparison.

*   **Output & Reporting:**
    *   **Summary Report:** Provide a concise summary of the comparison, including:
        *   Number of rows unique to each source.
        *   Number of rows with matching IDs but differing values.
        *   Column similarity statistics (e.g., in a tabular format).
    *   **Detailed Diff:** For rows with differences, provide a user-friendly output showing the differences:
        *   Colorized diff (similar to `git diff`) to highlight changes.
        *   Tabular format showing old vs. new values side-by-side.
    *   **Output Formats:**
        *   Human-readable output to the console (default).
        *   Optionally, output results to a file (e.g., CSV, JSON).
    *   **Drill-Down:** Allow users to retrieve the specific rows or column values that are different (e.g., using flags like `--show-unique-rows-source1`, `--show-diff-for-id=123`).

**6. Command-Line Interface (Examples):**

```bash
# Basic comparison with automatic mapping and ID detection
datacompare file1.csv file2.jsonl

# Specify a custom mapping file
datacompare --mapping mapping.json

# Specify ID columns explicitly
datacompare file1.csv file2.csv --id-columns id,order_id

# Select columns for comparison
datacompare file1.csv file2.csv --compare-columns name,price,quantity

# Show rows unique to source 1
datacompare file1.csv file2.csv --show-unique-rows-source1

# Show diff for a specific row
datacompare file1.csv file2.csv --show-diff-for-id 123

# Output results to a file
datacompare file1.csv file2.csv --output-format json --output-file results.json
```

**7. Error Handling:**

*   Provide informative error messages for invalid input, file format issues, mapping problems, and other potential errors.
*   Gracefully handle large files and memory limitations.

**8. Performance:**

*   Optimized for speed and memory efficiency to handle datasets with up to 1 million rows.
*   Consider using techniques like:
    *   Chunking (processing data in smaller batches).
    *   Indexing (if applicable).
    *   Efficient data structures and algorithms.

**9. Technology Stack (Suggestions):**

*   **Programming Language:** Python (due to its rich data processing libraries).
*   **Potential Libraries:**
    *   `pandas` (for data manipulation and analysis).
    *   `polars` (pandas alternative).
    *   `json` (for handling JSONL).
    *   `csv` (for handling CSV).
    *   `difflib` (for generating diffs).
    *   `argparse` (for building the CLI).
    *   `fuzzywuzzy` (optional, for fuzzy string matching in automatic mapping).

**10. Testing:**

*   **Integration Tests:** Test the entire workflow with various data sources and scenarios.
*   **Test Data:** Test data should include CSVs with at least 100 rows.

