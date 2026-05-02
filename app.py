"""
Salary Management System - Streamlit app.py
Salary Management System with Supabase PostgreSQL persistence and CSV fallback.

IMPORTANT:
1. Do NOT hardcode your real password in this file.
2. Put DATABASE_URL in Streamlit Cloud Secrets or local .streamlit/secrets.toml.
3. Recommended Streamlit Secret format:
   DATABASE_URL = "postgresql+psycopg2://postgres.YOUR_PROJECT_REF:YOUR_DATABASE_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require"
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Salary Management System",
    page_icon="💼",
    layout="wide",
)

APP_NAME = "Salary Management System"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
EMPLOYEE_CSV = DATA_DIR / "employees.csv"
ATTENDANCE_CSV = DATA_DIR / "attendance.csv"

# -----------------------------------------------------------------------------
# Null-character / text sanitization helpers
# -----------------------------------------------------------------------------

def remove_null_characters(value: Any) -> Any:
    """
    Removes real and encoded null characters from strings.

    Why this exists:
    - Python/psycopg2 raises "embedded null character" when a text value contains \x00.
    - Sometimes the bad value is not visible on screen.
    - Sometimes it appears URL-encoded as %00 inside DATABASE_URL.
    """
    if isinstance(value, str):
        cleaned = value.replace("\x00", "")
        cleaned = cleaned.replace("\\x00", "")
        cleaned = cleaned.replace("\\0", "")
        cleaned = re.sub(r"%00", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"%2500", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    return value


def clean_text_value(value: Any) -> Any:
    """Safely cleans user-entered text without changing numbers/dates/booleans."""
    if pd.isna(value) if not isinstance(value, (list, dict, tuple, set)) else False:
        return ""
    if isinstance(value, str):
        return remove_null_characters(value)
    return value


def clean_sql_params(params: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Clean SQL parameters before passing them to psycopg2."""
    if not params:
        return {}

    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        cleaned_key = str(remove_null_characters(key))
        if isinstance(value, str):
            cleaned[cleaned_key] = remove_null_characters(value)
        else:
            cleaned[cleaned_key] = value
    return cleaned


def clean_dataframe_values(df: pd.DataFrame) -> pd.DataFrame:
    """Remove hidden null characters from all object/string columns in a dataframe."""
    if df is None or df.empty:
        return df

    cleaned = df.copy()
    for col in cleaned.columns:
        if cleaned[col].dtype == "object" or str(cleaned[col].dtype).startswith("string"):
            cleaned[col] = cleaned[col].map(clean_text_value)
    return cleaned

# -----------------------------------------------------------------------------
# Supabase / SQLAlchemy connection helpers
# -----------------------------------------------------------------------------


def get_database_url() -> str:
    """
    Reads DATABASE_URL safely from Streamlit Secrets first,
    then from environment variables.

    Important:
    - Do not hardcode the password in this file.
    - Keep DATABASE_URL in Streamlit Cloud Secrets.
    - This removes hidden/null characters that can break psycopg2.
    """
    try:
        db_url = st.secrets.get("DATABASE_URL", "")
    except Exception:
        db_url = os.getenv("DATABASE_URL", "")

    db_url = str(remove_null_characters(db_url)).strip().strip('"').strip("'")
    return db_url


def normalize_database_url(raw_url: str) -> str:
    """
    Normalize Supabase URL for SQLAlchemy + psycopg2.

    Accepts:
      postgres://...
      postgresql://...
      postgresql+psycopg2://...

    Returns:
      postgresql+psycopg2://...?sslmode=require
    """
    url = str(remove_null_characters(raw_url or "")).strip().strip('"').strip("'")

    if not url:
        return ""

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]

    # Supabase requires SSL for cloud database connections.
    if "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"

    return url


DATABASE_URL = normalize_database_url(get_database_url())



# Create SQLAlchemy engine BEFORE running any test query.
engine: Optional[Engine] = None

if DATABASE_URL:
    try:
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
            pool_pre_ping=True,
            future=True,
            connect_args={
                "sslmode": "require",
                "connect_timeout": 10,
            },
        )
    except Exception as exc:
        st.error("Failed to create database engine.")
        st.exception(exc)
else:
    st.warning("DATABASE_URL is missing. App will use local CSV fallback.")


