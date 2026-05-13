
# WageWise V115 Section-First Redirect Layout

- Fixed WageWise header visibility and navigation text overlap.
- Disabled unreliable auto-scroll and moved to section-first rerun navigation.
- Restored centered Section update card between navigation and content.
- Renamed the actual user management page to Access Manager to avoid Users & Access / User & Access Manager redundancy.
- Added clearer primary, secondary and subheader hierarchy.
- Scope is UI/navigation only; payroll, database, leave and advance logic are unchanged.

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


# V73 Database Health UX + Speed Fix

Addressed observations:
1. Reduced repeated schema checks to improve Supabase speed.
2. Redesigned Database Health into a cleaner setup/admin layout.
3. Moved Reset SMS Tables into a Danger Zone with confirmation checkbox.
4. Balloon celebration now triggers once per action result, not repeatedly.
5. Removed duplicate success/confirmation paths from DB Health actions.

Note:
- Supabase will still be slower than CSV because reads/writes go over the internet.
- Seed is expected to take time because it clears and inserts multiple tables.


# V74 Performance + Bulk Upload Fix

Fixed:
1. Page speed:
   - Added per-session table cache for Supabase reads.
   - Write operations update/invalidate cache.
   - Reduces repeated DB calls across a single page run.

2. Bulk upload button visibility:
   - Removed per-row DB lock check; payroll lock data is read once.
   - Upload mode moved above validation.
   - Final button renamed to "Confirm Bulk Upload Now" and appears right after validation summary.
   - Large preview moved into collapsed expander.

3. UX:
   - Reduced duplicate celebration/toast paths on bulk upload.


# V75 Speed + Simplified UX Recovery

Deal-breaker fixes:
1. Startup no longer checks Supabase schema on every page load.
2. Supabase read/write now uses fast path and session table cache.
3. Login and role selection no longer wait for audit DB writes.
4. Audit logging no longer blocks core UI actions.
5. Database Health is simplified and heavy details are hidden in expanders.
6. DB errors are no longer shown as long technical/code-like messages across normal pages.

Important:
- Supabase will always be slower than pure CSV because it uses internet/database calls.
- This build prioritizes user adoption speed over excessive diagnostics on every page.


# V76 Client Confidence Pack

Built on V75 performance recovery.

Added:
1. Payroll Control Centre
   - Guided monthly flow with Employees, Leaves, Advances, Payroll and Approval readiness.

2. Month Readiness Check
   - Active employees, leave rows, advance schedules, payroll rows and lock status.

3. Salary Calculation Explanation
   - Expandable employee-wise explanation in Salary Summary.

4. Mobile Salary Cards retained/enhanced through the existing app-style Salary Summary.

5. Bulk Upload Backup + Undo
   - Creates backup before bulk leave upload.
   - Adds Undo Last Bulk Upload action after upload.

Goal:
- Speed + clarity + confidence + recovery without adding new payroll rules.


# V77 Demo Mode + User Manual Pack

Added:
1. Demo Mode toggle
   - Available on Dashboard, Payroll Control Centre and Tech.
   - Demo Mode ON hides technical database clutter and shows client-friendly guidance.
   - Demo Mode OFF shows full operational and database details.

2. Demo Mode Guide under Tech
   - Explains when to use ON/OFF.
   - Provides quick toggle buttons.

3. User Manual
   - `SMS_USER_MANUAL.md` included in package.
   - Separate DOCX manual created for review:
     `SMS_User_Manual_Supervisor_Admin_Tech.docx`

Focus:
- Better client demonstration
- Clear role-wise user education
- Reduced confusion for Supervisor/Admin/Tech users


# V78 User Role Access Control

Added:
- User-level role-card access controls:
  - Allow Admin card
  - Allow Supervisor card
  - Allow Tech card
- Admin/Tech user manager can switch Admin access OFF for another login without deleting the login.
- Role Selection page now only shows role cards enabled for that login.
- Backward compatible: existing users default to all role cards ON.

Use case:
- Keep a user active but remove Admin access by switching "Allow Admin card" OFF.


# V79 WageWise Branding Pack

