# V54 Special Impact Tools Fixed

Fix over V53:
- Payroll page now includes Special Impact Tools controls before Generate Monthly Payroll.
- `special_config_global` is now defined and passed safely into payroll generation.
- Retains Employee Profile person-wise Special Impact Tools.
- Retains V52 header visibility and prior payroll/leave fixes.

Special Impact Tools:
- Uninformed Leave: Apply Yes/No + penalty per leave.
- Collaborative Leave: Apply Yes/No + method:
  1. Deduct as leave days
  2. Additional amount per collaborative leave
  3. Fixed total collaborative deduction