def check_database_connection() -> tuple[bool, str]:
    """
    Checks whether Supabase is reachable and returns status/message for fallback logic.
    """
    if engine is None:
        return False, "Database engine was not created. Check DATABASE_URL in Streamlit Secrets."

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user;"))
            row = result.fetchone()

        database_name = row[0] if row else "unknown"
        database_user = row[1] if row else "unknown"
        return True, f"Connected to Supabase PostgreSQL successfully. Database: {database_name}; User: {database_user}"

    except Exception as exc:
        return False, str(exc)


def run_sql(sql: str, params: Optional[dict[str, Any]] = None) -> None:
    """Execute INSERT/UPDATE/DELETE/DDL SQL."""
    if engine is None:
        raise RuntimeError("DATABASE_URL missing or database engine not created. Cannot run SQL.")

    with engine.begin() as conn:
        conn.execute(text(sql), clean_sql_params(params))


def read_sql_df(sql: str, params: Optional[dict[str, Any]] = None) -> pd.DataFrame:
    """Read SQL query into a pandas DataFrame."""
    if engine is None:
        raise RuntimeError("DATABASE_URL missing or database engine not created. Cannot read SQL.")

    with engine.connect() as conn:
        return clean_dataframe_values(pd.read_sql_query(text(sql), conn, params=clean_sql_params(params)))


# -----------------------------------------------------------------------------
# Database table setup
# -----------------------------------------------------------------------------

