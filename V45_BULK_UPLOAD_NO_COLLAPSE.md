# V45 Bulk Upload No-Collapse Fix

Fixed the V44 issue:
- Replace entire uploaded month no longer collapses rows by Date + Emp_ID.
- Every uploaded row is saved exactly.
- This fixes cases like expected 63 rows but only 37 saved.
- Append mode now uses full-row matching instead of only Date + Emp_ID.
- Duplicate Date + Emp_ID rows are warned but not removed in replace-month mode.
