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
