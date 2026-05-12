# WageWise Fresh Repository Deployment Checklist

## Files intentionally kept
- `app.py` — the only Streamlit main app file.
- `requirements.txt` — dependency file Streamlit must install.
- `data/` — local fallback seed data only. Supabase remains the live source when `DATABASE_URL` is present.
- `.streamlit/secrets.example.toml` — example only; do not commit real secrets.
- `.github/workflows/keep-wagewise-awake-playwright.yml` — optional keep-awake workflow.
- Essential SQL/README files.

## Files intentionally removed
- Old app files such as `WageWise_V78_2_app.py`.
- `__pycache__` and `.pyc` files.
- Old version note clutter.
- `runtime.txt` because Streamlit Community Cloud Python version should be selected in app settings.

## Streamlit deployment settings
1. New GitHub repo should have `app.py` at repo root.
2. Streamlit Cloud main file path: `app.py`.
3. Select Python version in Streamlit app settings: use Python 3.11 or 3.12.
4. Add secrets in Streamlit Cloud, not GitHub.
5. Reboot app after editing secrets/requirements.

## Authlib check
If OIDC still says Authlib missing, temporarily deploy:
`check_authlib.py`
as the Streamlit main file path. It will show whether Authlib is installed.
Then switch main file path back to `app.py`.
