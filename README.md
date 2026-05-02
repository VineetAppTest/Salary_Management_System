# Salary Management System - Streamlit Cloud Build

## Corrected access structure

There is only ONE login.

Default login:
- Email: `demo@sms.local`
- Password: `demo123`

After login, the user sees three role cards:
- Admin
- Supervisor
- Tech

The same logged-in user can enter any of the three roles.  
This is meant to isolate functions, not create separate user identities.

## Role structure

### Admin
Payroll operations:
- Employees
- Leave
- Holiday
- Advance
- Payroll
- Payroll Approval
- Employee Profile
- Logs

### Supervisor
Simple daily entry:
- Mark Leave
- Add Advance

### Tech
Technical utilities only:
- Bulk Leave Upload
- Advance Master Edit
- Advance Schedule Edit
- Password Change

## Streamlit Cloud

Main file path: `app.py`


# V22 Advance Reconciliation Fix

Fixed:
- Advance Cases and Advance Schedule now reconcile through Tech > Advance Master Edit.
- Editing an Advance Case can rebuild the schedule automatically.
- Editing an Advance Schedule can sync the Advance Case amount with the total schedule.
- Reconciliation summary added with Amount Given, Schedule Total, Difference and Reconciled status.
- Auto Rebuild All Unreconciled Schedules button added.
- All amount increment/decrement controls changed to ₹100.


# V23 Unified Advance Editor

Changed:
- Replaced separate Advance Case and Advance Schedule editing with one Unified Advance Editor.
- Saving an advance now writes both advance_cases and advance_schedule together.
- Create New Advance also creates both case and schedule together.
- Reconciliation status remains visible.
- ₹100 increment/decrement retained.
- Confirmation messages added for successful Tech actions.


# V24 Clean Unified Advance Editor

Changed:
- Removed employee dropdown from edit section.
- Advance ID is now the only selector for existing advances.
- Employee is displayed read-only.
- Employee selection is available only while creating a new advance.
- Layout is now:
  1. Reconciliation Status
  2. Select Advance
  3. Advance Summary
  4. Edit Advance Controls
  5. Schedule Preview
- This prevents accidental employee switching and keeps advance_cases and advance_schedule aligned.


# V25 Bulk Upload Fix + Mobile Salary Summary

Critical fixes:
- Bulk Leave Upload now shows uploaded row count, valid count and error count.
- Bulk upload preview shows all valid rows, not just 20.
- Leave page now shows total saved rows and displays all entries.
- Added download of all leave entries.
- Added persistent confirmation for download/action triggers.
- Added error-row CSV download for failed bulk upload validation.
- Date parsing is more tolerant for Excel/Indian date formats.
- Leave type aliases are normalized.
- Added Admin page: Salary Summary.
- Salary Summary includes:
  Name, Total Pay, Daily Pay @30 days, Advance Prior Month, Advance Current Month, Total Advance, Leaves Taken, Deduction for the Month, Leave Deduction Cost, Net Salary to be Paid, Advance Left.
- Final monthly Excel now includes Mobile_Summary sheet.


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


# V27 Bulk Upload Confirmation

Restored:
- Balloons animation after successful bulk leave upload.
- Success message remains visible after completion.
- Toast confirmation added for extra clarity.


# V28 Mobile Salary Summary UI

Updated:
- Mobile Salary Summary now trims extra empty rows.
- Added app-like summary cards.
- Added phone-friendly HTML summary table.
- Name column stays sticky/fixed while scrolling right.
- Spreadsheet-style dataframe moved inside optional expander.
- CSV download still available.


# V29 Responsive Polish

Final phone + laptop optimisation pass:
- Improved mobile spacing and full-width controls.
- Better laptop/tablet max-width and padding.
- Download buttons now have clear green action styling.
- Navigation buttons stack cleanly on phone.
- Inputs use 16px font on phone to avoid browser zoom.
- Tabs are horizontally scrollable on phone.
- Cards, metrics, forms and tables have improved spacing.
- Mobile Salary Summary sticky-name table retained.
- Compile check passed.


