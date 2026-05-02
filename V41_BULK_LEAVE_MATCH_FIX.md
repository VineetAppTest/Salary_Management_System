# V41 Bulk Leave Match Fix

Issue fixed:
- Bulk uploaded leaves could appear in leave_entries but still not count in payroll if Emp_ID/name formatting differed.
- Payroll now normalizes employee IDs and names before matching leaves.
- Example accepted mappings:
  - E_Asha
  - Asha
  - e asha / E-Asha / E_Asha with spaces/case differences
- Payroll calculation now normalizes leave types again before counting.
- Rejected/cancelled leaves remain ignored.
- Added Payroll > Leave matching diagnostics.
- Added Employee Profile > Leave matching check for selected employee.

This specifically addresses cases where Asha has 15+ uploaded leaves but payroll was still treating her as no-leave.
