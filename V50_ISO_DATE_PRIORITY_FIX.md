# V50 ISO Date Priority Fix

Fixed:
- Saved dates are stored as ISO YYYY-MM-DD.
- The previous parser could treat 2026-04-11 as 2026-11-04 because day-first parsing ran too early.
- Parser now detects YYYY-MM-DD first before trying day-first upload formats.
- Leave diagnostics now includes a TOTAL row.
- Payroll diagnostics displays total uploaded rows and counted leave units.

This addresses the case where leave_entries had many April rows saved but diagnostics showed only a subset.
