# Implementation Tasks

## 1. Project Setup
- [x] Create project structure and virtual environment using uv
- [x] Set up basic CLI framework using argparse
  - [x] Test: Basic CLI argument parsing
- [x] Create pyproject.toml with dependencies
- [x] Set up testing framework (pytest)
- [x] Create initial README.md

## 2. Data Source Ingestion
- [x] Implement file format detection (CSV/JSONL)
  - [x] Test: Format detection for CSV and JSONL files
- [x] Create CSV reader with configurable delimiter
  - [x] Test: Reading CSV with different delimiters (test_scenarios.md #7)
- [x] Create JSONL reader
  - [x] Test: Reading JSONL files (test_scenarios.md #2)
- [x] Implement chunked reading for large files
  - [x] Test: Processing large files (test_scenarios.md #3)
- [x] Add error handling for file access and parsing
  - [x] Test: Invalid file formats and access errors
- [x] Create data source abstraction layer
  - [x] Test: Common interface for different file types

## 3. Column Mapping
- [x] Implement automatic column mapping
  - [x] Header name similarity matching
    - [x] Test: Basic column name matching (test_scenarios.md #1)
  - [x] Data content similarity analysis
    - [x] Test: Content-based mapping accuracy
- [x] Create configuration file parser (JSON/YAML)
  - [x] Test: Config file parsing and validation
- [x] Implement manual column mapping via config
  - [x] Test: Custom mapping configurations
- [x] Add validation for mapping configuration
  - [x] Test: Invalid mapping scenarios

## 4. Unique Identifier Handling
- [x] Implement automatic ID column detection
  - [x] Column name analysis ("id", "key", etc.)
    - [x] Test: ID column detection (test_scenarios.md #3)
  - [x] Data uniqueness analysis
    - [x] Test: Uniqueness validation
- [x] Add manual ID column specification
  - [x] Test: Custom ID column configuration
- [x] Implement ID column validation
  - [x] Test: Invalid ID columns
- [x] Add duplicate ID detection
  - [x] Test: Duplicate ID handling

## 5. Comparison Engine
- [x] Implement row-level comparison
  - [x] Find rows unique to source 1
    - [x] Test: Unique row detection (test_scenarios.md #1, #2)
  - [x] Find rows unique to source 2
    - [x] Test: Unique row detection (test_scenarios.md #1, #2)
  - [x] Detect rows with matching IDs but different values
    - [x] Test: Value difference detection (test_scenarios.md #2)
- [x] Implement column-level comparison
  - [x] Calculate matching value percentages
    - [x] Test: Similarity calculations
  - [x] Identify columns with highest/lowest similarity
    - [x] Test: Column similarity ranking
- [x] Add support for case-insensitive comparison
  - [x] Test: Case sensitivity handling (test_scenarios.md #6)
- [x] Add support for string trimming
  - [x] Test: String trimming functionality
- [x] Implement column selection/exclusion
  - [x] Test: Column filtering

## 6. Output Generation
- [x] Create summary report generator
  - [x] Row count differences
    - [x] Test: Summary statistics accuracy
  - [x] Column similarity statistics
    - [x] Test: Statistical calculations
- [ ] Implement detailed diff generation
  - [ ] Colorized console output
    - [ ] Test: Console formatting
  - [ ] Side-by-side comparison
    - [ ] Test: Comparison display format
- [ ] Add output format handlers
  - [ ] Console output formatter
    - [ ] Test: Console output formatting
  - [ ] CSV output formatter
    - [ ] Test: CSV output generation
  - [ ] JSON output formatter
    - [ ] Test: JSON output generation
- [ ] Implement drill-down queries
  - [ ] Show unique rows by source
    - [ ] Test: Row filtering
  - [ ] Show differences for specific IDs
    - [ ] Test: ID-based filtering

## 7. Performance Optimization
- [ ] Implement memory-efficient processing
  - [ ] Test: Memory usage with large datasets
- [ ] Add progress indicators for large files
  - [ ] Test: Progress reporting accuracy
- [ ] Optimize comparison algorithms
  - [ ] Test: Performance benchmarks
- [ ] Add performance benchmarking
  - [ ] Test: Benchmark suite execution

## 8. Documentation
- [ ] Write detailed API documentation
- [ ] Create user guide with examples
- [ ] Add command-line help text
- [ ] Document configuration file format
- [ ] Add contributing guidelines

## 9. Final Steps
- [ ] Code cleanup and refactoring
- [ ] Error message improvements
- [ ] Final performance tuning
- [ ] Release preparation