User-facing branding updated:
- App name changed from Salary Management System to WageWise.
- Subtitle changed to: Leave, advances and payroll in one guided flow.
- Tech role is displayed as System Admin where safe.
- User manager renamed to Users & Access.
- User manual updated to WageWise branding.

Internal logic/table names remain unchanged to avoid breaking the app.


# V80 Two-Role Access Fix

Corrected role model:
- Only two user-facing roles now exist: Admin and Supervisor.
- Removed the third System Admin/Tech role card from login role selection.
- Admin now includes all setup/system-admin utilities in Admin navigation:
  - System Admin
  - Bulk Leave Upload
  - System Health
  - Users & Access
  - Database Health
- Supervisor remains limited to supervisor actions.
- User access control now has only:
  - Allow Admin card
  - Allow Supervisor card

Backward compatibility:
- Older users with Tech/System Admin access are mapped safely to Admin where required.
- Internal function names remain unchanged where needed to avoid breaking logic.


# WageWise V81 Navigation + Login Cleanup

Updated:
1. Navigation buttons grouped by workflow:
   - Overview
   - Monthly Inputs
   - Payroll Run
   - Admin Setup

2. Email domain changed from sms.local to wagewise.local.

3. Default local fallback logins:
   - admin@wagewise.local / admin123
   - supervisor@wagewise.local / supervisor123

4. Payroll Control Centre clarified:
   - Control Centre = guided status/checklist page.
   - Payroll = calculation/recalculation page.
   - Payroll Approval = final approval/lock page.
   - Recommended flow: Control Centre → Payroll → Salary Summary → Payroll Approval.

Important Supabase note:
If Supabase already has old users, the app will use Supabase users instead of CSV fallback users. Update sms_users in Supabase or reset/seed users if required.


# WageWise V82 Client-Ready Polish Freeze

No salary calculation rule changes.

Focus:
- Confidence: Monthly Close Checklist, Last Updated indicators, Next Step guidance.
- Usability: clearer navigation groups and vertical stacked navigation buttons.
- Recovery: manual payroll snapshot backup on Payroll Approval.
- Look and feel: refined blue/teal schema, softer cards, better primary button styling.
- Speed/clarity: no new heavy business logic; technical storage wording softened for users.

Final recommended flow:
Control Centre → Payroll Calculation → Salary Summary → Payroll Approval.


# WageWise V83 Responsive UI Final Polish

No salary logic changes.

What changed:
- Desktop navigation redesigned into a balanced 2-column layout:
  - Left side: Overview, Monthly Inputs, Payroll Processing
  - Right side: Setup & Controls (larger panel)
- Mobile experience refined:
  - Same sections automatically stack into a single-column phone-friendly flow
  - Full-width touch-friendly buttons
  - Cleaner spacing and reduced clutter
- Visual polish:
  - Refined WageWise blue/teal scheme
  - Softer cards and helper panel
  - Better top navigation card
- Existing flow retained:
  Payroll Control Centre → Payroll Calculation → Salary Summary → Payroll Approval


# WageWise V85 Micro Polish Pass

Polish only. No payroll logic changes.

Updated:
- Improved spacing between navigation groups
- Better visual balance between left and right desktop navigation panels
- More consistent button alignment and sizing
- Cleaner bordered group containers
- Slightly tighter layout and smoother visual hierarchy


# WageWise V88 Safe Auth - No URL Session

Important correction:
- V87 URL-based session persistence should NOT be used.
- V88 intentionally removes/avoids URL session tokens because copied URLs can create access risk.

What V88 keeps:
- V85 final UI polish and navigation micro-polish.
- V86 user access recovery safeguards.
- Create/Edit/Delete user verification.
- Emergency Supabase recovery SQL.

Security stance:
- Browser refresh may require login again.
- This is safer than keeping login state in a shareable URL.
- For true production-grade refresh persistence, use a proper auth provider such as Streamlit OIDC/Auth0/Supabase Auth in a later controlled phase.

No salary calculation logic changes.


# WageWise V89 Supervisor Employee Visibility Fix

