# V40 Asha Payroll Fix

Issue found:
- Payroll calculation was not saving all report-critical fields into payroll_items.
- Fields like Holiday_Exclusions, Leaves_After_Allowed_And_Exclusions, Advance_Prior_Month,
  Advance_Given_This_Month, Advance_Balance_Open and Advance_Balance_Close were missing from saved rows.
- This caused Payroll_Final / Salary Summary to look wrong for employees such as Asha.

Fix:
- Saved payroll row now includes all critical fields.
- Mobile Summary now prefers calculated payroll row values where available.
- For Asha starter data:
  - Monthly Salary: ₹10,000
  - L1 paid leaves: 2
  - No leaves: 2 unused leaves encashed
  - April advance deduction: ₹500
  - Expected net = ₹10,000 + ₹666.67 encashment - ₹500 = ₹10,166.67
