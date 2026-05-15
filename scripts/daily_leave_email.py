"""
WageWise daily leave email job.
Runs at 10:00 AM IST via GitHub Actions and emails admins/supervisors
with APPROVED leave entries reported from previous day 10:00 AM to current day 09:59:59 AM.

Business logic:
- Any leave for any leave date is included if it was ENTERED/REPORTED between previous day 10 AM and current day 10 AM.
- Only Status = Approved is included.
- Cancelled / Canceled / Rejected / Pending / blank statuses are excluded.

Required GitHub repository secrets:
- DATABASE_URL or SUPABASE_DB_URL
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD
Optional:
- SMTP_FROM_EMAIL
- EMAIL_RECIPIENTS  # comma-separated override list. If blank, active admins/supervisors from sms_users are used.
- APP_TIMEZONE      # default Asia/Kolkata
"""

import hashlib
import html
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import create_engine, text


APP_VERSION = "WageWise Daily Leave Email v2 - reported-window + approved-only"


def env(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default) or "").strip()


def get_engine():
    db_url = env("DATABASE_URL") or env("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL / SUPABASE_DB_URL is not configured.")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)


def ensure_notification_log(engine):
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS "sms_leave_email_log" (
                "Leave_Key" TEXT PRIMARY KEY,
                "Sent_At" TEXT,
                "Window_Start" TEXT,
                "Window_End" TEXT,
                "Recipient_Count" TEXT,
                "Subject" TEXT
            )
        '''))


def read_table(engine, table_name: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', engine)
    except Exception as exc:
        print(f"Could not read table {table_name}: {exc}")
        return pd.DataFrame()


def parse_timestamp_series_as_ist(series: pd.Series, timezone_name: str) -> pd.Series:
    """Parse app timestamp text and treat timezone-naive values as local business time."""
    parsed = pd.to_datetime(series.astype(str).str.strip(), errors="coerce", dayfirst=False)
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(series.astype(str).str.strip()[missing], errors="coerce", dayfirst=True)

    # App currently stores timestamp as text without timezone, e.g. 2026-05-14T03:34:41.
    # Treat those values as local business time, not UTC.
    try:
        if getattr(parsed.dt, "tz", None) is None:
            parsed = parsed.dt.tz_localize(timezone_name)
        else:
            parsed = parsed.dt.tz_convert(timezone_name)
    except Exception:
        # Fallback for mixed timezone values: parse as naive then localize.
        parsed = pd.to_datetime(series.astype(str).str.strip(), errors="coerce").dt.tz_localize(timezone_name)
    return parsed


def format_subject_window(dt: datetime) -> str:
    suffix = "th" if 11 <= dt.day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(dt.day % 10, "th")
    try:
        hour = dt.strftime("%-I %p").lower().replace(" ", "")
    except ValueError:
        hour = dt.strftime("%#I %p").lower().replace(" ", "")
    hour = hour.replace("am", " am").replace("pm", " pm")
    return f"{dt.day}{suffix} {dt.strftime('%b')} {hour}"


def leave_key(row: pd.Series) -> str:
    raw = "|".join([
        str(row.get("Timestamp", "")),
        str(row.get("Date", "")),
        str(row.get("Emp_ID", "")),
        str(row.get("Leave_Type", "")),
        str(row.get("Remarks", "")),
        str(row.get("Supervisor", "")),
        str(row.get("Status", "")),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_recipients(users: pd.DataFrame) -> list[str]:
    override = env("EMAIL_RECIPIENTS")
    if override:
        return sorted({x.strip().lower() for x in override.split(",") if "@" in x})

    if users.empty or "email" not in users.columns:
        return []

    df = users.copy()
    if "active" in df.columns:
        active = df["active"].astype(str).str.lower().isin(["true", "1", "yes", "active"])
        df = df[active]

    allowed = pd.Series(False, index=df.index)
    if "role" in df.columns:
        allowed = allowed | df["role"].astype(str).str.lower().isin(["admin", "supervisor", "system admin", "super admin"])
    if "allow_admin" in df.columns:
        allowed = allowed | df["allow_admin"].astype(str).str.lower().isin(["true", "1", "yes"])
    if "allow_supervisor" in df.columns:
        allowed = allowed | df["allow_supervisor"].astype(str).str.lower().isin(["true", "1", "yes"])

    df = df[allowed]
    return sorted({str(x).strip().lower() for x in df["email"].tolist() if "@" in str(x) and not str(x).endswith("@wagewise.local")})


def build_html_table(rows: pd.DataFrame) -> str:
    if rows.empty:
        return "<p>No approved leave entries were marked in this window.</p>"
    safe_rows = []
    for _, r in rows.iterrows():
        safe_rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('Date', '')))}</td>"
            f"<td>{html.escape(str(r.get('Name', '')))}</td>"
            f"<td>{html.escape(str(r.get('Leave_Type', '')))}</td>"
            f"<td>{html.escape(str(r.get('Status', '')))}</td>"
            f"<td>{html.escape(str(r.get('Remarks', '')))}</td>"
            "</tr>"
        )
    return """
    <table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;width:100%;">
        <thead style="background:#1F4E79;color:#ffffff;">
            <tr><th>Leave Date</th><th>Name</th><th>Type of Leave</th><th>Status</th><th>Remarks</th></tr>
        </thead>
        <tbody>{}</tbody>
    </table>
    """.format("\n".join(safe_rows))


def send_email(to_emails: list[str], subject: str, html_body: str):
    smtp_host = env("SMTP_HOST")
    smtp_port = int(env("SMTP_PORT", "587"))
    smtp_user = env("SMTP_USER")
    smtp_password = env("SMTP_PASSWORD")
    from_email = env("SMTP_FROM_EMAIL") or smtp_user

    missing = [name for name, value in {
        "SMTP_HOST": smtp_host,
        "SMTP_PORT": str(smtp_port),
        "SMTP_USER": smtp_user,
        "SMTP_PASSWORD": smtp_password,
        "SMTP_FROM_EMAIL/SMTP_USER": from_email,
    }.items() if not value]
    if missing:
        raise RuntimeError("Missing email configuration: " + ", ".join(missing))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, to_emails, msg.as_string())


def main():
    timezone_name = env("APP_TIMEZONE", "Asia/Kolkata")
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)

    # This implements: entries reported from yesterday 10:00 AM to today 09:59:59 AM
    # are included in today's 10 AM email, regardless of the leave Date.
    window_end = now.replace(hour=9, minute=59, second=59, microsecond=0)
    if now < now.replace(hour=10, minute=0, second=0, microsecond=0):
        window_end = window_end - timedelta(days=1)
    window_start = (window_end + timedelta(seconds=1)) - timedelta(days=1)

    subject_start = window_start.replace(hour=10, minute=0, second=0)
    subject_end = (window_end + timedelta(seconds=1)).replace(hour=10, minute=0, second=0)
    subject = f"Approved Leaves Marked from {format_subject_window(subject_start)} to {format_subject_window(subject_end)}"

    print(f"{APP_VERSION}")
    print(f"Run Time: {now.isoformat(timespec='seconds')}")
    print(f"Window Start: {window_start.isoformat(timespec='seconds')}")
    print(f"Window End: {window_end.isoformat(timespec='seconds')}")

    engine = get_engine()
    ensure_notification_log(engine)

    leaves = read_table(engine, "sms_leave_entries")
    employees = read_table(engine, "sms_employees")
    users = read_table(engine, "sms_users")
    sent_log = read_table(engine, "sms_leave_email_log")

    if leaves.empty:
        print("No leave entries table data found. Nothing to email.")
        return

    for col in ["Date", "Emp_ID", "Leave_Type", "Remarks", "Supervisor", "Timestamp", "Status"]:
        if col not in leaves.columns:
            leaves[col] = ""

    print(f"Total Leave Rows Before Filter: {len(leaves)}")

    leaves["_reported_at"] = parse_timestamp_series_as_ist(leaves["Timestamp"], timezone_name)
    leaves = leaves[leaves["_reported_at"].notna()].copy()
    print(f"Rows With Valid Timestamp: {len(leaves)}")

    print("Latest parsed leave timestamps:")
    try:
        print(leaves[["Timestamp", "_reported_at", "Date", "Emp_ID", "Leave_Type", "Status"]].tail(10).to_string(index=False))
    except Exception:
        pass

    leaves = leaves[
        (leaves["_reported_at"] >= pd.Timestamp(window_start)) &
        (leaves["_reported_at"] <= pd.Timestamp(window_end))
    ].copy()
    print(f"Rows After Reported-Time Window Filter: {len(leaves)}")

    # Business rule: only approved leaves should be emailed.
    leaves = leaves[leaves["Status"].astype(str).str.strip().str.lower().eq("approved")].copy()
    print(f"Rows After Approved-Only Filter: {len(leaves)}")

    leaves["Leave_Key"] = leaves.apply(leave_key, axis=1)
    sent_keys = set(sent_log.get("Leave_Key", pd.Series(dtype=str)).astype(str).tolist()) if not sent_log.empty else set()
    leaves = leaves[~leaves["Leave_Key"].astype(str).isin(sent_keys)].copy()
    print(f"Rows After Already-Sent Filter: {len(leaves)}")

    if not employees.empty and "Emp_ID" in employees.columns:
        emp_cols = [c for c in ["Emp_ID", "Name"] if c in employees.columns]
        if "Name" in emp_cols:
            emp_lookup = employees[emp_cols].drop_duplicates("Emp_ID")
            leaves = leaves.merge(emp_lookup, on="Emp_ID", how="left")

    if "Name" not in leaves.columns:
        leaves["Name"] = leaves["Emp_ID"]
    leaves["Name"] = leaves["Name"].fillna(leaves["Emp_ID"]).astype(str)

    leaves = leaves.sort_values(["_reported_at", "Date", "Name"], na_position="last")
    display_rows = leaves[["Date", "Name", "Leave_Type", "Status", "Remarks", "Leave_Key"]].copy()

    recipients = get_recipients(users)
    print(f"Valid Recipient Count: {len(recipients)}")
    if not recipients:
        print("No valid admin/supervisor recipient emails found. Set EMAIL_RECIPIENTS or update Access Manager emails.")
        return

    if display_rows.empty:
        print(f"No approved leave entries for window. Subject would have been: {subject}")
        return

    html_body = f"""
    <div style="font-family:Arial,sans-serif;color:#1A202C;">
        <h2 style="color:#1F4E79;margin-bottom:6px;">WageWise Daily Approved Leave Summary</h2>
        <p><strong>Reported Window:</strong> {html.escape(subject.replace('Approved Leaves Marked from ', ''))}</p>
        <p>This email includes approved leave entries reported during the window, regardless of the leave date.</p>
        {build_html_table(display_rows)}
        <p style="font-size:12px;color:#4A5568;margin-top:16px;">Generated automatically by WageWise.</p>
    </div>
    """

    send_email(recipients, subject, html_body)

    now_iso = datetime.now(tz).isoformat(timespec="seconds")
    log_rows = [
        {
            "Leave_Key": str(r["Leave_Key"]),
            "Sent_At": now_iso,
            "Window_Start": window_start.isoformat(timespec="seconds"),
            "Window_End": window_end.isoformat(timespec="seconds"),
            "Recipient_Count": str(len(recipients)),
            "Subject": subject,
        }
        for _, r in display_rows.iterrows()
    ]
    with engine.begin() as conn:
        for row in log_rows:
            conn.execute(text('''
                INSERT INTO "sms_leave_email_log" ("Leave_Key", "Sent_At", "Window_Start", "Window_End", "Recipient_Count", "Subject")
                VALUES (:Leave_Key, :Sent_At, :Window_Start, :Window_End, :Recipient_Count, :Subject)
                ON CONFLICT ("Leave_Key") DO NOTHING
            '''), row)

    print(f"Sent leave email to {len(recipients)} recipient(s). Rows: {len(display_rows)}. Subject: {subject}")


if __name__ == "__main__":
    main()