Fix:
- Supervisor login no longer shows a broken "no active employee" state because of old Supervisor_Email mapping.
- Supports both supervisor@wagewise.local and legacy supervisor@sms.local mapping.
- If no employees are specifically mapped to the logged-in supervisor, Supervisor view temporarily shows all active employees with a friendly note.
- Admin can later assign Supervisor_Email in Employees for strict supervisor-wise visibility.

No salary calculation logic changes.


# WageWise V90 Supervisor Direct Login Fix

Fix:
- Supervisor users no longer land on the role selection page when they have only Supervisor access.
- Any user with exactly one allowed role is taken directly to that role dashboard.
- Admin users with both Admin and Supervisor access will still see the role choice page.
- No salary calculation logic changes.


# WageWise V91 Users & Access Storage Fix

Fixes:
- User save verification failure after creating/editing logins.
- Repairs missing `allow_admin` and `allow_supervisor` columns in Cloud Storage before user save.
- User write verification now bypasses stale cache and checks active storage directly.
- Adds a repair button: Users & Access → Repair Users Storage Columns.
- Includes SQL repair file: `REPAIR_WAGEWISE_USERS_COLUMNS.sql`.

No salary calculation logic changes.


# WageWise V92 Users Direct Save + Supervisor UI Fix

Fixes:
1. Supervisor UI
   - Switch Role button is hidden for Supervisor users.

2. Users & Access save verification
   - User save no longer uses the generic table writer.
   - When Cloud Storage is enabled, the app directly writes `sms_users`.
   - Verification reads the active `sms_users` table directly.
   - Avoids the empty-table verification issue caused by schema drift/fallback mismatch.

No salary calculation logic changes.


# WageWise V93 Switch Role Visibility Fix

Fix:
- Supervisor-only login does not show Switch Role.
- Admin login with both Admin and Supervisor access will show Switch Role even when currently operating in Supervisor role.
- Visibility is now based on number of allowed roles for the login, not the currently selected role.

No salary calculation logic changes.


# WageWise V94 Action Focus & Guidance Fix

UX-only fix. No salary calculation logic changes.

Added:
- Button clicks now set a clear focus/guidance message.
- Destination page shows a highlighted action-focus panel.
- Supervisor quick actions now clearly show the active section after Mark Leave/Add Advance.
- Save actions give next-step guidance after completion.
- Payroll Control Centre navigation buttons now redirect attention with guidance.

Purpose:
- Users should always know that the click worked and what to do next.


# WageWise V95 Login Polish + Auth Direction

UI:
- Removed security/browser-refresh instruction line from login page.
- Removed desktop/mobile layout explanation line from navigation.
- Login page made more attractive with WageWise hero, product line and cleaner login card.

Authentication recommendation:
- Current V95 remains on safe custom login.
- Do not use URL session tokens.
- Recommended production path: Streamlit OIDC.
- Keep WageWise users table only for role access control after OIDC identity is verified.

No salary calculation logic changes.


# WageWise V96 OIDC Ready Build

Added:
- Streamlit OIDC login path when `[auth]` secrets are configured.
- Fallback WageWise login remains available for UAT/testing.
- OIDC verified email maps to Users & Access table for Admin/Supervisor permissions.
- Added Authlib dependency.
- Added `.streamlit/secrets.example.toml` OIDC template.
- Added V96 OIDC setup notes.

No salary calculation logic changes.


# WageWise V97 Total Advance Summary Fix

Fix:
- Salary Summary `Total Advance` now shows total advance amount taken by the employee up to payroll recalculation date.
- `Deduction for the Month` remains based only on the selected salary month’s advance repayment schedule.
- `Advance Left` is calculated as Total Advance minus deductions scheduled up to the selected salary month.
- Advance page wording updated to clarify this difference.

Important:
- This changes reporting/advance summary correctness.
- It does not change salary calculation rules except keeping monthly deduction tied to the schedule.


# WageWise V98 Advance Calculation Guardrails

Reviewed scenarios:
1. No advance: Total Advance = 0, Deduction for Month = 0, Advance Left = 0.
2. Current-month advance with current-month deduction: Total Advance includes amount taken; deduction follows schedule.
3. Prior-month advance with current-month scheduled deduction: Total Advance remains full amount taken; current month deducts schedule only.
4. Future advance entered after payroll recalculation: excluded from older payroll summary.
5. Duplicate/dirty schedule exceeding advance amount: deduction and balance are capped to avoid negative/illogical values.
6. Missing schedule: salary summary falls back to payroll row values.
7. Employee Profile monthly advance override: deduction is capped to remaining balance.

