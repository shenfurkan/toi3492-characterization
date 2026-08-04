# Project Behavioral Guidelines for EXONYM

## Testing & Verification Cadence

1. **Selective Test Execution**:
   - Avoid executing `pytest` or running full automated test suites after tasks where no Python source code (`src/`, `tests/`) has been created or modified (e.g., editorial edits, metadata tagging, documentation updates).
   - Executing test suites on purely non-code tasks creates unnecessary operational friction ("red tape").

2. **Milestone & Draft Testing**:
   - Once a manuscript/article or campaign phase draft takes shape, execute test suites (`python -m pytest` and `exonym verify`) more frequently to ensure data integrity, schema validity, and baseline reproducibility.
