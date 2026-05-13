# WageWise v116.8 - GitHub Actions Node 24 Native Fix

This build updates the GitHub Actions workflow actions to their Node 24-compatible major versions.

## Updated workflows
- `.github/workflows/keep-wagewise-awake-playwright.yml`
- `.github/workflows/daily_leave_email.yml`

## Changes
- `actions/checkout@v4` -> `actions/checkout@v5`
- `actions/setup-python@v5` -> `actions/setup-python@v6`
- Retains `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` as an additional compatibility flag.

## Scope
No payroll, leave, advance, holiday, employee, database, UI, or salary logic changed. This is only a GitHub Actions maintenance patch.
