# V51 Advance Summary Fix

Fixed Salary Summary advance split:
- Advance Prior Month now reflects current-month deduction lines for advance IDs created before the selected month.
- Advance Current Month now reflects current-month deduction lines for advance IDs created in the selected month.
- Total Advance = Advance Prior Month + Advance Current Month.
- This addresses the Pooja case where 2k prior month + 2k current month should show total advance as 4k, not 2k.