def initialize_sms_tables() -> None:
    """Create/repair basic SMS tables if they do not already exist."""
    run_sql(
        """
        CREATE TABLE IF NOT EXISTS employees (
            emp_id TEXT PRIMARY KEY,
            employee_name TEXT NOT NULL,
            level TEXT DEFAULT 'L1',
            monthly_salary NUMERIC(12,2) DEFAULT 0,
            paid_leave_quota INTEGER DEFAULT 2,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    # If an older/incompatible employees table already existed, CREATE IF NOT EXISTS
    # would not add missing columns. These ALTERs repair that situation safely.
    for sql in [
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS emp_id TEXT;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS employee_name TEXT;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS level TEXT DEFAULT 'L1';",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS monthly_salary NUMERIC(12,2) DEFAULT 0;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS paid_leave_quota INTEGER DEFAULT 2;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        "ALTER TABLE employees ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();",
        "CREATE UNIQUE INDEX IF NOT EXISTS employees_emp_id_unique_idx ON employees (emp_id);",
    ]:
        try:
            run_sql(sql)
        except Exception:
            # Do not block the app during repair; read/save will show specific errors if needed.
            pass

    run_sql(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id BIGSERIAL PRIMARY KEY,
            attendance_date DATE NOT NULL,
            emp_id TEXT NOT NULL,
            status TEXT NOT NULL,
            leave_type TEXT,
            supervisor TEXT,
            remarks TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    for sql in [
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS attendance_date DATE;",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS emp_id TEXT;",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS status TEXT;",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS leave_type TEXT;",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS supervisor TEXT;",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS remarks TEXT;",
        "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        "CREATE UNIQUE INDEX IF NOT EXISTS attendance_date_emp_id_unique_idx ON attendance (attendance_date, emp_id);",
    ]:
        try:
            run_sql(sql)
        except Exception:
            pass

    run_sql(
        """
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id BIGSERIAL PRIMARY KEY,
            payroll_month DATE NOT NULL,
            emp_id TEXT NOT NULL,
            working_days INTEGER DEFAULT 0,
            present_days NUMERIC(8,2) DEFAULT 0,
            paid_leave_days NUMERIC(8,2) DEFAULT 0,
            lop_days NUMERIC(8,2) DEFAULT 0,
            penalties NUMERIC(12,2) DEFAULT 0,
            gross_salary NUMERIC(12,2) DEFAULT 0,
            net_salary NUMERIC(12,2) DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(payroll_month, emp_id)
        );
        """
    )


# -----------------------------------------------------------------------------
# Data normalization helpers
# -----------------------------------------------------------------------------

EXPECTED_EMPLOYEE_COLUMNS = [
    "emp_id",
    "employee_name",
    "level",
    "monthly_salary",
    "paid_leave_quota",
    "active",
]

EXPECTED_ATTENDANCE_COLUMNS = [
    "attendance_date",
    "emp_id",
    "status",
    "leave_type",
    "supervisor",
    "remarks",
]

COLUMN_ALIASES = {
    "employee_id": "emp_id",
    "emp id": "emp_id",
    "empid": "emp_id",
    "emp_code": "emp_id",
    "employee_code": "emp_id",
    "employee no": "emp_id",
    "employee_number": "emp_id",
    "employee name": "employee_name",
    "emp_name": "employee_name",
    "name": "employee_name",
    "full_name": "employee_name",
    "employee": "employee_name",
    "salary": "monthly_salary",
    "monthly_amount": "monthly_salary",
    "fixed_monthly_salary": "monthly_salary",
    "gross_salary": "monthly_salary",
    "paid_leaves": "paid_leave_quota",
    "paid_leave_balance": "paid_leave_quota",
    "leave_quota": "paid_leave_quota",
    "quota": "paid_leave_quota",
    "attendance date": "attendance_date",
    "date": "attendance_date",
    "leave status": "status",
    "leave_type/status": "status",
}


def clean_column_name(column: object) -> str:
    """Convert old Excel/CSV style column names into app-safe snake_case names."""
    col = str(column or "").strip().replace("\ufeff", "")
    lowered = col.lower().strip()
    lowered = lowered.replace("-", "_").replace("/", "_").replace(".", "_")
    lowered = "_".join(lowered.split())
    return COLUMN_ALIASES.get(lowered, lowered)


def normalize_dataframe_columns(df: pd.DataFrame, expected_columns: list[str], table_name: str) -> pd.DataFrame:
    """
    Normalizes column names so old data with Employee ID / Emp_ID / employee_id
    does not crash the app when the code expects emp_id.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=expected_columns)

    normalized = clean_dataframe_values(df.copy())
    normalized.columns = [clean_column_name(c) for c in normalized.columns]

    # If duplicate columns are created after normalization, keep the first non-null value.
    if normalized.columns.duplicated().any():
        normalized = normalized.groupby(level=0, axis=1).first()

    # Last-resort mapping if an existing DB table only has id, but not emp_id.
    if "emp_id" not in normalized.columns and "id" in normalized.columns:
        normalized["emp_id"] = normalized["id"].astype(str)

    # Avoid hard crash: return a clean empty expected frame if emp_id is genuinely unavailable.
    if table_name == "employees" and "emp_id" not in normalized.columns:
        st.error(
            "Employee data was found, but no Employee ID column could be identified. "
            "Please rename the ID column to emp_id or Employee ID."
        )
        st.write("Available columns:", list(df.columns))
        return pd.DataFrame(columns=expected_columns)

    if table_name == "attendance" and "emp_id" not in normalized.columns:
        # Attendance can be empty/incomplete during setup; avoid crashing payroll.
        return pd.DataFrame(columns=expected_columns)

    for col in expected_columns:
        if col not in normalized.columns:
            if col == "level":
                normalized[col] = "L1"
            elif col == "monthly_salary":
                normalized[col] = 0.0
            elif col == "paid_leave_quota":
                normalized[col] = 2
            elif col == "active":
                normalized[col] = True
            else:
                normalized[col] = ""

    if "monthly_salary" in normalized.columns:
        normalized["monthly_salary"] = pd.to_numeric(normalized["monthly_salary"], errors="coerce").fillna(0.0)
    if "paid_leave_quota" in normalized.columns:
        normalized["paid_leave_quota"] = pd.to_numeric(normalized["paid_leave_quota"], errors="coerce").fillna(2).astype(int)
    if "active" in normalized.columns:
        normalized["active"] = normalized["active"].fillna(True)

    # Remove blank employee IDs to avoid selectbox/runtime issues.
    if "emp_id" in normalized.columns:
        normalized["emp_id"] = normalized["emp_id"].astype(str).str.strip()
        normalized = normalized[normalized["emp_id"] != ""]

    return normalized[expected_columns]

# -----------------------------------------------------------------------------
# CSV fallback helpers
# -----------------------------------------------------------------------------

