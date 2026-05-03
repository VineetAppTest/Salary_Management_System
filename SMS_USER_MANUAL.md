# Salary Management System - User Manual

## Purpose
The Salary Management System helps supervisors, admins and tech users manage monthly salary calculation using employee master data, leave entries, advances, payroll calculation and approval.

## Roles
The app has one login. After login, choose one role card:
- Supervisor
- Admin
- Tech

## Demo Mode
Demo Mode is useful during client walkthroughs. When it is ON, technical database details are hidden and business-friendly guidance is shown. Turn it OFF when troubleshooting or managing Supabase setup.

## Supervisor Flow
### What supervisors can do
1. Mark employee leave.
2. Add employee advance.
3. Review recent leave and advance entries.

### Supervisor leave flow
1. Login.
2. Choose Supervisor card.
3. Click Mark Leave.
4. Select employee.
5. Select leave type.
6. Add remarks where required.
7. Save.
8. Check confirmation.

### Supervisor advance flow
1. Login.
2. Choose Supervisor card.
3. Click Add Advance.
4. Select employee.
5. Enter amount and repayment details.
6. Save.
7. Confirm the entry appears in recent advances.

## Admin Flow
### Recommended monthly process
1. Open Payroll Control Centre.
2. Select payroll month.
3. Check readiness cards:
   - Employees ready
   - Leaves uploaded
   - Advances ready
   - Payroll calculated
   - Review and lock
4. Go to Payroll.
5. Generate payroll.
6. Go to Salary Summary.
7. Review employee salary cards and table.
8. Open salary calculation explanation if needed.
9. Go to Payroll Approval.
10. Approve and lock only after final review.

### Admin leave flow
1. Open Leave page.
2. Add or review leave rows.
3. Check that leave rows match the payroll month.
4. Use Payroll page diagnostics if leaves are not reflected.

### Admin advance flow
1. Open Advance page.
2. Add or update advances.
3. Ensure deduction month and deduction amount are correct.
4. Verify effect in Salary Summary after payroll recalculation.

### Employee Profile recalculation flow
Use Employee Profile only for person-wise recalculation or special impact changes.
1. Select employee.
2. Select month.
3. Adjust extra paid leaves, advance deduction or special impact settings.
4. Recalculate selected employee.
5. Recheck Salary Summary.

## Tech Flow
### What tech users can do
1. Bulk leave upload.
2. Manage users and passwords.
3. Edit advance master/schedules.
4. Check database health.
5. Seed/export/reset Supabase data when required.
6. Turn Demo Mode ON/OFF.

### Bulk leave upload flow
1. Open Tech role.
2. Open Bulk Leave Upload.
3. Download template.
4. Fill Date, Emp_ID, Leave_Type, Status and Remarks.
5. Upload CSV.
6. Review validation summary.
7. Click Confirm Bulk Upload Now.
8. Check success message.
9. Use Undo Last Bulk Upload if upload needs reversal.

### Database Health flow
Use this only during setup or troubleshooting.
1. Open Tech.
2. Open Database Health.
3. Confirm storage mode.
4. If setting up Supabase for first time, run schema SQL in Supabase.
5. Click Seed Supabase from CSV.
6. Confirm row counts.
7. Use Reset SMS Tables only if seed fails due to old schema/index issues.

## Payroll confidence checklist
Before approving payroll, confirm:
- Employees count is correct.
- Leave rows for the month are correct.
- Advances and deduction schedule are correct.
- Payroll has been generated after final leave/advance updates.
- Salary Summary is reviewed.
- Any employee-specific recalculation is completed.
- Payroll is approved and locked only after review.

## Recovery features
- Bulk upload creates backup before replacing leave data.
- Undo Last Bulk Upload can restore previous leave data.
- Supabase Export to CSV can be used as backup.
- Database Health row counts help confirm persistence.

## Common issues
### Data not showing after upload
Check whether the correct month was selected and verify row counts.

### Leaves not considered in payroll
Open Payroll page and check Leave Matching Diagnostics.

### App is slow
Supabase uses internet/database calls and may be slower than local CSV. Use normal business pages for daily work and avoid Database Health unless troubleshooting.

### Client demo recommendation
Turn Demo Mode ON. Start from Payroll Control Centre, then open Salary Summary.
