# V67 V63 UI + Supabase Parity

Base: V63 stable with updated data.

This is not a debug/test app. It preserves the full Salary Management System UI and adds:
- Supabase PostgreSQL behind existing read_table/write_table functions
- CSV fallback
- Tech → Database Health
- Row-count validation
- Schema alignment
- Seed Supabase from CSV
- Export Supabase to CSV
