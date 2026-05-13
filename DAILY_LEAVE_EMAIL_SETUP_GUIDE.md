# Daily Leave Email Setup Guide — Layman Version

## What this does
Every day at 10:00 AM IST, GitHub will run a backend job that emails admins and supervisors a table of leaves marked since the previous 10 AM window.

The email includes:
- Date
- Name
- Type of Leave
- Remarks

It does not resend leave rows that were already reported earlier.

## Step 1 — Upload this build to GitHub
Upload the full V116.5 build to your WageWise GitHub repository.

## Step 2 — Add GitHub repository secrets
Open your GitHub repository, then go to:

Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

1. `DATABASE_URL`
   - Use the same Supabase/Postgres database URL used by Streamlit.

2. `SMTP_HOST`
   - For Gmail, use: `smtp.gmail.com`

3. `SMTP_PORT`
   - For Gmail, use: `587`

4. `SMTP_USER`
   - Your sending email address.

5. `SMTP_PASSWORD`
   - Your email app password, not your normal Gmail password.

6. Optional: `SMTP_FROM_EMAIL`
   - Same as SMTP_USER unless you have another sender email.

7. Optional: `EMAIL_RECIPIENTS`
   - Comma-separated list, for example:
     `admin@email.com,supervisor@email.com`
   - Use this if you want fixed recipients instead of reading recipients from WageWise Access Manager.

## Step 3 — Confirm workflow exists
In GitHub, open:

Actions → WageWise Daily Leave Email

You should see the workflow.

## Step 4 — Test once manually
Click:

Run workflow

This sends the daily leave email if new leave entries exist in the window.

## Step 5 — Daily automation
After setup, GitHub runs it automatically at 10:00 AM IST every day.

## Note
If no new leave entries exist for the window, the job will not send an empty email.