def ensure_csv_files() -> None:
    """Create fallback CSV files if they do not exist."""
    if not EMPLOYEE_CSV.exists():
        pd.DataFrame(
            columns=[
                "emp_id",
                "employee_name",
                "level",
                "monthly_salary",
                "paid_leave_quota",
                "active",
            ]
        ).to_csv(EMPLOYEE_CSV, index=False)

    if not ATTENDANCE_CSV.exists():
        pd.DataFrame(
            columns=[
                "attendance_date",
                "emp_id",
                "status",
                "leave_type",
                "supervisor",
                "remarks",
            ]
        ).to_csv(ATTENDANCE_CSV, index=False)


def load_employees(use_db: bool) -> pd.DataFrame:
    if use_db:
        try:
            df = read_sql_df("SELECT * FROM employees ORDER BY emp_id NULLS LAST;")
            return normalize_dataframe_columns(df, EXPECTED_EMPLOYEE_COLUMNS, "employees")
        except Exception as exc:
            st.warning("Could not read employees table from Supabase. Showing an empty employee list.")
            with st.expander("Employee table read error"):
                st.code(str(exc))
            return pd.DataFrame(columns=EXPECTED_EMPLOYEE_COLUMNS)

    ensure_csv_files()
    df = pd.read_csv(EMPLOYEE_CSV)
    return normalize_dataframe_columns(df, EXPECTED_EMPLOYEE_COLUMNS, "employees")


def load_attendance(use_db: bool) -> pd.DataFrame:
    if use_db:
        try:
            df = read_sql_df("SELECT * FROM attendance ORDER BY attendance_date DESC NULLS LAST, emp_id NULLS LAST;")
            return normalize_dataframe_columns(df, EXPECTED_ATTENDANCE_COLUMNS, "attendance")
        except Exception as exc:
            st.warning("Could not read attendance table from Supabase. Showing an empty attendance list.")
            with st.expander("Attendance table read error"):
                st.code(str(exc))
            return pd.DataFrame(columns=EXPECTED_ATTENDANCE_COLUMNS)

    ensure_csv_files()
    df = pd.read_csv(ATTENDANCE_CSV)
    return normalize_dataframe_columns(df, EXPECTED_ATTENDANCE_COLUMNS, "attendance")


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------
st.title(f"💼 {APP_NAME}")
st.caption("Supabase PostgreSQL enabled with safe local CSV fallback.")

# Prepare database once at startup.
# The app uses Supabase only when both login and table setup are successful.
connected, db_message = check_database_connection()

if connected:
    try:
        initialize_sms_tables()
        db_message = "Supabase login and SMS table setup completed successfully."
    except Exception as exc:
        connected = False
        db_message = f"Supabase login worked, but SMS table setup failed. Raw error: {exc}"

if connected:
    st.success("✅ LIVE MODE: Supabase database is connected and SMS tables are ready.")
else:
    st.warning("⚠️ CSV FALLBACK MODE: Supabase is not ready for this session.")
    with st.expander("Database error details"):
        st.code(db_message)

# Sidebar controls
with st.sidebar:
    st.header("System Status")
    st.write("Database:", "✅ Supabase" if connected else "⚠️ Local CSV fallback")

    if connected:
        if st.button("Create / Repair SMS Tables", use_container_width=True):
            try:
                initialize_sms_tables()
                st.success("SMS tables are ready in Supabase.")
                st.rerun()
            except Exception as exc:
                st.error("Could not create tables.")
                st.code(str(exc))

    st.divider()
    st.caption("Keep DATABASE_URL only in Streamlit Secrets, not inside GitHub code.")

# Main tabs
home_tab, employee_tab, attendance_tab, payroll_tab = st.tabs(
    ["Home", "Employee Master", "Attendance", "Payroll Preview"]
)

with home_tab:
    st.subheader("Connection Summary")

    col1, col2, col3 = st.columns(3)

    employees_df = load_employees(connected)
    attendance_df = load_attendance(connected)

    with col1:
        st.metric("Employees", len(employees_df))
    with col2:
        st.metric("Attendance Entries", len(attendance_df))
    with col3:
        st.metric("Current Storage", "Supabase" if connected else "CSV")

    st.info(
        "Use the Employee Master tab to add staff, Attendance tab to enter leave/attendance, "
        "and Payroll Preview tab to review salary impact for the selected month."
    )