No leave/salary rules changed; only advance deduction/balance guardrails were tightened.


# WageWise V99 Phone + Admin Corrections

Built on V98. Includes all V98 advance guardrails.

Changes:
1. Phone UI polish
   - tighter mobile spacing
   - cleaner stacked navigation/cards
   - smaller mobile salary table text and better scrolling

2. Admin leave corrections
   - Admin can edit leave row
   - Admin can delete leave row
   - Mandatory admin correction remark for edit/delete
   - Audit log recorded

3. Admin advance corrections
   - Admin can edit advance case
   - Admin can delete advance case
   - Schedule rebuilt when advance is edited
   - Mandatory admin correction remark for edit/delete
   - Audit log recorded

4. Ria/Riya correction in packaged data
   - ₹700 advance moved to May-2026 salary deduction
   - additional ₹50 advance added for May-2026 deduction
   - April salary should not deduct these two May advances

5. Browser logout
   - Refresh-safe login still requires OIDC setup in Streamlit secrets.
   - The build retains OIDC-ready capability from V96.

No change to leave/payroll rules.


# WageWise V100 Advance Safe Edit + Recovery Guard

Critical fix after V99 advance edit issue:
- Main advance correction is now edit-only, not edit/delete in the same form.
- Physical delete removed from normal correction flow.
- Cancel is moved to a separate Danger Zone and marks advance/schedule as Cancelled instead of deleting rows.
- Before every admin advance edit/cancel, the app creates backups of:
  - advance_cases
  - advance_schedule
- Edit updates only the selected Advance_ID.
- Schedule rebuild removes/recreates only the selected Advance_ID schedule rows.
- Mandatory admin correction remark remains.
- V98/V99 advance calculation guardrails remain intact.

If data was deleted in Supabase before V100:
- Check Streamlit app backups if available.
- Check Supabase backups/logs if available.
- Do not seed CSV unless you intentionally want to overwrite live data.


# WageWise V101 Leave Safe Edit + Recovery Guard

Built on V100.

Critical safety fix:
- Leave correction now follows enterprise-safe pattern.
- Physical delete is removed from the Admin leave correction flow.
- Admin can edit selected leave row safely.
- Admin can cancel selected leave row safely by setting Status = Cancelled.
- Cancelled leave rows remain in the table for audit and are ignored by payroll.
- Backup of leave_entries is created before every admin edit/cancel.
- Mandatory admin correction remark remains.
- Audit log captures the correction and backup path.

Retained from V100:
- Advance safe edit/recovery guard.
- Advance cancellation instead of physical delete.
- V98 advance calculation guardrails.
- V96 OIDC-ready capability.

No salary/leave calculation rule changes.


# WageWise V102 Leave Correction Full List Selector

Built on V101.

Fix:
- Admin correction selector now shows total saved leave rows and filtered row count.
- Added filters for month, employee and status.
- Added a correction preview table before row selection.
- The row selector uses the full filtered leave dataset, not an unclear small dropdown.
- Safe edit/cancel with backup from V101 is retained.
- No payroll/leave rule changes.


# WageWise V103 OIDC User Access Creation Fix

Fix:
- Users & Access can now create Google/OIDC access records without requiring a real password.
- Password fields are now optional fallback-password fields.
- If password is left blank, the user can still login through Google/OIDC if their email matches.
- The app now clearly warns: never enter Gmail password in WageWise.
- Fallback/UAT password login still works only if a fallback password is explicitly set.

Why:
- Google verifies the Gmail password.
- WageWise should only store email + Admin/Supervisor access permissions.

No salary/payroll/leave/advance logic changes.


# WageWise V104 OIDC Minimal Pattern Fix

Built after minimal Google OIDC test succeeded.

