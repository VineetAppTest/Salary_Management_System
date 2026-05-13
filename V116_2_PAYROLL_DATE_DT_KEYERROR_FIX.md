# WageWise v116.2 - Payroll Date_dt KeyError Fix

## P0 fix
Fixed a payroll crash where an employee/month with no matching leave rows could produce an empty leave DataFrame without `Date_dt`, causing `sort_values("Date_dt")` to raise `KeyError`.

## Behaviour
- Payroll now safely continues when an employee has no leave entries for the selected month.
- Missing `Date_dt` is created as `NaT` before sorting.
- No payroll formula, advance logic, holiday logic, database schema, or existing data is changed.

## Validation
- `app.py` compile check passed.
- ZIP integrity check passed.
