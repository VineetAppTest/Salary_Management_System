# WageWise V116.1 — Backend Actions Applied

This build applies the two requested backend corrections safely and idempotently.

## Completed actions

1. **Advance master creation from schedules**
   - The app now creates missing `advance_cases` records from existing `advance_schedule` rows for April 2026 onwards.
   - This is conservative: it only creates missing master rows and does not delete or overwrite existing advance data.
   - This protects against the earlier problem where schedule rows existed but the advance tab did not show matching advance records.

2. **E_Vivek holiday exclusions added**
   - Added employee-specific holiday exclusions for `E_Vivek` from **2026-05-01 to 2026-05-12**.
   - Remark used: `started on 13th May`.

## Supabase / Cloud Storage

If the deployed app is connected to Supabase, the app includes an idempotent startup correction that applies these backend actions after login.

A manual SQL version is also included:

`V116_1_BACKEND_ACTIONS_ADVANCES_HOLIDAYS.sql`

Use that SQL file only if you want to apply the backend correction directly from Supabase SQL Editor.

## Safety notes

- No payroll calculation logic was rewritten.
- No existing advances are deleted.
- No existing holiday records are deleted.
- Duplicate E_Vivek holiday rows are skipped.
- Existing advance master records are preserved.
