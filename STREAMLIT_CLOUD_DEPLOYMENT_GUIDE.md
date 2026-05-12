# Streamlit Cloud + GitHub Deployment Guide

## Fixed repository structure

This ZIP is packaged flat for Streamlit Cloud.

At GitHub repository root, you must see:
- `app.py`
- `requirements.txt`
- `runtime.txt`
- `.gitignore`
- `.streamlit/config.toml`
- `data/`

Do not upload the parent folder. Upload the contents of this ZIP directly.

## Deploy steps

1. Create a new private GitHub repository.
2. Upload all extracted files directly into the repository root.
3. Confirm `app.py` is visible on the first page of the repository.
4. Go to Streamlit Cloud.
5. Click New app.
6. Select the repository.
7. Main file path: `app.py`.
8. Click Deploy.

## Default login

- Email: `admin@sms.local`
- Password: `admin123`

After login choose:
- Admin Access
- Supervisor Access
