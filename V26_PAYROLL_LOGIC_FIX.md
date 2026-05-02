# V26 Payroll Logic Fix

Updated as requested:
- Report header changed from Daily Pay @30 days to Daily Wage.
- Payroll_Final Present Days now equals Total Days - LOP Days.
- Advance Prior Month is prior advance carry-forward after current month scheduled deduction for prior advances.
- Advance Current Month is advance taken in the current month.
- Deduction for the Month is current month scheduled advance deduction.
- Leave Deduction Cost in summary is: (Total leaves taken - Level leave allowance L1/L2) × Daily Wage.
- Mobile Summary and Excel Mobile_Summary use the corrected headers/formulas.
- Payroll items now store Leave_Deduction_Cost and Advance_Prior_Month.
