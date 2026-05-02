# V38 Payroll Month Rule + Leave Calculation Fix

Implemented:
- Payroll generation now blocked until selected month is complete.
- Employee Profile recalculation also blocked until month is complete.
- Payroll page now shows leaves detected for selected month before calculation.
- Leave type is normalized inside payroll calculation, not only during upload.
- Rejected/cancelled leave rows are ignored.
- This fixes cases where uploaded leave rows were visible but not counted due to text mismatch.
- Payroll report and approval report now use sticky/frozen Name column.
- Audit spreadsheet view remains inside expander.

Rule:
- Do not calculate/approve payroll before the 1st after month-end.