# V30 Customer Experience Fix

Fixed:
- Celebratory balloons restored for successful save/action completion after reruns.
- Toast confirmation added where supported.
- Persistent success message remains visible.
- Mobile Salary Summary table height constrained to avoid large empty white space above/below table.
- Table rows tightened for mobile.
- Optional spreadsheet view height reduced dynamically.
- Sticky Name column retained.

Suggestion from Victor/team:
- Keep the app-like summary as the default view.
- Keep spreadsheet view hidden in expander for audit/admin review only.
- For future production, add a short "last action completed" bar at top for every role.


# V31 Summary Default UX

Implemented accepted suggestion:
- App-style Mobile Salary Summary is now positioned as the default view.
- Spreadsheet/raw table moved under `Audit view / spreadsheet view`.
- Added helper text to guide users to use the app-style summary for daily use.
- Sticky Name column retained.


# V32 User Manager

Changes:
- Removed demo/default login details from the login page.
- Upgraded Tech > Users & Password into User / Member Manager.
- Added create login/member.
- Added edit existing login email ID.
- Added edit display name, role, active/inactive status.
- Added password reset while editing.
- Added delete login with confirmation.
- Prevents duplicate login email IDs.
- Prevents deleting the last remaining login.


# V36 Advance/Profile Sync

Implemented:
- Advance Updation and Person-wise Payroll Exclusions / Deductions now flow both ways.
- Advance Updation creates the advance case and repayment schedule.
- Employee Profile reads current month deduction from advance_schedule.
- If Admin overrides Advance Deduction in Employee Profile, it syncs back to advance_schedule.
- If no schedule exists and Admin enters deduction, a manual adjustment schedule/case is created.
- Advance Schedule Review now clearly shows linked/synced behavior.
- Advance override step changed to ₹100.


# V37 Consolidated Safety Build

Merged critical checks from V33, V34, V35 into latest V36:
- V33 no-leave safety restored.
- Empty leave table is valid.
- Leave page shows clear no-leave message.
- V34 no-advance/no-schedule defensive handling retained.
- Blank/missing CSV files handled safely.
- Dashboard and supervisor recent entries are safe with empty tables.
- V35 Tech > System Health restored.
- V36 Advance Updation ↔ Employee Profile sync retained.

Use Tech > System Health before client demo.


# V38 Payroll Month Rule + Leave Calculation Fix

Implemented:
- Payroll generation now blocked until selected month is complete.
- Employee Profile recalculation also blocked until month is complete.
- Payroll page now shows leaves detected for selected month before calculation.
- Leave type is normalized inside payroll calculation, not only during upload.
- Rejected/cancelled leave rows are ignored.
- This fixes cases where uploaded leave rows were visible but not counted due to text mismatch.
- Payroll report and approval report now use sticky/frozen Name column.
- Audit spreadsheet view remains inside expander.

Rule:
- Do not calculate/approve payroll before the 1st after month-end.


# V39 Lock After 1st Recalculation Rule

Changed payroll rule:
- Payroll calculation is allowed anytime as preview.
- Payroll cannot be approved/locked until the 1st after the payroll month ends.
- Payroll must be recalculated on or after that 1st date before approval/lock.
- Employee Profile recalculation is allowed anytime until payroll is locked.
- This prevents early lock while still allowing preview payroll before month-end.


# V40 Asha Payroll Fix

Issue found:
- Payroll calculation was not saving all report-critical fields into payroll_items.
- Fields like Holiday_Exclusions, Leaves_After_Allowed_And_Exclusions, Advance_Prior_Month,
  Advance_Given_This_Month, Advance_Balance_Open and Advance_Balance_Close were missing from saved rows.
- This caused Payroll_Final / Salary Summary to look wrong for employees such as Asha.

