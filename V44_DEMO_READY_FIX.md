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
