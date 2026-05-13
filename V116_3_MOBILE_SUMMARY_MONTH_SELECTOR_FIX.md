# WageWise v116.3 - Mobile Salary Summary Month Selector Fix

## P0 fix
- Fixed Mobile Salary Summary month dropdown so recalculated months such as Apr-2026 remain selectable.
- Month selector now builds options from multiple trusted payroll-related sources:
  - payroll_items.Month
  - leave_adjustment_log.Month
  - advance_schedule.Deduction_Month
  - last recalculated month stored in session state
- Month values are normalized to the app format, e.g. Apr-2026, even if stored as April-2026 or date-like values.
- Month list is sorted chronologically instead of relying on raw table insertion order.

## Scope control
- No payroll calculation formula changed.
- No advance logic changed.
- No holiday logic changed.
- No database schema changed.

## Expected result
After April payroll is generated or recalculated, Apr-2026 appears in Mobile Salary Summary > Select month and can be selected normally.
