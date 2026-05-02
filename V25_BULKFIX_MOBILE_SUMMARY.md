# V25 Bulk Upload Fix + Mobile Salary Summary

Critical fixes:
- Bulk Leave Upload now shows uploaded row count, valid count and error count.
- Bulk upload preview shows all valid rows, not just 20.
- Leave page now shows total saved rows and displays all entries.
- Added download of all leave entries.
- Added persistent confirmation for download/action triggers.
- Added error-row CSV download for failed bulk upload validation.
- Date parsing is more tolerant for Excel/Indian date formats.
- Leave type aliases are normalized.
- Added Admin page: Salary Summary.
- Salary Summary includes:
  Name, Total Pay, Daily Pay @30 days, Advance Prior Month, Advance Current Month, Total Advance, Leaves Taken, Deduction for the Month, Leave Deduction Cost, Net Salary to be Paid, Advance Left.
- Final monthly Excel now includes Mobile_Summary sheet.