Fix:
- Saved payroll row now includes all critical fields.
- Mobile Summary now prefers calculated payroll row values where available.
- For Asha starter data:
  - Monthly Salary: ₹10,000
  - L1 paid leaves: 2
  - No leaves: 2 unused leaves encashed
  - April advance deduction: ₹500
  - Expected net = ₹10,000 + ₹666.67 encashment - ₹500 = ₹10,166.67


# V41 Bulk Leave Match Fix

Issue fixed:
- Bulk uploaded leaves could appear in leave_entries but still not count in payroll if Emp_ID/name formatting differed.
- Payroll now normalizes employee IDs and names before matching leaves.
- Example accepted mappings:
  - E_Asha
  - Asha
  - e asha / E-Asha / E_Asha with spaces/case differences
- Payroll calculation now normalizes leave types again before counting.
- Rejected/cancelled leaves remain ignored.
- Added Payroll > Leave matching diagnostics.
- Added Employee Profile > Leave matching check for selected employee.

This specifically addresses cases where Asha has 15+ uploaded leaves but payroll was still treating her as no-leave.


# V42 Leave Logic Verified

Fixed:
- Payroll leave calculation now defensively counts uploaded bulk leaves.
- Leave type variations with invisible spaces/dashes/case differences are handled.
- If leave rows match but count as zero units, a diagnostic row is created.
- Payroll diagnostics now show Uploaded Leave Rows, Counted Leave Units, Allowed Leaves, Expected LOP, Expected Leave Deduction.

Uploaded file validation:
- Total rows: 62
- Asha leave units: 15.0
- Asha allowed L1 leaves: 2
- Asha expected LOP: 13.0
- Asha expected leave deduction: ₹4333.33
- Asha April advance deduction: ₹500.0
- Asha expected net salary: ₹5166.67


# V44 Demo Ready Fix

Fixes both urgent demo blockers:
1. Bulk upload persistence:
   - Default mode is now "Replace entire leave data for uploaded month".
   - App immediately re-reads leave_entries.csv after save.
   - It verifies saved row count against uploaded valid row count.
   - If 62 rows are uploaded but fewer are saved, the app shows an error immediately.
   - Saved summary remains visible; no hidden rerun.

2. Mobile report spacing:
   - Report tables have compact row height.
   - Table container max-height reduced.
   - Spreadsheet/audit views are shorter.
   - Sticky Name column retained.


# V45 Bulk Upload No-Collapse Fix

Fixed the V44 issue:
- Replace entire uploaded month no longer collapses rows by Date + Emp_ID.
- Every uploaded row is saved exactly.
- This fixes cases like expected 63 rows but only 37 saved.
- Append mode now uses full-row matching instead of only Date + Emp_ID.
- Duplicate Date + Emp_ID rows are warned but not removed in replace-month mode.


# V46 Strict Bulk Month Replacement

Fixed:
- V45 could append new upload rows but fail to remove existing month rows, causing expected 63 but found 100.
- V46 removes existing rows using a strict parsed month label check.
- Replace entire leave data for uploaded month now means:
  1. remove all saved rows for uploaded month(s)
  2. append every uploaded valid row
  3. verify saved row count equals uploaded valid row count

Demo instruction:
- Tech > Bulk Leave Upload
- Select Replace entire leave data for uploaded month
- Upload file
- Confirm Bulk Upload
- Saved rows should equal valid rows.


# V47 Full QA Consolidated

QA focus:
- Role flow
- User manager
- Bulk upload strict month replace
- Leave matching diagnostics
- No-leave safety
- No-advance/no-schedule safety
- System Health
- Advance/Profile sync
- Payroll lock rule
- Sticky reports
- Mobile spacing
- Salary Summary

Patch added:
- Explicit no-advance safe messaging.
- Explicit no-advance-schedule safe messaging.
- Defensive no-schedule guard in payroll calculation.


# V47 Full QA Consolidated

