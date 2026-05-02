"""
Salary Management System - Streamlit app.py
Supabase PostgreSQL + SQLAlchemy connection fixed for Streamlit Cloud.

IMPORTANT:
1. Do NOT hardcode your real password in this file.
2. Put DATABASE_URL in Streamlit Cloud Secrets or local .streamlit/secrets.toml.
3. Recommended Supabase transaction pooler URL format:
   DATABASE_URL = "postgresql+psycopg2://postgres.YOUR_PROJECT_REF:YOUR_ENCODED_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
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
# Supabase / SQLAlchemy connection helpers
# -----------------------------------------------------------------------------

def get_secret_value(key: str, default: str = "") -> str:
    """Read value from Streamlit secrets first, then environment variables."""
    try:
        if key in st.secrets:
            value = st.secrets[key]
            return str(value).strip()
    except Exception:
        # Local machine may not have .streamlit/secrets.toml yet.
        pass

    return str(os.getenv(key, default)).strip()


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
    url = (raw_url or "").strip().strip('"').strip("'")

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


@st.cache_resource(show_spinner=False)
def get_engine() -> Optional[Engine]:
    """
    Create a SQLAlchemy engine for Supabase Transaction Pooler.

    For Streamlit Cloud / serverless-style deployments, Supabase recommends:
      - Transaction pooler
      - Port 6543
      - SQLAlchemy NullPool
    """
    raw_url = (
        get_secret_value("DATABASE_URL")
        or get_secret_value("SUPABASE_DB_URL")
        or get_secret_value("DB_URL")
    )

    database_url = normalize_database_url(raw_url)

    if not database_url:
        return None

    return create_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        client_encoding="utf8",
        future=True,
    )


def test_database_connection() -> tuple[bool, str]:
    """Return database connection status and message."""
    engine = get_engine()

    if engine is None:
        return (
            False,
            "DATABASE_URL is missing. Add it in Streamlit Cloud → App → Settings → Secrets.",
        )

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS ok"))
            value = result.scalar()

        if value == 1:
            return True, "Connected to Supabase PostgreSQL successfully."
        return False, "Database responded, but the test query did not return the expected result."

    except Exception as exc:
        return False, str(exc)


def run_sql(sql: str, params: Optional[dict[str, Any]] = None) -> None:
    """Execute INSERT/UPDATE/DELETE/DDL SQL."""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL missing. Cannot run SQL.")

    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def read_sql_df(sql: str, params: Optional[dict[str, Any]] = None) -> pd.DataFrame:
    """Read SQL query into a pandas DataFrame."""
    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL missing. Cannot read SQL.")

    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


# -----------------------------------------------------------------------------
# Database table setup
# -----------------------------------------------------------------------------

def initialize_sms_tables() -> None:
    """Create basic SMS tables if they do not already exist."""
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

    run_sql(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id BIGSERIAL PRIMARY KEY,
            attendance_date DATE NOT NULL,
            emp_id TEXT NOT NULL REFERENCES employees(emp_id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            leave_type TEXT,
            supervisor TEXT,
            remarks TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(attendance_date, emp_id)
        );
        """
    )

    run_sql(
        """
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id BIGSERIAL PRIMARY KEY,
            payroll_month DATE NOT NULL,
            emp_id TEXT NOT NULL REFERENCES employees(emp_id) ON DELETE CASCADE,
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
            return read_sql_df(
                """
                SELECT emp_id, employee_name, level, monthly_salary, paid_leave_quota, active
                FROM employees
                ORDER BY emp_id;
                """
            )
        except Exception:
            return pd.DataFrame(
                columns=["emp_id", "employee_name", "level", "monthly_salary", "paid_leave_quota", "active"]
            )

    ensure_csv_files()
    return pd.read_csv(EMPLOYEE_CSV)


def load_attendance(use_db: bool) -> pd.DataFrame:
    if use_db:
        try:
            return read_sql_df(
                """
                SELECT attendance_date, emp_id, status, leave_type, supervisor, remarks
                FROM attendance
                ORDER BY attendance_date DESC, emp_id;
                """
            )
        except Exception:
            return pd.DataFrame(
                columns=["attendance_date", "emp_id", "status", "leave_type", "supervisor", "remarks"]
            )

    ensure_csv_files()
    return pd.read_csv(ATTENDANCE_CSV)


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------
st.title(f"💼 {APP_NAME}")
st.caption("Supabase PostgreSQL enabled with safe local CSV fallback.")

connected, db_message = test_database_connection()

if connected:
    st.success("✅ Supabase database connected.")
else:
    st.warning("⚠️ Database connection issue. Falling back to local CSV for this session.")
    with st.expander("Show database error details"):
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

# Try to initialize tables automatically once after confirmed DB connection.
if connected:
    try:
        initialize_sms_tables()
    except Exception as exc:
        st.error("Connected to Supabase, but table setup failed.")
        st.code(str(exc))

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
        "If this page shows 'Supabase database connected', your SQLAlchemy connection is working. "
        "You can now connect the rest of your Salary Management System pages to the same engine functions."
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
                            "emp_id": emp_id.strip(),
                            "employee_name": employee_name.strip(),
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
                    "emp_id": emp_id.strip(),
                    "employee_name": employee_name.strip(),
                    "level": level,
                    "monthly_salary": monthly_salary,
                    "paid_leave_quota": int(paid_leave_quota),
                    "active": bool(active),
                }
                df = df[df["emp_id"].astype(str) != emp_id.strip()]
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(EMPLOYEE_CSV, index=False)
                st.success("Employee saved to local CSV fallback.")
                st.rerun()

    st.dataframe(load_employees(connected), use_container_width=True, hide_index=True)

with attendance_tab:
    st.subheader("Attendance Entry")

    employees_df = load_employees(connected)
    employee_ids = employees_df["emp_id"].astype(str).tolist() if not employees_df.empty else []

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
                            "emp_id": selected_emp_id,
                            "status": status,
                            "leave_type": leave_type,
                            "supervisor": supervisor,
                            "remarks": remarks,
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
                    "emp_id": selected_emp_id,
                    "status": status,
                    "leave_type": leave_type,
                    "supervisor": supervisor,
                    "remarks": remarks,
                }
                df = df[~((df["attendance_date"].astype(str) == str(attendance_date)) & (df["emp_id"].astype(str) == selected_emp_id))]
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
            emp_id = str(emp["emp_id"])
            monthly_salary = float(emp.get("monthly_salary", 0) or 0)
            per_day_salary = monthly_salary / days_in_month if days_in_month else 0

            emp_att = attendance_df[attendance_df["emp_id"].astype(str) == emp_id].copy()
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