Fix:
- Full WageWise OIDC login now follows the same working minimal pattern.
- Uses `st.button(..., on_click=st.login)` instead of calling `st.login()` inside an if block.
- Removed the OIDC refresh button to avoid duplicate session/rerun state issues.
- Uses safe `st.user.to_dict()` style access.
- Avoids duplicate OIDC handling in login_screen and main.
- Keeps fallback/UAT login.
- OIDC users still map to Users & Access by exact Gmail ID.

No payroll/leave/advance calculation changes.


# WageWise V105 Login Experience Polish

Built on V104 OIDC minimal pattern fix.

Changes:
- Login screen made fuller and more polished for desktop.
- Removed equal Organisation/Fallback tabs.
- Primary login is now a single clear button: Continue with Google.
- Fallback/UAT login is hidden under a small expander: Fallback / support login.
- Keeps the working minimal OIDC pattern from V104.
- No payroll/leave/advance calculation changes.

Note:
- Automatic fallback after a failed external Google login is not reliable/safe because the user leaves the app for Google OAuth.
- The safe UX is: Google is primary, fallback is available only under support expander.


# WageWise V106 Mobile Login Compact Fix

Built on V105.

Fix:
- Desktop login remains fuller.
- Phone login is now compact and less cluttered.
- Google login button appears much higher on phone.
- Feature chips and 3-step trust cards are hidden on phone only.
- Login hero/card spacing reduced on phone.
- Fallback/support login remains hidden under expander.
- No payroll/leave/advance calculation changes.


# WageWise V107 Go-Live Stability + Recovery Build

Built on V106.

Fixes and improvements:
1. Login
   - Removed 3-step cards from desktop and mobile.
   - Login screen loads faster by not running data/table setup before showing login.

2. Navigation and UX
   - Active navigation button uses visible primary styling.
   - Adds inline section guidance after navigation instead of relying only on top-right toast.
   - Navigation spacing tightened for better balance.

3. Form completion behaviour
   - Users & Access create/update keeps user on Users & Access and shows a clear inline note.
   - More form-specific reset work can be added after testing exact pages, but this build prevents the known Users & Access -> Advance Master confusion.

4. Advance data-loss protection
   - Critical tables are backed up before guarded writes.
   - Unsafe empty writes are blocked if the table already had data.
   - This specifically protects advance_cases and advance_schedule from accidental full wipe.

5. Recovery
   - Added Section Rollback panel:
     Setup & Controls → Recovery
   - Restore only one selected section from backup without resetting the entire app.

6. Technical checks
   - Technical checks are now separated under a dedicated tab.

Team Go-Live recommendation:
- Keep physical delete disabled for payroll-critical data.
- Use Cancel/Inactive statuses with audit.
- Keep OIDC as primary login.
- Test Recovery rollback once before client Go-Live.
- Export Supabase tables before the first client live payroll run.

No payroll/leave/advance calculation rule changes.


# WageWise V108 Auto Jump to Selected Section

Built on V107.

Fix:
- Navigation clicks now set an auto-jump flag.
- After Streamlit reruns, the app places a selected-section anchor before page content.
- A small browser script attempts to smooth-scroll to the selected content area.
- Users & Access create/update also keeps context and attempts to jump back to the selected section.
- Existing V107 recovery, guarded writes and go-live stability fixes are retained.

Important:
- Streamlit does not provide a native guaranteed scroll API.
- This is a best-effort browser auto-jump and should work in common desktop/mobile browsers.
- If a browser blocks the script, the inline “You are now in…” guidance remains as fallback.

No payroll/leave/advance calculation changes.


# WageWise V109 Go-Live Navigation & Safety Correction

Built on V108, retaining V107 recovery/stability.

Corrections:
1. Removed top-right toast notification for action focus.
2. Converted Setup areas from fragile tabs into true pages:
   - Users & Access
   - Advance Master
   - Recovery
   - Technical Checks
   - Demo Mode Guide
3. Rebalanced navigation:
   - Workflows
   - Payroll & Reports
   - Setup & Recovery
   - Technical
4. Active navigation button contrast improved.
5. Removed reliance on auto-scroll as the primary fix; selected section is now routed as actual page content.
6. Users & Access create/update/repair keeps user in Users & Access.
7. Critical table write safety strengthened:
   - unsafe empty write guard retained
   - pre-write backup retained
   - post-write row-count verification added