Full QA pass completed:
- Role flow checked.
- User/member manager checked.
- Bulk upload strict replace checked.
- Leave upload save verification checked.
- Leave matching diagnostics checked.
- No-leave safety checked.
- No-advance and no-schedule safety checked.
- System Health checked.
- Advance/Profile sync checked.
- Payroll approval rule checked.
- Mobile report spacing checked.
- Sticky Name reports checked.
- Salary Summary checked.
- Compile check passed.

Use Tech > System Health before demo.


# V48 Bulk Upload Physical Row Verification

Fixed:
- Previous verification used grouped employee summary row totals, which could report 26 even when physical saved rows were higher.
- V48 verifies using actual physical saved rows for the uploaded month.
- Employee summary remains visible, but it is not used as the row-count source.
- Removed misleading V46 retry message.


# V49 Date Parsing Fix

Issue:
- Leave entries showed 63 rows saved, but Payroll detected only 1 for Apr-2026.
- Root cause: inconsistent date parsing/month filtering across upload, payroll, diagnostics and reports.

Fix:
- Added robust app-wide date parser.
- Supports DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY and mixed date text.
- Payroll, diagnostics, bulk upload verification and leave cleanup now use the same parser.
- Payroll page warns if leave file has rows but selected month detects none.


# V50 ISO Date Priority Fix

Fixed:
- Saved dates are stored as ISO YYYY-MM-DD.
- The previous parser could treat 2026-04-11 as 2026-11-04 because day-first parsing ran too early.
- Parser now detects YYYY-MM-DD first before trying day-first upload formats.
- Leave diagnostics now includes a TOTAL row.
- Payroll diagnostics displays total uploaded rows and counted leave units.

This addresses the case where leave_entries had many April rows saved but diagnostics showed only a subset.


# V51 Advance Summary Fix

Fixed Salary Summary advance split:
- Advance Prior Month now reflects current-month deduction lines for advance IDs created before the selected month.
- Advance Current Month now reflects current-month deduction lines for advance IDs created in the selected month.
- Total Advance = Advance Prior Month + Advance Current Month.
- This addresses the Pooja case where 2k prior month + 2k current month should show total advance as 4k, not 2k.


# V52 Header Visibility Fix

Fixed:
- Page header/title was clipped at the top on mobile/laptop.
- Increased top padding for the Streamlit page container.
- Added safer title/subtitle spacing and line-height.
- Keeps existing mobile report spacing and sticky Name column logic.


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


# V55 Special Impact Profile Only

Implemented product-flow correction:
- Payroll page is now Step 1 only: regular overall payroll calculation.
- Removed Special Impact Tools from Payroll page to avoid confusion.
- Employee Profile is Step 2: person-wise recalculation and special impact handling.
- Special Impact Tools remain only in Employee Profile.
- Employee Profile recalculation continues to feed into Payroll, Salary Summary, Final Excel and connected reports.
- Payroll report now clarifies that it reflects regular payroll plus individual profile recalculations.

Reason:
- Avoids accidental global application of special impact rules when user intended employee-specific recalculation.


# V56 Safe Helper Fix

Fixed:
- Payroll page / Final Excel download error caused by missing `safe_numeric_series()`.
- Added missing helper before salary summary calculation.
- Made Amount_Given access safe in salary summary.
- Special Impact Tools remain only on Employee Profile.


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


# V58 Before/After Special Impact Lifecycle

Added full lifecycle visibility for special impact:
- Regular_Leave_Units_Before_Special is calculated and saved.
- Special_Impact_Leave_Units is calculated and saved.
- Special_Impact_Leave_Difference is calculated and saved.
- Leave adjustment log records regular units and special difference per leave row.
- Employee Profile shows before/after note after recalculation:
  Regular Payroll Leave Units, Special Impact Leave Units, Difference Applied.
- Reports/approval view include the fields.

Example:
- Kiran regular: 4 regular + 5 collaborative = 9 units.
- If collaborative special impact is activated at 1.5, special units = 11.5.
- Difference applied = 2.5.


# V59 V58 + Collaborative Dependent Fix

Base preserved:
- Built from V58 `before_after_special_impact`.
- V58 before/after special impact messaging is retained.

