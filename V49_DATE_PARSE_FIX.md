# V49 Date Parsing Fix

Issue:
- Leave entries showed 63 rows saved, but Payroll detected only 1 for Apr-2026.
- Root cause: inconsistent date parsing/month filtering across upload, payroll, diagnostics and reports.

Fix:
- Added robust app-wide date parser.
- Supports DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY and mixed date text.
- Payroll, diagnostics, bulk upload verification and leave cleanup now use the same parser.
- Payroll page warns if leave file has rows but selected month detects none.
