# WageWise Keep-Awake Playwright Setup Guide

This utility keeps the Streamlit WageWise app warm by opening it from GitHub Actions on a schedule.

## Files added

- `.github/workflows/keep-wagewise-awake-playwright.yml`
- `scripts/keep_wagewise_awake_playwright.py`

## GitHub secret required

Add this repository secret:

```text
WAGEWISE_APP_URL
```

Value example:

```text
https://your-wagewise-app.streamlit.app
```

Use the full live Streamlit URL.

## How to add the secret

1. Open your GitHub repo.
2. Go to **Settings**.
3. Open **Secrets and variables**.
4. Click **Actions**.
5. Click **New repository secret**.
6. Name: `WAGEWISE_APP_URL`.
7. Secret value: your Streamlit WageWise app URL.
8. Click **Add secret**.

## How to test once manually

1. Open the repo in GitHub.
2. Click **Actions**.
3. Select **keep-wagewise-awake-playwright**.
4. Click **Run workflow**.
5. Choose the main branch.
6. Click **Run workflow**.

If successful, the run logs should show that the WageWise app opened and the page title was captured.

## Schedule

The workflow runs every 30 minutes using UTC GitHub Actions schedule.

## Important note

This workflow does not change payroll, leave, advance, holiday, or employee data. It only opens the app URL to keep the Streamlit instance warm.
