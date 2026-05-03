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
