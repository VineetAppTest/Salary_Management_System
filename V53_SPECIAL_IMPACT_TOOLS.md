# V53 Special Impact Tools

Added Special Impact Tools:
- Separate Uninformed Leave impact control.
- Separate Collaborative Leave impact control.
- Payroll page has global controls before payroll generation.
- Employee Profile has person-wise controls for recalculation.
- Uninformed Leave:
  - Apply Yes/No
  - Penalty amount per uninformed leave, default ₹50
- Collaborative Leave:
  - Apply Yes/No
  - Deduct as leave days, default 1.5 days
  - Additional amount per collaborative leave
  - Fixed total collaborative deduction
- Payroll rows now store separate impact fields for audit:
  - Uninformed_Special_Amount
  - Collaborative_Special_Amount
  - Apply_Uninformed_Impact
  - Apply_Collaborative_Impact
  - Collaborative_Impact_Mode
  - Collaborative_Impact_Value
