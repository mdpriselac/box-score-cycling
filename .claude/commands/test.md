---
description: Run tests and analyze any failures
argument-hint: [file path, marker, or pytest flags]
---

# Run Tests

Run the project test suite and provide analysis of results.

## Steps

1. **Determine scope**: Based on `$ARGUMENTS`:
   - No arguments → run all tests: `uv run pytest`
   - A marker like `unit` or `integration` → `uv run pytest -m <marker>`
   - A file path → `uv run pytest <path>`
   - Any other pytest flags → pass through directly

2. **Run tests**:
   ```bash
   uv run pytest $ARGUMENTS -v
   ```

3. **Analyze results**:
   - If all tests pass, report the summary (number of tests, time elapsed)
   - If tests fail, for each failure:
     - Identify the failing test and the assertion or error
     - Read the relevant source code to understand what's being tested
     - Explain why it likely failed
     - Suggest a fix

4. **Check coverage gaps**: If the user asked about coverage or all tests passed, note any obvious areas lacking test coverage based on the test file structure in `cycling_project/tests/`.