Fix added:
- Collaborative impact method and value are now true dependent controls.
- Amount per collaborative leave treats value as rupees, not leave days.
- Day mode alone changes leave units and is capped to prevent accidental 50-day impact.
- Special Impact Tools remain only on Employee Profile.


# V60 Faizan Profile/Summary Fix

Fixed:
- Faizan could appear after full payroll generation but disappear after Employee Profile recalculation.
- Added payroll month reconciliation guard:
  - Every payroll month must contain one row for every active employee.
  - If Employee Profile recalculation accidentally leaves an active employee missing, the missing row is restored automatically.
  - Salary Summary also reconciles before display.
  - Payroll report also reconciles before display.
- Active employee filtering is now more robust against blank/case/space issues in Status.

This protects Faizan and any future active employee from disappearing from Payroll/Summary after individual recalculation.


# V61 UX Fixes on Stable Baseline

Applied on uploaded stable baseline:
1. Unified Advance Editor
   - Refund Start Month is now calendar-style date_input.
   - User can pick any date in the start month; app stores Apr-2026 format.
   - Applied to Edit Advance Controls and matching Create New Advance input pattern.

2. Employee Profile / Special Impact Tools
   - Added clearer Special Impact heading.
   - Added "Final Recalculation Inputs" heading inside the form.
   - Clarified that Extra Paid Leaves, Advance Deduction and Recalculate button are part of the same employee-level recalculation.

3. Dark theme button safety
   - Forced button text to white across normal/dark phone themes.
   - Specifically protects login/action/download buttons from invisible text.


# V62 Leave Save + Phone Dark Theme Fix

Fixed:
1. Leave page crash
   - Manual leave saving no longer uses positional list assignment.
   - It now writes by column names and includes Status='Approved'.
   - Prevents pandas error: cannot set a row with mismatched columns.

2. Dark theme button visibility
   - Removed over-aggressive global white button text rule.
   - Button dark-theme fix is now scoped to phone-width dark theme only.
   - Laptop/light-theme button behavior is not forcibly changed.


# V63 Stable Build with Updated Data

Base:
- V62 leave-save + phone dark-theme fix.

Updated data files merged:
- users.csv
- employees.csv
- advance_cases.csv
- advance_schedule.csv
- leave_entries.csv from checked_clean_bulk_leave_upload (1).csv

Notes:
- Uploaded checked clean bulk leave file has been placed as data/leave_entries.csv.
- Payroll rows are intentionally not pre-generated; generate payroll inside the app after deployment/testing.


# V69 Seed Confirmation Fix

Fixed:
- Clicking Tech → Database Health → Seed Supabase from CSV now shows a persistent success/error message.
- Removed immediate rerun after seed/export so confirmation does not disappear.
- Added visible current Supabase row-count summary for key tables.


# V70 Balloon Confirmations

Updated confirmation behavior:
- Major success / completion messages now use balloon-style indication consistently.
- `set_confirmation()` now defaults to balloon celebration.
- Balloon flag is reset cleanly after rendering.
- Database Health seed/export confirmations also use balloon-style feedback.
- Persistent DB health success message shows balloons; failures do not.


# V71 Seed Action Result Panel

Fixed:
- Seed Supabase from CSV now shows an unmistakable result panel after click.
- Result panel includes action name, status, timestamp, message, row counts before and after.
- Uses explicit button keys.
- Uses rerun only after saving the result into session state so the result remains visible.


# V72 Supabase Reset + Seed Fix

Problem fixed:
- Seed failed on `sms_users_pkey`, caused by old Supabase schema/index from earlier attempts.

Added:
- `SUPABASE_RESET_SMS_TABLES_RUN_IF_SEED_FAILS.sql`
- Tech → Database Health → Reset SMS Tables button
- Longer local statement timeout during seed/reset
- Seed uses batch insert method.

Recommended setup:
1. If seed fails, click Reset SMS Tables once.
2. Then click Seed Supabase from CSV.
3. Verify row counts.
