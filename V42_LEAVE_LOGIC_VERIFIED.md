# V42 Leave Logic Verified

Fixed:
- Payroll leave calculation now defensively counts uploaded bulk leaves.
- Leave type variations with invisible spaces/dashes/case differences are handled.
- If leave rows match but count as zero units, a diagnostic row is created.
- Payroll diagnostics now show Uploaded Leave Rows, Counted Leave Units, Allowed Leaves, Expected LOP, Expected Leave Deduction.

Uploaded file validation:
- Total rows: 62
- Asha leave units: 15.0
- Asha allowed L1 leaves: 2
- Asha expected LOP: 13.0
- Asha expected leave deduction: ₹4333.33
- Asha April advance deduction: ₹500.0
- Asha expected net salary: ₹5166.67
