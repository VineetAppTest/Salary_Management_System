# Supabase PostgreSQL Setup Guide

This build supports persistent Supabase PostgreSQL storage.

## Streamlit secrets

Add this in Streamlit Cloud → App → Settings → Secrets:

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
```

Use the Supabase Transaction Pooler / IPv4-compatible PostgreSQL connection string.

## Behavior

- If DATABASE_URL is present, the app creates `sms_*` PostgreSQL tables and reads/writes there.
- If DATABASE_URL is missing, the app uses local CSV fallback.
- Existing CSV files inside `/data` are used to seed empty database tables.
