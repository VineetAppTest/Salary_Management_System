# V46 Strict Bulk Month Replacement

Fixed:
- V45 could append new upload rows but fail to remove existing month rows, causing expected 63 but found 100.
- V46 removes existing rows using a strict parsed month label check.
- Replace entire leave data for uploaded month now means:
  1. remove all saved rows for uploaded month(s)
  2. append every uploaded valid row
  3. verify saved row count equals uploaded valid row count

Demo instruction:
- Tech > Bulk Leave Upload
- Select Replace entire leave data for uploaded month
- Upload file
- Confirm Bulk Upload
- Saved rows should equal valid rows.
