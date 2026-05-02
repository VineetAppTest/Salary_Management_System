# V36 Advance/Profile Sync

Implemented:
- Advance Updation and Person-wise Payroll Exclusions / Deductions now flow both ways.
- Advance Updation creates the advance case and repayment schedule.
- Employee Profile reads current month deduction from advance_schedule.
- If Admin overrides Advance Deduction in Employee Profile, it syncs back to advance_schedule.
- If no schedule exists and Admin enters deduction, a manual adjustment schedule/case is created.
- Advance Schedule Review now clearly shows linked/synced behavior.
- Advance override step changed to ₹100.
