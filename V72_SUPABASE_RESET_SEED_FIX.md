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
