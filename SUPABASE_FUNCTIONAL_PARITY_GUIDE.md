# V66 Supabase Functional Parity Guide

## Goal
Everything that worked in V63 should work exactly the same, but data should persist in Supabase.

## Setup
Add this in Streamlit Cloud → App → Settings → Secrets:

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
```

Use Supabase Transaction Pooler / IPv4-compatible URL.

## Validation
Open the app → Tech → Database Health.

Target row counts:
- employees: 7
- leave_entries: 62
- advance_cases: 6
- advance_schedule: 6
- users: 1

If DB rows are empty, click:
**Seed Supabase from CSV**

Then:
1. Generate Payroll
2. Check Salary Summary
3. Reopen/restart app
4. Confirm data remains
