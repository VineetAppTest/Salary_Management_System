# V68 Supabase No Runtime Schema

Why this build exists:
- Supabase timed out while app tried to CREATE TABLE during Streamlit startup.
- V68 removes runtime table creation.
- Run `SUPABASE_SCHEMA_RUN_ONCE.sql` once in Supabase SQL Editor.
- Then open app → Tech → Database Health → Seed Supabase from CSV.

This preserves the full V63 UI with Supabase behind read/write functions.