Retained:
- V108/V107 rollback and guarded write foundations
- V106 mobile login compact fix
- V105 login polish
- V104 working OIDC minimal pattern
- V103 OIDC user creation without Gmail password
- V102 leave correction full list selector
- V101 leave safe edit/cancel
- V100 advance safe edit/recovery guard

No payroll, leave, or advance calculation rule changes.


# WageWise V110 Go-Live Compact Navigation + True Routing

Revised build after V109 review.

Major correction:
- Navigation is now compact selector-first.
- Selected section content appears immediately below the selector.
- Full grouped navigation is optional and collapsed under "Open full navigation".
- This avoids the manual-scroll problem instead of relying on fragile auto-scroll scripts.

Retained:
- True page routing for Users & Access / Advance Master / Recovery / Technical Checks.
- No top-right toast.
- Data safety and Section Rollback.
- OIDC minimal working pattern.
- Safe edit/cancel flows for advances and leaves.

No payroll, leave, or advance calculation rule changes.


# WageWise V111 Button Grid Navigation Fix

Built after V110 feedback.

Correction:
- Removed dropdown navigation.
- Removed collapsed full-navigation dependency.
- Navigation is now a visible button grid:
  - Daily Work
  - Payroll Flow
  - Setup
  - Recovery & Technical
- The selected section opens immediately below navigation.
- Active button is clearly highlighted.
- Works better for desktop and phone than a dropdown.

Retained:
- True page routing for Users & Access / Advance Master / Recovery / Technical Checks.
- No top-right toast.
- Data safety and Section Rollback.
- OIDC minimal working login pattern.
- Safe edit/cancel flows.

No payroll, leave, or advance calculation rule changes.


# WageWise V112 Navigation Cleanup Verified

This build corrects the V111 issue where dropdown/full-navigation remnants could still exist.

Verified correction:
- No dropdown navigation in page_navigation.
- No `compact_section_selector`.
- No `Go to section` selectbox.
- No `Open full navigation` expander.
- Navigation is a visible button grid only.
- Selected section opens directly below the button-grid navigation.

Retained:
- True page routing for Users & Access / Advance Master / Recovery / Technical Checks.
- No top-right toast.
- Data safety and Section Rollback.
- OIDC minimal working login pattern.
- Safe edit/cancel flows.

No payroll, leave, or advance calculation rule changes.


# WageWise V113 Build Marker + Spacing + Auto-Scroll Repair

Built on V112.

Changes:
1. Added visible build marker:
   - Build V113 appears next to WageWise title.

2. Spacing fixes:
   - More top padding between page top and heading.
   - Better spacing between Navigation note and group sections.
   - Better spacing between group headings and buttons.

3. Auto-scroll repair:
   - Navigation button clicks set a pending scroll flag.
   - After rerun, app renders a stable content anchor and triggers a best-effort scroll to selected content.
   - Multiple timed attempts are used to improve reliability in Streamlit.

4. Guidance moved:
   - "You are now in..." and action-focus messages are moved to the bottom under "Section update".

Retained:
- Button-grid navigation.
- No dropdown navigation.
- No collapsed full-navigation dependency.
- No top-right toast.
- True page routing.
- Recovery and unsafe write protections.
- OIDC login pattern.

No payroll, leave, or advance calculation rule changes.


# WageWise V114 Auto-Scroll Anchor Hardening

Built on V113.

Fix:
- Hardcoded stable anchor:
  <div id="ww-selected-content-anchor"></div>
- Auto-scroll looks for the exact hardcoded anchor.
- Scroll trigger now runs after the selected content routing block starts.
- Scroll retries at 250ms, 750ms and 1300ms.
- Fallback scroll remains if browser cannot find the anchor.
- Build marker updated to Build V114.

Retained:
- V113 build marker/spacing improvements.
- Button-grid navigation.
- No dropdown navigation.
- No collapsed full-navigation dependency.
- Bottom guidance section.
- No top-right toast.
- True page routing.
- Recovery and unsafe-write protections.
- OIDC login pattern.

No payroll, leave, or advance calculation rule changes.
