# V57 Profile-Only Special Logic

Fixed:
- Collaborative impact was being applied inherently during regular payroll.
- Regular Payroll now counts Collaborative Leave as 1 normal leave.
- Collaborative 1.5 impact applies only when activated on Employee Profile for the selected employee.
- Uninformed penalty is also profile-only by default, not globally applied during regular payroll.
- Employee Profile Special Impact Tools now default to No.
- Payroll page wording clarified:
  - Step 1 = regular overall payroll only
  - Step 2 = Employee Profile person-wise special impact recalculation

Example:
- Kiran with 4 regular leaves + 5 collaborative leaves:
  - Regular payroll Leave Units = 9
  - If Collaborative Impact is activated in Employee Profile with 1.5 days, Leave Units = 11.5
