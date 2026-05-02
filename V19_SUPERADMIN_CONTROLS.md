# V19 Super Admin Controls

Implemented:
1. Three access modes:
   - Super Admin
   - Admin
   - Supervisor

2. Super Admin access includes:
   - Advance Master Edit UI
   - Advance Schedule Edit UI
   - Bulk Leave Upload
   - Password change utility
   - Full operational access

3. Admin access includes:
   - Payroll operations
   - Employee management
   - Leave/Holiday/Advance entry
   - Payroll approval
   - Employee Profile adjustments

4. Supervisor access:
   - Dashboard only
   - Mark Leave
   - Add Advance

5. Special deductions:
   - Calculated from penalty/collaborative logic.
   - Admin now gets Yes/No dropdown in Employee Profile.
   - Default is Yes.
   - Selecting No waives special deductions for that employee/month.

6. Advance deduction:
   - Final payroll deduction is controlled in Person-wise Payroll Exclusions / Deductions.
   - Advance Schedule Review is view-only there.
   - Detailed advance master/schedule edits are under Super Admin only.

7. Bulk upload:
   - Super Admin only.
   - Completion message retained after upload.
   - Duplicate handling available: skip or replace.