with employee_tab:
    st.subheader("Employee Master")

    employees_df = load_employees(connected)

    with st.form("employee_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            emp_id = st.text_input("Employee ID", placeholder="Example: EMP001")
            employee_name = st.text_input("Employee Name")
        with c2:
            level = st.selectbox("Level", ["L1", "L2"], index=0)
            monthly_salary = st.number_input("Monthly Salary", min_value=0.0, step=500.0)
        with c3:
            default_quota = 4 if level == "L2" else 2
            paid_leave_quota = st.number_input(
                "Paid Leave Quota",
                min_value=0,
                step=1,
                value=default_quota,
            )
            active = st.checkbox("Active", value=True)

        submitted = st.form_submit_button("Save Employee")

    if submitted:
        if not emp_id or not employee_name:
            st.error("Employee ID and Employee Name are required.")
        else:
            if connected:
                try:
                    run_sql(
                        """
                        INSERT INTO employees
                            (emp_id, employee_name, level, monthly_salary, paid_leave_quota, active, updated_at)
                        VALUES
                            (:emp_id, :employee_name, :level, :monthly_salary, :paid_leave_quota, :active, NOW())
                        ON CONFLICT (emp_id)
                        DO UPDATE SET
                            employee_name = EXCLUDED.employee_name,
                            level = EXCLUDED.level,
                            monthly_salary = EXCLUDED.monthly_salary,
                            paid_leave_quota = EXCLUDED.paid_leave_quota,
                            active = EXCLUDED.active,
                            updated_at = NOW();
                        """,
                        {
                            "emp_id": remove_null_characters(emp_id),
                            "employee_name": remove_null_characters(employee_name),
                            "level": level,
                            "monthly_salary": monthly_salary,
                            "paid_leave_quota": int(paid_leave_quota),
                            "active": bool(active),
                        },
                    )
                    st.success("Employee saved to Supabase.")
                    st.rerun()
                except Exception as exc:
                    st.error("Could not save employee to Supabase.")
                    st.code(str(exc))
            else:
                ensure_csv_files()
                df = pd.read_csv(EMPLOYEE_CSV)
                new_row = {
                    "emp_id": remove_null_characters(emp_id),
                    "employee_name": remove_null_characters(employee_name),
                    "level": level,
                    "monthly_salary": monthly_salary,
                    "paid_leave_quota": int(paid_leave_quota),
                    "active": bool(active),
                }
                df = normalize_dataframe_columns(df, EXPECTED_EMPLOYEE_COLUMNS, "employees")
                df = df[df["emp_id"].astype(str) != remove_null_characters(emp_id)]
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(EMPLOYEE_CSV, index=False)
                st.success("Employee saved to local CSV fallback.")
                st.rerun()

    st.dataframe(load_employees(connected), use_container_width=True, hide_index=True)

with attendance_tab:
    st.subheader("Attendance Entry")

    employees_df = load_employees(connected)
    employee_ids = [remove_null_characters(x) for x in employees_df.get("emp_id", pd.Series(dtype=str)).astype(str).str.strip().tolist()] if not employees_df.empty else []

    if not employee_ids:
        st.info("Add employees first before entering attendance.")
    else:
        with st.form("attendance_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                attendance_date = st.date_input("Attendance Date")
                selected_emp_id = st.selectbox("Employee ID", employee_ids)
            with c2:
                status = st.selectbox(
                    "Status",
                    [
                        "Present",
                        "Leave - Full Day",
                        "Leave - Half Day",
                        "Leave - Uninformed",
                        "Leave - Collaborative",
                    ],
                )
                leave_type = None if status == "Present" else status
            with c3:
                supervisor = st.text_input("Supervisor")
                remarks = st.text_area("Remarks", height=80)

            attendance_submitted = st.form_submit_button("Save Attendance")

        if attendance_submitted:
            if connected:
                try:
                    run_sql(
                        """
                        INSERT INTO attendance
                            (attendance_date, emp_id, status, leave_type, supervisor, remarks)
                        VALUES
                            (:attendance_date, :emp_id, :status, :leave_type, :supervisor, :remarks)
                        ON CONFLICT (attendance_date, emp_id)
                        DO UPDATE SET
                            status = EXCLUDED.status,
                            leave_type = EXCLUDED.leave_type,
                            supervisor = EXCLUDED.supervisor,
                            remarks = EXCLUDED.remarks;
                        """,
                        {
                            "attendance_date": attendance_date,
                            "emp_id": remove_null_characters(selected_emp_id),
                            "status": remove_null_characters(status),
                            "leave_type": remove_null_characters(leave_type) if leave_type else None,
                            "supervisor": remove_null_characters(supervisor),
                            "remarks": remove_null_characters(remarks),
                        },
                    )
                    st.success("Attendance saved to Supabase.")
                    st.rerun()
                except Exception as exc:
                    st.error("Could not save attendance to Supabase.")
                    st.code(str(exc))
            else:
                ensure_csv_files()
                df = pd.read_csv(ATTENDANCE_CSV)
                new_row = {
                    "attendance_date": str(attendance_date),
                    "emp_id": remove_null_characters(selected_emp_id),
                    "status": remove_null_characters(status),
                    "leave_type": remove_null_characters(leave_type) if leave_type else None,
                    "supervisor": remove_null_characters(supervisor),
                    "remarks": remove_null_characters(remarks),
                }
                df = normalize_dataframe_columns(df, EXPECTED_ATTENDANCE_COLUMNS, "attendance")
                df = df[~((df["attendance_date"].astype(str) == str(attendance_date)) & (df["emp_id"].astype(str) == remove_null_characters(selected_emp_id)))]
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(ATTENDANCE_CSV, index=False)
                st.success("Attendance saved to local CSV fallback.")
                st.rerun()

    st.dataframe(load_attendance(connected), use_container_width=True, hide_index=True)

with payroll_tab:
    st.subheader("Payroll Preview")
    st.caption("This is a basic preview screen. Your detailed payroll rules can be plugged into this section next.")

    employees_df = load_employees(connected)
    attendance_df = load_attendance(connected)

    if employees_df.empty:
        st.info("No employees available for payroll preview.")
    else:
        month = st.date_input("Payroll Month", value=pd.Timestamp.today().date().replace(day=1))
        month_start = pd.Timestamp(month).replace(day=1)
        month_end = month_start + pd.offsets.MonthEnd(0)
        days_in_month = int(month_end.day)

        preview_rows = []
        for _, emp in employees_df.iterrows():
            emp_id = str(emp.get("emp_id", "")).strip()
            if not emp_id:
                continue

            monthly_salary = float(emp.get("monthly_salary", 0) or 0)
            per_day_salary = monthly_salary / days_in_month if days_in_month else 0

            emp_att = attendance_df[attendance_df.get("emp_id", pd.Series(dtype=str)).astype(str) == emp_id].copy()
            if not emp_att.empty and "attendance_date" in emp_att.columns:
                emp_att["attendance_date"] = pd.to_datetime(emp_att["attendance_date"], errors="coerce")
                emp_att = emp_att[
                    (emp_att["attendance_date"] >= month_start)
                    & (emp_att["attendance_date"] <= month_end)
                ]

            uninformed_count = int((emp_att.get("status", pd.Series(dtype=str)) == "Leave - Uninformed").sum())
            collaborative_count = int((emp_att.get("status", pd.Series(dtype=str)) == "Leave - Collaborative").sum())
            full_leave_count = int((emp_att.get("status", pd.Series(dtype=str)) == "Leave - Full Day").sum())
            half_leave_count = int((emp_att.get("status", pd.Series(dtype=str)) == "Leave - Half Day").sum())

            leave_days = full_leave_count + (half_leave_count * 0.5) + uninformed_count + (collaborative_count * 1.5)
            paid_quota = float(emp.get("paid_leave_quota", 0) or 0)
            lop_days = max(0.0, leave_days - paid_quota)
            penalty = uninformed_count * 50
            net_salary = max(0.0, monthly_salary - (lop_days * per_day_salary) - penalty)

            preview_rows.append(
                {
                    "emp_id": emp_id,
                    "employee_name": emp.get("employee_name", ""),
                    "monthly_salary": round(monthly_salary, 2),
                    "days_in_month": days_in_month,
                    "leave_days": round(leave_days, 2),
                    "paid_leave_quota": paid_quota,
                    "lop_days": round(lop_days, 2),
                    "penalty": round(penalty, 2),
                    "net_salary_preview": round(net_salary, 2),
                }
            )

        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        st.warning(
            "Note: This preview uses your broad SMS rules only. Final production payroll should also include advance deductions, encashment, approvals, audit logs, and payslip generation."
        )
