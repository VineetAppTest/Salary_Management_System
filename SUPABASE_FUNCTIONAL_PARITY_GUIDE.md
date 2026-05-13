# Supabase Functional Parity Guide - V68

## Important V68 change
The app no longer creates tables during startup. This avoids Supabase timeout errors.

## Step 1: Run schema once
1. Open Supabase.
2. Open your project.
3. Go to SQL Editor.
4. Open `SUPABASE_SCHEMA_RUN_ONCE.sql` from this package.
5. Copy all SQL.
6. Paste in Supabase SQL Editor.
7. Click Run.

## Step 2: Add Streamlit secret
In Streamlit Cloud → App → Settings → Secrets:

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
```

Use Supabase pooler / IPv4-compatible URL.

## Step 3: Seed data
Open app → Tech → Database Health → click `Seed Supabase from CSV`.

Expected:
- employees: 7
- leave_entries: 62
- advance_cases: 6
- advance_schedule: 6
- users: 1

## Step 4: Test parity
1. Login.
2. Payroll → Generate Payroll.
3. Salary Summary → verify all employees.
4. Refresh/restart app.
5. Confirm data persists.
