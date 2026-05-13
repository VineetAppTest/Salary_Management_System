import calendar
import hashlib
import os
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from io import BytesIO
from sqlalchemy import create_engine, text

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

COLOR_SCHEMA = {
    "primary": "#1F4E79",
    "primary_dark": "#163B5C",
    "secondary": "#D9EAF7",
    "success": "#1F7A4D",
    "warning": "#B7791F",
    "danger": "#B42318",
    "background": "#F7FAFC",
    "card": "#FFFFFF",
    "text": "#1A202C",
}

LEAVE_UNITS = {
    "Leave - Full Day": 1.0,
    "Leave - Half Day": 0.5,
    "Leave - Uninformed": 1.0,
    "Leave - Collaborative": 1.0,
}

LEVEL_OPTIONS = ["L0", "L1", "L2"]

def normalize_employee_level(level):
    level_value = str(level or "L1").strip().upper()
    return level_value if level_value in LEVEL_OPTIONS else "L1"

def paid_leave_allowance_for_level(level):
    level_value = normalize_employee_level(level)
    if level_value == "L0":
        return 0.0
    if level_value == "L1":
        return 2.0
    return 4.0

def is_contractor_level(level):
    return normalize_employee_level(level) == "L0"


def employee_joining_date(emp):
    """Return Date of Joining as Timestamp, or NaT if not provided/invalid."""
    try:
        return parse_app_date_value(emp.get("Date_of_Joining", ""))
    except Exception:
        return pd.NaT


def employee_service_window_for_month(emp, year, month):
    """Calculate whether employee is eligible for payroll in month and payable service days.

    Rule: if Date of Joining is after the payroll month, employee is omitted.
    If joining happens within the payroll month, salary and paid leave quota are pro-rated
    from joining date through month end. Blank DOJ means existing employee / full-month eligible.
    """
    total_days = calendar.monthrange(int(year), int(month))[1]
    month_start = pd.Timestamp(year=int(year), month=int(month), day=1)
    month_end = pd.Timestamp(year=int(year), month=int(month), day=total_days)
    join_dt = employee_joining_date(emp)
    if pd.isna(join_dt):
        return True, month_start, total_days, 1.0, join_dt
    join_dt = pd.Timestamp(join_dt).normalize()
    if join_dt > month_end:
        return False, None, 0, 0.0, join_dt
    service_start = max(join_dt, month_start)
    service_days = max(0, (month_end - service_start).days + 1)
    fraction = service_days / total_days if total_days else 0.0
    return service_days > 0, service_start, service_days, fraction, join_dt


def prorate_paid_leave_quota(level, service_fraction):
    base = paid_leave_allowance_for_level(level)
    # Round down to nearest half-day to avoid over-crediting partial month leave.
    return max(0.0, int((base * float(service_fraction)) * 2) / 2.0)


BUILD_VERSION = "V116.5"
BUILD_LABEL = "V116.5 · Daily Leave Email Automation"
NAV_SCROLL_ANCHOR = "ww-section-content-anchor"

REQUIRED_FILES = {
    "users": ["email", "name", "role", "password_hash", "active", "allow_admin", "allow_supervisor"],
    "employees": ["Emp_ID", "Name", "Level", "Monthly_Salary", "Extra_Paid_Leaves", "Status", "Supervisor_Email", "Date_of_Joining"],
    "leave_entries": ["Date", "Emp_ID", "Leave_Type", "Remarks", "Supervisor", "Timestamp", "Status"],
    "employee_holidays": ["Holiday_ID", "Date", "Emp_ID", "Festival_Name", "Remarks", "Created_By", "Timestamp"],
    "advance_cases": ["Advance_ID", "Emp_ID", "Advance_Date", "Amount_Given", "Refund_Start_Month", "First_Month_Deduction", "Remaining_Months", "Status", "Remarks", "Created_By", "Timestamp"],
    "advance_schedule": ["Advance_ID", "Emp_ID", "Deduction_Month", "Scheduled_Deduction", "Admin_Updated_Deduction", "Final_Deduction", "Status", "Updated_By", "Updated_At"],
    "payroll_items": ["Month", "Emp_ID", "Name", "Level", "Monthly_Salary", "Total_Days", "Daily_Wage", "Leave_Units", "Holiday_Exclusions", "Extra_Paid_Leaves", "Paid_Leave_Allowed", "Paid_Leave_Used", "Leaves_After_Allowed_And_Exclusions", "LOP_Days", "Leave_Deduction_Cost", "Present_Days", "Unused_Leaves", "Encashment", "Uninformed_Count", "Collaborative_Count", "Special_Deductions", "Special_Deductions_Applied", "Advance_Prior_Month", "Advance_Given_This_Month", "Advance_Deduction", "Advance_Balance_Open", "Advance_Balance_Close", "Final_Salary_Without_Special", "Final_Salary_With_Special", "Admin_Override_Extra_Leaves", "Admin_Override_Special_Deduction", "Admin_Override_Advance_Deduction", "Payroll_Status", "Approved_By", "Approved_At", "Locked", "Last_Recalculated_By", "Last_Recalculated_At"],
    "leave_adjustment_log": ["Month", "Date", "Emp_ID", "Original_Leave_Type", "Leave_Units", "Paid_Leave_Before", "Paid_Leave_Used", "LOP_Created", "Special_Deduction", "Remarks", "Supervisor", "Timestamp"],
    "cleansing_log": ["Timestamp", "Area", "Issue", "Action", "Record_Key"],
    "audit_log": ["Timestamp", "User", "Action", "Details"],
}


def get_database_url():
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
        if "SUPABASE_DB_URL" in st.secrets:
            return st.secrets["SUPABASE_DB_URL"]
    except Exception:
        pass
    return os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or ""

def db_enabled():
    return bool(get_database_url())


def db_setup_cache_key():
    return "db_setup_ready_v73"

def clear_db_setup_cache():
    st.session_state.pop(db_setup_cache_key(), None)


def db_table_cache_key(name):
    return f"db_table_cache_v74_{name}"

def clear_db_table_cache(name=None):
    if name:
        st.session_state.pop(db_table_cache_key(name), None)
    else:
        for key in list(st.session_state.keys()):
            if str(key).startswith("db_table_cache_v74_"):
                st.session_state.pop(key, None)



@st.cache_resource(show_spinner=False)
def get_db_engine():
    db_url = get_database_url()
    if not db_url:
        return None
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300)

def db_table_name(name):
    return f"sms_{name}"

def normalize_required_columns(name, df):
    if name in REQUIRED_FILES:
        for col in REQUIRED_FILES[name]:
            if col not in df.columns:
                if col == "Payroll_Status":
                    df[col] = "Calculated"
                elif col == "Locked":
                    df[col] = False
                elif col == "Status" and name == "leave_entries":
                    df[col] = "Approved"
                elif name == "users" and col in ["allow_admin", "allow_supervisor"]:
                    df[col] = True
                else:
                    df[col] = ""
        required = REQUIRED_FILES[name]
        extras = [c for c in df.columns if c not in required]
        df = df[required + extras]
    return df

def ensure_data_files_csv_only():
    for name, columns in REQUIRED_FILES.items():
        path = file_path(name)
        if not path.exists():
            pd.DataFrame(columns=columns).to_csv(path, index=False)

    users_path = file_path("users")
    try:
        users = pd.read_csv(users_path)
    except Exception:
        users = pd.DataFrame(columns=REQUIRED_FILES["users"])
    if users.empty:
        users = pd.DataFrame([
            {"email": "admin@wagewise.local", "name": "WageWise Admin", "role": "Admin", "password_hash": hash_password("admin123"), "active": True, "allow_admin": True, "allow_supervisor": True},
            {"email": "supervisor@wagewise.local", "name": "WageWise Supervisor", "role": "Supervisor", "password_hash": hash_password("supervisor123"), "active": True, "allow_admin": False, "allow_supervisor": True},
        ])
        users.to_csv(users_path, index=False)

    employees_path = file_path("employees")
    try:
        employees = pd.read_csv(employees_path)
    except Exception:
        employees = pd.DataFrame(columns=REQUIRED_FILES["employees"])
    if employees.empty:
        employees = pd.DataFrame([
            {"Emp_ID": "E_Gudiya", "Name": "Gudiya", "Level": "L1", "Monthly_Salary": 9200, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
            {"Emp_ID": "E_Asha", "Name": "Asha", "Level": "L1", "Monthly_Salary": 10000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
            {"Emp_ID": "E_Pooja", "Name": "Pooja", "Level": "L1", "Monthly_Salary": 8000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
            {"Emp_ID": "E_Kiran", "Name": "Kiran", "Level": "L1", "Monthly_Salary": 8000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
            {"Emp_ID": "E_Riya", "Name": "Riya", "Level": "L1", "Monthly_Salary": 4500, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
            {"Emp_ID": "E_Sunita", "Name": "Sunita", "Level": "L1", "Monthly_Salary": 8000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
            {"Emp_ID": "E_Faizan", "Name": "Faizan", "Level": "L2", "Monthly_Salary": 16000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@wagewise.local"},
        ])
        employees.to_csv(employees_path, index=False)

def read_table_csv(name):
    ensure_data_files_csv_only()
    try:
        df = pd.read_csv(file_path(name))
    except (pd.errors.EmptyDataError, FileNotFoundError):
        df = pd.DataFrame(columns=REQUIRED_FILES.get(name, []))
    return normalize_required_columns(name, df)

def write_table_csv(name, df, allow_empty_restore=False):
    df = normalize_required_columns(name, df)
    critical_tables = {"advance_cases", "advance_schedule", "leave_entries", "users", "employees", "payroll_items"}
    if name in critical_tables and not allow_empty_restore:
        try:
            existing = read_table_csv(name)
            if len(existing) > 0 and df.empty:
                backup_table(name, "before_csv_empty_write_guard")
                raise ValueError(f"Blocked unsafe empty local write for {name}. Existing rows: {len(existing)}.")
        except (pd.errors.EmptyDataError, FileNotFoundError):
            pass
    df.to_csv(file_path(name), index=False)

def check_db_table_exists(conn, name):
    table = db_table_name(name)
    exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = :table_name
        )
    """), {"table_name": table}).scalar()
    return bool(exists)

def check_db_table_columns(conn, name):
    table = db_table_name(name)
    existing = [
        row[0] for row in conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = :table_name
        """), {"table_name": table}).fetchall()
    ]
    required = REQUIRED_FILES[name]
    missing = [c for c in required if c not in existing]
    return existing, missing

def ensure_database_tables():
    """Verify Cloud Storage setup exists; cache success to reduce page slowness."""
    engine = get_db_engine()
    if engine is None:
        ensure_data_files_csv_only()
        return False

    if st.session_state.get(db_setup_cache_key()) is True:
        return True

    ensure_data_files_csv_only()
    try:
        missing_tables = []
        missing_columns = []
        with engine.begin() as conn:
            for name in REQUIRED_FILES:
                if not check_db_table_exists(conn, name):
                    missing_tables.append(db_table_name(name))
                    continue
                _, missing = check_db_table_columns(conn, name)
                if missing:
                    for col in missing:
                        try:
                            conn.execute(text(f'ALTER TABLE "{db_table_name(name)}" ADD COLUMN "{col}" TEXT'))
                        except Exception:
                            missing_columns.append(f"{db_table_name(name)}: {col}")
        if missing_tables or missing_columns:
            st.warning(
                "Cloud Storage setup is not ready. Using Local fallback. "
                "Run SUPABASE_SCHEMA_RUN_ONCE.sql in Cloud Storage SQL Editor. "
                f"Missing tables: {', '.join(missing_tables) if missing_tables else 'None'}. "
                f"Missing columns: {' | '.join(missing_columns) if missing_columns else 'None'}."
            )
            st.session_state[db_setup_cache_key()] = False
            return False

        st.session_state[db_setup_cache_key()] = True
        return True
    except Exception as e:
        st.warning(f"Database connection issue. Using Local fallback for this session. Details: {e}")
        st.session_state[db_setup_cache_key()] = False
        return False

def read_table_db(name):
    engine = get_db_engine()
    if engine is None:
        return read_table_csv(name)
    try:
        cache_key = db_table_cache_key(name)
        if cache_key in st.session_state:
            return st.session_state[cache_key].copy()

        # Fast path: no setup scan here. Schema health is handled only in System Admin → Storage Health.
        table = db_table_name(name)
        df = pd.read_sql_query(f'SELECT * FROM "{table}"', engine)
        df = normalize_required_columns(name, df)
        st.session_state[cache_key] = df.copy()
        return df.copy()
    except Exception as e:
        st.session_state["last_db_runtime_issue"] = f"Could not read {name} from Cloud Storage. Local fallback used."
        return read_table_csv(name)

def write_table_db(name, df, allow_empty_restore=False):
    engine = get_db_engine()
    if engine is None:
        write_table_csv(name, df)
        return
    df = normalize_required_columns(name, df)
    critical_tables = {"advance_cases", "advance_schedule", "leave_entries", "users", "employees", "payroll_items"}
    try:
        table = db_table_name(name)
        existing_count = 0
        if name in critical_tables:
            try:
                with engine.connect() as conn:
                    existing_count = int(conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)
            except Exception:
                existing_count = 0
            if existing_count > 0:
                backup_table(name, "before_write_guard")
            if existing_count > 0 and df.empty and not allow_empty_restore:
                raise ValueError(f"Blocked unsafe empty write for {name}. Existing rows: {existing_count}. Use Section Rollback or explicit recovery if clearing is intended.")

        expected_count = len(df)
        # V116.4: safely extend Cloud Storage table columns before writing.
        # This allows non-destructive additions like Date_of_Joining without forcing a table reset.
        with engine.begin() as conn:
            try:
                existing_cols = [r[0] for r in conn.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table_name
                """), {"table_name": table}).fetchall()]
                for col in df.columns:
                    if col not in existing_cols:
                        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT'))
            except Exception:
                pass

        with engine.begin() as conn:
            try:
                conn.execute(text("SET LOCAL statement_timeout = '60000'"))
            except Exception:
                pass
            conn.execute(text(f'DELETE FROM "{table}"'))
        if not df.empty:
            df.astype(str).to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=100)
        if name in critical_tables:
            with engine.connect() as conn:
                after_count = int(conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)
            if after_count != expected_count:
                raise ValueError(f"Write verification failed for {name}. Expected {expected_count} rows, found {after_count}.")
        st.session_state[db_table_cache_key(name)] = df.copy()
    except Exception as e:
        st.session_state["last_db_runtime_issue"] = f"Could not write {name} to Cloud Storage. Local fallback used. Details: {e}"
        # Do not silently overwrite local fallback when an unsafe DB write was blocked.
        if "Blocked unsafe empty write" in str(e):
            raise
        write_table_csv(name, df)
        clear_db_table_cache(name)

def db_connection_status_text():
    if not db_enabled():
        return "Local Local fallback"
    try:
        with get_db_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "Cloud Storage PostgreSQL connected"
    except Exception as e:
        return f"Cloud Storage connection failed: {e}"

def get_csv_row_counts():
    ensure_data_files_csv_only()
    rows = []
    for name in REQUIRED_FILES:
        try:
            rows.append({"Table": name, "CSV Rows": len(pd.read_csv(file_path(name)))})
        except Exception as e:
            rows.append({"Table": name, "CSV Rows": f"Error: {e}"})
    return pd.DataFrame(rows)

def get_db_row_counts():
    if not db_enabled():
        return pd.DataFrame([{"Table": name, "DB Rows": "No DATABASE_URL"} for name in REQUIRED_FILES])
    rows = []
    try:
        ensure_database_tables()
        with get_db_engine().begin() as conn:
            for name in REQUIRED_FILES:
                table = db_table_name(name)
                try:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                    rows.append({"Table": name, "DB Rows": int(count or 0)})
                except Exception as e:
                    rows.append({"Table": name, "DB Rows": f"Error: {e}"})
    except Exception as e:
        rows.append({"Table": "connection", "DB Rows": f"Error: {e}"})
    return pd.DataFrame(rows)

def get_setup_alignment_report():
    if not db_enabled():
        return pd.DataFrame([{"Table": name, "Schema Status": "No DATABASE_URL", "Missing Columns": "", "Extra Columns": ""} for name in REQUIRED_FILES])
    rows = []
    try:
        ensure_database_tables()
        with get_db_engine().begin() as conn:
            for name, required in REQUIRED_FILES.items():
                table = db_table_name(name)
                existing = [r[0] for r in conn.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = :table_name
                """), {"table_name": table}).fetchall()]
                missing = [c for c in required if c not in existing]
                extra = [c for c in existing if c not in required]
                rows.append({"Table": name, "Schema Status": "OK" if not missing else "Missing Columns", "Missing Columns": ", ".join(missing), "Extra Columns": ", ".join(extra)})
    except Exception as e:
        rows.append({"Table": "connection", "Schema Status": f"Error: {e}", "Missing Columns": "", "Extra Columns": ""})
    return pd.DataFrame(rows)


def reset_supabase_sms_tables():
    """Drop/recreate only SMS tables from the app.

    Use only during setup when Cloud Storage has old/bad setup or seed is blocked by old primary keys/indexes.
    """
    if not db_enabled():
        return "DATABASE_URL not configured."
    engine = get_db_engine()
    with engine.begin() as conn:
        try:
            conn.execute(text("SET LOCAL statement_timeout = '60000'"))
        except Exception:
            pass
        for name in REQUIRED_FILES:
            conn.execute(text(f'DROP TABLE IF EXISTS "{db_table_name(name)}" CASCADE'))
        for name, columns in REQUIRED_FILES.items():
            col_sql = ", ".join([f'"{c}" TEXT' for c in columns])
            conn.execute(text(f'CREATE TABLE "{db_table_name(name)}" ({col_sql})'))
    clear_db_setup_cache()
    clear_db_table_cache()
    return "Cloud Storage SMS tables reset successfully. Now click Load Cloud Data from Backup."


def seed_supabase_from_csv(overwrite=True):
    if not db_enabled():
        return "DATABASE_URL not configured."
    if not ensure_database_tables():
        return "Cloud Storage setup is not ready. Run SUPABASE_SCHEMA_RUN_ONCE.sql first, then retry seed."
    engine = get_db_engine()
    ensure_data_files_csv_only()
    with engine.begin() as conn:
        try:
            conn.execute(text("SET LOCAL statement_timeout = '60000'"))
        except Exception:
            pass
        for name in REQUIRED_FILES:
            table = db_table_name(name)
            if overwrite:
                conn.execute(text(f'DELETE FROM "{table}"'))
            df = read_table_csv(name)
            if not df.empty:
                df = normalize_required_columns(name, df).astype(str)
                try:
                    existing_cols = [r[0] for r in conn.execute(text("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = :table_name
                    """), {"table_name": table}).fetchall()]
                    for col in df.columns:
                        if col not in existing_cols:
                            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT'))
                except Exception:
                    pass
                df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=100)
    clear_db_table_cache()
    return "Cloud Storage seeded from CSV successfully."

def export_supabase_to_csv():
    if not db_enabled():
        return "DATABASE_URL not configured."
    ensure_database_tables()
    engine = get_db_engine()
    for name in REQUIRED_FILES:
        df = pd.read_sql_table(db_table_name(name), engine)
        write_table_csv(name, normalize_required_columns(name, df))
    clear_db_table_cache()
    return "Cloud Storage exported to CSV successfully."


def file_path(name):
    return DATA_DIR / f"{name}.csv"

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def ensure_data_files():
    # Performance rule: app startup must never perform Cloud Storage setup checks.
    # Cloud Storage is accessed only when a table is actually read/written.
    ensure_data_files_csv_only()

def read_table(name):
    if db_enabled():
        return read_table_db(name)
    return read_table_csv(name)

def write_table(name, df, allow_empty_restore=False):
    if db_enabled():
        write_table_db(name, df, allow_empty_restore=allow_empty_restore)
    else:
        write_table_csv(name, df, allow_empty_restore=allow_empty_restore)

def normalize_payroll_columns(df):
    """Ensure older CSV files get the new approval columns."""
    required = REQUIRED_FILES["payroll_items"]
    for col in required:
        if col not in df.columns:
            if col == "Payroll_Status":
                df[col] = "Calculated"
            elif col == "Locked":
                df[col] = False
            else:
                df[col] = ""
    return df[required] if set(required).issubset(set(df.columns)) else df

def is_month_locked(month_value):
    payroll = normalize_payroll_columns(read_table("payroll_items"))
    if payroll.empty:
        return False
    month_rows = payroll[payroll["Month"].astype(str) == str(month_value)]
    if month_rows.empty:
        return False
    return month_rows["Locked"].astype(str).str.lower().isin(["true", "1", "yes"]).any()

def set_month_status(month_value, status, approved_by="", approved_at="", locked=False):
    payroll = normalize_payroll_columns(read_table("payroll_items"))
    if payroll.empty:
        return
    mask = payroll["Month"].astype(str) == str(month_value)
    payroll.loc[mask, "Payroll_Status"] = status
    payroll.loc[mask, "Approved_By"] = approved_by
    payroll.loc[mask, "Approved_At"] = approved_at
    payroll.loc[mask, "Locked"] = locked
    write_table("payroll_items", payroll)

def payroll_excel_bytes(month_value):
    payroll = normalize_payroll_columns(read_table("payroll_items"))
    leave_log = read_table("leave_adjustment_log")
    schedule = read_table("advance_schedule")

    payroll_month = payroll[payroll["Month"].astype(str) == str(month_value)].copy()
    leave_month = leave_log[leave_log["Month"].astype(str) == str(month_value)].copy() if not leave_log.empty and "Month" in leave_log else leave_log.head(0)
    schedule_month = schedule[schedule["Deduction_Month"].astype(str) == str(month_value)].copy() if not schedule.empty and "Deduction_Month" in schedule else schedule.head(0)

    summary_month = clean_summary_rows(build_mobile_salary_summary(month_value))

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_month.to_excel(writer, index=False, sheet_name="Mobile_Summary")
        payroll_month.to_excel(writer, index=False, sheet_name="Payroll_Final")
        leave_month.to_excel(writer, index=False, sheet_name="Leave_Adjustment_Log")
        schedule_month.to_excel(writer, index=False, sheet_name="Advance_Schedule")
    output.seek(0)
    return output.getvalue()


def show_confirmation_area():
    """Display one clean blinking confirmation after button actions."""
    msg = st.session_state.pop("confirmation_message", None)
    celebrate = st.session_state.pop("celebrate_success", False)
    if msg:
        st.markdown(
            f"""
            <div class='ww-clean-confirmation'>
                <div class='ww-clean-confirmation-title'>Action completed</div>
                <div class='ww-clean-confirmation-text'>{msg}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if celebrate:
            st.balloons()

def set_confirmation(message, celebrate=True):
    st.session_state.confirmation_message = message
    st.session_state.celebrate_success = bool(celebrate)

def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default

def sync_advance_schedule_override(emp_id, month_value, final_deduction, updated_by):
    """
    Sync Employee Profile advance override back into advance_schedule.
    This makes Person-wise Payroll Exclusions / Deductions and Advance Updation speak to each other.
    """
    schedule = read_table("advance_schedule")
    cases = read_table("advance_cases")
    final_deduction = safe_float(final_deduction)

    # If there is no advance for this employee/month and deduction is 0, nothing needs to be written.
    if final_deduction == 0 and (schedule.empty or "Emp_ID" not in schedule.columns):
        return "No advance schedule found; deduction retained as ₹0."

    if schedule.empty:
        schedule = pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])

    mask = (
        (schedule["Emp_ID"].astype(str) == str(emp_id)) &
        (schedule["Deduction_Month"].astype(str) == str(month_value))
    ) if not schedule.empty else pd.Series([], dtype=bool)

    if mask.any():
        # Apply override to existing schedule rows for that employee/month.
        idxs = schedule[mask].index.tolist()
        first_idx = idxs[0]
        schedule.loc[first_idx, "Admin_Updated_Deduction"] = final_deduction
        schedule.loc[first_idx, "Final_Deduction"] = final_deduction
        schedule.loc[first_idx, "Status"] = "Open"
        schedule.loc[first_idx, "Updated_By"] = updated_by
        schedule.loc[first_idx, "Updated_At"] = datetime.now().isoformat(timespec="seconds")
        # If multiple schedule rows exist for same employee/month, zero out the extras to avoid double deduction.
        for extra_idx in idxs[1:]:
            schedule.loc[extra_idx, "Admin_Updated_Deduction"] = 0
            schedule.loc[extra_idx, "Final_Deduction"] = 0
            schedule.loc[extra_idx, "Updated_By"] = updated_by
            schedule.loc[extra_idx, "Updated_At"] = datetime.now().isoformat(timespec="seconds")
        write_table("advance_schedule", schedule)
        return "Advance schedule updated from Employee Profile."

    if final_deduction > 0:
        # If no schedule exists but admin sets a deduction, create a manual adjustment schedule row.
        adv_id = f"ADJ-{str(emp_id)}-{str(month_value).replace('-', '')}"
        schedule.loc[len(schedule)] = [
            adv_id, str(emp_id), str(month_value), final_deduction, final_deduction,
            final_deduction, "Open", updated_by, datetime.now().isoformat(timespec="seconds")
        ]
        write_table("advance_schedule", schedule)

        # Also create a matching advance case if not present, so reporting sees it.
        if cases.empty:
            cases = pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
        if "Advance_ID" not in cases.columns or adv_id not in cases["Advance_ID"].astype(str).tolist():
            cases.loc[len(cases)] = [
                adv_id, str(emp_id), str(date.today()), final_deduction, str(month_value),
                final_deduction, 0, "Open", "Created from Employee Profile adjustment",
                updated_by, datetime.now().isoformat(timespec="seconds")
            ]
            write_table("advance_cases", cases)
        return "Manual advance schedule created from Employee Profile."

    return "No advance schedule change needed."


def download_ack(label):
    set_confirmation(f"{label} prepared/download action triggered.")

def normalize_leave_type(value):
    raw = "" if pd.isna(value) else str(value).strip()
    aliases = {
        "full day": "Leave - Full Day",
        "full": "Leave - Full Day",
        "leave full day": "Leave - Full Day",
        "leave - full day": "Leave - Full Day",
        "half day": "Leave - Half Day",
        "half": "Leave - Half Day",
        "leave half day": "Leave - Half Day",
        "leave - half day": "Leave - Half Day",
        "uninformed": "Leave - Uninformed",
        "un-informed": "Leave - Uninformed",
        "leave uninformed": "Leave - Uninformed",
        "leave - uninformed": "Leave - Uninformed",
        "collaborative": "Leave - Collaborative",
        "collaborated": "Leave - Collaborative",
        "collab": "Leave - Collaborative",
        "leave collaborative": "Leave - Collaborative",
        "leave - collaborative": "Leave - Collaborative",
    }
    return aliases.get(raw.lower(), raw)


def canonical_text(value):
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())

def build_employee_alias_map():
    employees = read_table("employees")
    alias_map = {}
    if employees.empty:
        return alias_map
    for _, r in employees.iterrows():
        emp_id = str(r.get("Emp_ID", "")).strip()
        name = str(r.get("Name", "")).strip()
        if emp_id:
            alias_map[canonical_text(emp_id)] = emp_id
        if name:
            alias_map[canonical_text(name)] = emp_id
            alias_map[canonical_text("E_" + name)] = emp_id
            alias_map[canonical_text("E-" + name)] = emp_id
            alias_map[canonical_text("E " + name)] = emp_id
    return alias_map

def normalize_emp_id_value(value):
    raw = str(value).strip()
    alias_map = build_employee_alias_map()
    return alias_map.get(canonical_text(raw), raw)

def normalize_leave_entries_for_payroll(leave_entries):
    if leave_entries.empty:
        return leave_entries
    df = leave_entries.copy()
    if "Emp_ID" in df.columns:
        df["Emp_ID"] = df["Emp_ID"].apply(normalize_emp_id_value)
    if "Leave_Type" in df.columns:
        df["Leave_Type"] = df["Leave_Type"].apply(normalize_leave_type)
    if "Status" not in df.columns:
        df["Status"] = "Approved"
    df["Status"] = df["Status"].fillna("Approved").astype(str).str.strip()
    return df


def parse_app_date_series(series):
    """Robust date parser for app CSV dates.

    Priority:
    1. ISO saved format YYYY-MM-DD
    2. Indian upload format DD-MM-YYYY / DD/MM/YYYY
    3. Generic fallback

    This avoids the bug where saved ISO dates like 2026-04-11 were interpreted as 2026-11-04.
    """
    s = series.astype(str).str.strip()
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    # 1) ISO format first: YYYY-MM-DD or YYYY/MM/DD
    iso_mask = s.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", na=False)
    if iso_mask.any():
        parsed.loc[iso_mask] = pd.to_datetime(s[iso_mask], errors="coerce", yearfirst=True)

    # 2) Indian/day-first format: DD-MM-YYYY or DD/MM/YYYY
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(s[missing], errors="coerce", dayfirst=True)

    # 3) Generic fallback for any remaining.
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(s[missing], errors="coerce", dayfirst=False)

    return parsed

def parse_app_date_value(value):
    return parse_app_date_series(pd.Series([value])).iloc[0]


def build_leave_match_diagnostics(month_value):
    employees = read_table("employees")
    leaves = normalize_leave_entries_for_payroll(read_table("leave_entries"))
    if leaves.empty:
        return pd.DataFrame(columns=["Emp_ID", "Name", "Uploaded Leave Rows", "Counted Leave Units", "Rejected/Cancelled Rows"])
    try:
        yr, mon = parse_month_label(str(month_value))
    except Exception:
        return pd.DataFrame()
    month_start = pd.Timestamp(year=yr, month=mon, day=1)
    month_end = pd.Timestamp(year=yr, month=mon, day=calendar.monthrange(yr, mon)[1])
    leaves["Date_dt"] = parse_app_date_series(leaves["Date"])
    leaves = leaves[(leaves["Date_dt"] >= month_start) & (leaves["Date_dt"] <= month_end)]
    rows = []
    for _, emp in employees.iterrows():
        emp_id = str(emp["Emp_ID"])
        emp_leaves = leaves[leaves["Emp_ID"].astype(str) == emp_id].copy()
        rejected = emp_leaves["Status"].astype(str).str.lower().isin(["rejected", "cancelled", "canceled"]).sum() if not emp_leaves.empty else 0
        counted = 0.0
        if not emp_leaves.empty:
            valid = emp_leaves[~emp_leaves["Status"].astype(str).str.lower().isin(["rejected", "cancelled", "canceled"])]
            counted = sum(LEAVE_UNITS.get(str(x), 0) for x in valid["Leave_Type"])
        level = normalize_employee_level(emp.get("Level", "L1"))
        salary_value = safe_float(emp.get("Monthly_Salary", 0))
        days_in_month = calendar.monthrange(yr, mon)[1]
        daily_wage = salary_value if is_contractor_level(level) else (salary_value / days_in_month if days_in_month else 0)
        allowed = paid_leave_allowance_for_level(level)
        expected_lop = max(0, counted - allowed)
        rows.append({
            "Emp_ID": emp_id,
            "Name": emp["Name"],
            "Uploaded Leave Rows": int(len(emp_leaves)),
            "Counted Leave Units": counted,
            "Allowed Leaves": allowed,
            "Expected LOP": expected_lop,
            "Expected Leave Deduction": round(expected_lop * daily_wage, 2),
            "Rejected/Cancelled Rows": int(rejected),
        })
    diag_df = pd.DataFrame(rows)
    if not diag_df.empty:
        total_row = {
            "Emp_ID": "TOTAL",
            "Name": "TOTAL",
            "Uploaded Leave Rows": int(pd.to_numeric(diag_df["Uploaded Leave Rows"], errors="coerce").fillna(0).sum()),
            "Counted Leave Units": float(pd.to_numeric(diag_df["Counted Leave Units"], errors="coerce").fillna(0).sum()),
            "Allowed Leaves": float(pd.to_numeric(diag_df["Allowed Leaves"], errors="coerce").fillna(0).sum()) if "Allowed Leaves" in diag_df.columns else "",
            "Expected LOP": float(pd.to_numeric(diag_df["Expected LOP"], errors="coerce").fillna(0).sum()) if "Expected LOP" in diag_df.columns else "",
            "Expected Leave Deduction": float(pd.to_numeric(diag_df["Expected Leave Deduction"], errors="coerce").fillna(0).sum()) if "Expected Leave Deduction" in diag_df.columns else "",
            "Rejected/Cancelled Rows": int(pd.to_numeric(diag_df["Rejected/Cancelled Rows"], errors="coerce").fillna(0).sum()),
        }
        diag_df = pd.concat([diag_df, pd.DataFrame([total_row])], ignore_index=True)
    return diag_df


def get_month_bounds_from_label(month_value):
    yr, mon = parse_month_label(str(month_value))
    start = pd.Timestamp(year=yr, month=mon, day=1)
    end = pd.Timestamp(year=yr, month=mon, day=calendar.monthrange(yr, mon)[1])
    return yr, mon, start, end


def first_lock_allowed_date(year, month):
    """Payroll can be approved/locked only from the 1st after the payroll month ends."""
    last_day = calendar.monthrange(int(year), int(month))[1]
    month_end = date(int(year), int(month), last_day)
    return month_end + timedelta(days=1)

def can_lock_payroll_month(year, month):
    return date.today() >= first_lock_allowed_date(year, month)

def payroll_lock_rule_message(year, month):
    allowed_date = first_lock_allowed_date(int(year), int(month))
    return f"Payroll for {month_label(int(year), int(month))} can be approved/locked only from {allowed_date}, after final recalculation is done."



def safe_numeric_series(series):
    try:
        return pd.to_numeric(series, errors="coerce").fillna(0)
    except Exception:
        return pd.Series(dtype=float)



def schedule_month_tuple_value(value):
    try:
        sy, sm = parse_month_label(str(value))
        return (int(sy), int(sm))
    except Exception:
        return None

def advance_status_is_active(value):
    return str(value).strip().lower() not in ["rejected", "cancelled", "canceled", "void"]


def build_mobile_salary_summary(month_value):
    """Build user-facing Salary Summary.

    Advance guardrails:
    - Total Advance = total advance amount taken by employee up to payroll recalculation timestamp.
    - Deduction for the Month = selected month's repayment schedule only.
    - Future advances do not affect older payroll months.
    - Deductions/balance are capped so advance values cannot become negative or illogical.
    """
    payroll = normalize_payroll_columns(read_table("payroll_items"))
    advances = read_table("advance_cases")
    schedule = read_table("advance_schedule")

    if payroll.empty:
        return pd.DataFrame()

    month_df = payroll[payroll["Month"].astype(str) == str(month_value)].copy()
    if month_df.empty:
        return pd.DataFrame()

    yr, mon, month_start, month_end = get_month_bounds_from_label(month_value)

    if not advances.empty:
        advances = advances.copy()
        advances["Advance_Date_dt"] = parse_app_date_series(advances["Advance_Date"])

    rows = []
    for _, p in month_df.iterrows():
        emp_id = str(p["Emp_ID"])
        name = p.get("Name", "")
        level = str(p.get("Level", "L1"))
        total_pay = safe_float(p.get("Monthly_Salary", 0))
        daily_wage = safe_float(p.get("Daily_Wage", 0))

        recalc_cutoff = pd.to_datetime(p.get("Last_Recalculated_At", ""), errors="coerce")
        if pd.isna(recalc_cutoff):
            recalc_cutoff = month_end

        emp_adv = advances[
            (advances["Emp_ID"].astype(str) == emp_id) &
            (advances.get("Status", "Open").astype(str).apply(advance_status_is_active))
        ].copy() if (not advances.empty and "Emp_ID" in advances.columns) else pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
        emp_sched = schedule[schedule["Emp_ID"].astype(str) == emp_id].copy() if (not schedule.empty and "Emp_ID" in schedule.columns) else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])

        advance_prior_month = 0.0
        advance_current_month = 0.0
        total_advance = 0.0
        deduction_for_month = 0.0
        total_deducted_before_current = 0.0
        total_deducted_upto_current = 0.0
        eligible_advance_ids = set()

        if not emp_adv.empty and "Advance_Date_dt" in emp_adv.columns:
            emp_adv_until_recalc = emp_adv[
                emp_adv["Advance_Date_dt"].notna() &
                (emp_adv["Advance_Date_dt"] <= recalc_cutoff)
            ].copy()

            if not emp_adv_until_recalc.empty:
                total_advance = safe_numeric_series(emp_adv_until_recalc["Amount_Given"]).sum() if "Amount_Given" in emp_adv_until_recalc.columns else 0.0
                prior_cases = emp_adv_until_recalc[emp_adv_until_recalc["Advance_Date_dt"] < month_start]
                current_cases = emp_adv_until_recalc[
                    (emp_adv_until_recalc["Advance_Date_dt"] >= month_start) &
                    (emp_adv_until_recalc["Advance_Date_dt"] <= month_end)
                ]
                advance_prior_month = safe_numeric_series(prior_cases["Amount_Given"]).sum() if not prior_cases.empty and "Amount_Given" in prior_cases.columns else 0.0
                advance_current_month = safe_numeric_series(current_cases["Amount_Given"]).sum() if not current_cases.empty and "Amount_Given" in current_cases.columns else 0.0
                eligible_advance_ids = set(emp_adv_until_recalc["Advance_ID"].astype(str)) if "Advance_ID" in emp_adv_until_recalc.columns else set()

        if not emp_sched.empty:
            if eligible_advance_ids and "Advance_ID" in emp_sched.columns:
                emp_sched = emp_sched[emp_sched["Advance_ID"].astype(str).isin(eligible_advance_ids)].copy()

            for _, srow in emp_sched.iterrows():
                mt = schedule_month_tuple_value(srow.get("Deduction_Month", ""))
                if mt is None:
                    continue
                amt = max(0.0, safe_float(srow.get("Final_Deduction", 0)))

                if mt < (yr, mon):
                    total_deducted_before_current += amt

                if mt == (yr, mon):
                    deduction_for_month += amt

        if total_advance == 0:
            total_advance = safe_float(p.get("Advance_Prior_Month", 0)) + safe_float(p.get("Advance_Given_This_Month", 0))
        if advance_prior_month == 0:
            advance_prior_month = safe_float(p.get("Advance_Prior_Month", 0))
        if advance_current_month == 0:
            advance_current_month = safe_float(p.get("Advance_Given_This_Month", 0))
        if deduction_for_month == 0:
            deduction_for_month = safe_float(p.get("Advance_Deduction", 0))

        # Guardrails: monthly deduction cannot exceed remaining balance, and advance left cannot go negative.
        balance_before_month = max(0.0, total_advance - total_deducted_before_current)
        deduction_for_month = min(max(0.0, deduction_for_month), balance_before_month)
        total_deducted_upto_current = min(total_advance, total_deducted_before_current + deduction_for_month)
        advance_left = max(0.0, total_advance - total_deducted_upto_current)

        if total_advance == 0:
            advance_left = safe_float(p.get("Advance_Balance_Close", 0))

        leaves_taken = safe_float(p.get("Leave_Units", 0))
        base_leave_allowed = safe_float(p.get("Paid_Leave_Allowed", paid_leave_allowance_for_level(level)))
        report_lop = max(0.0, leaves_taken - base_leave_allowed)
        leave_deduction_cost = round(report_lop * daily_wage, 2)

        net_salary = safe_float(p.get("Final_Salary_With_Special", 0))

        rows.append({
            "Name": name,
            "Total Pay": round(total_pay, 2),
            "Daily Wage": round(daily_wage, 2),
            "Advance Prior Month": round(advance_prior_month, 2),
            "Advance Current Month": round(advance_current_month, 2),
            "Total Advance": round(total_advance, 2),
            "Total Leaves Taken": leaves_taken,
            "Deduction for the Month": round(deduction_for_month, 2),
            "Leave Deduction Cost on extra leaves": leave_deduction_cost,
            "Net Salary to be Paid": round(net_salary, 2),
            "Advance Left": round(advance_left, 2),
        })

    return pd.DataFrame(rows)

def add_audit(user, action, details):
    # Performance rule: do not let audit logging block UI actions such as login/navigation.
    lightweight_actions = {
        "SINGLE_LOGIN", "ROLE_SELECTED", "LOGOUT", "LOGOUT_FROM_ROLE_SELECTION",
        "PAGE_NAVIGATION", "DOWNLOAD"
    }
    if str(action) in lightweight_actions:
        return

    try:
        df = read_table("audit_log")
        df.loc[len(df)] = [datetime.now().isoformat(timespec="seconds"), user, action, details]
        write_table("audit_log", df)
    except Exception:
        # Audit should never break or slow the user's core workflow.
        pass

def add_clean_log(area, issue, action, record_key):
    df = read_table("cleansing_log")
    df.loc[len(df)] = [datetime.now().isoformat(timespec="seconds"), area, issue, action, record_key]
    write_table("cleansing_log", df)

def apply_theme():
    st.markdown(f"""
    <style>
    :root {{
        --sms-primary: #0B4F71;
        --sms-primary-dark: #083A54;
        --sms-accent: #1E88A8;
        --sms-bg: #F4F8FB;
        --sms-card: #FFFFFF;
        --sms-text: #172033;
        --sms-muted: #52616F;
        --sms-border: #D8E3EA;
    }}

    html, body, .stApp {{
        background: var(--sms-bg) !important;
        color: var(--sms-text) !important;
    }}

    .block-container {{
        padding-top: 1.6rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1180px !important;
    }}

    [data-testid="stSidebar"], section[data-testid="stSidebar"] {{
        display: none !important;
        visibility: hidden !important;
    }}

    [data-testid="collapsedControl"], button[kind="header"] {{
        display: none !important;
    }}

    h1, h2, h3, h4, h5, h6, p, div {{
        line-height: 1.35 !important;
        overflow: visible !important;
    }}

    .sms-title {{
        color: var(--sms-primary);
        font-weight: 900;
        font-size: 30px;
        line-height: 1.25 !important;
        margin: 6px 0 4px 0;
        padding-top: 4px;
    }}

    .sms-subtitle {{
        color: var(--sms-muted);
        font-size: 14px;
        margin-bottom: 18px;
        line-height: 1.45 !important;
    }}

    .stButton > button {{
        background-color: var(--sms-primary) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--sms-primary) !important;
        border-radius: 12px !important;
        min-height: 46px !important;
        font-weight: 800 !important;
        font-size: 15px !important;
        padding: 0.65rem 1rem !important;
        box-shadow: 0 2px 7px rgba(11,79,113,0.18) !important;
    }}

    .stButton > button:hover {{
        background-color: var(--sms-primary-dark) !important;
        color: #FFFFFF !important;
        border-color: var(--sms-primary-dark) !important;
    }}

    .stButton > button:focus {{
        outline: 3px solid rgba(30,136,168,0.28) !important;
        color: #FFFFFF !important;
    }}

    .stTextInput input, .stNumberInput input, .stDateInput input, textarea, .stSelectbox div[data-baseweb="select"] {{
        border-radius: 10px !important;
    }}

    label, .stMarkdown, .stCaptionContainer {{
        color: var(--sms-text) !important;
    }}

    .login-shell {{
        max-width: 620px;
        margin: 3.5vh auto 20px auto;
        background: var(--sms-card);
        border: 1px solid var(--sms-border);
        border-radius: 26px;
        padding: 30px 28px 26px 28px;
        box-shadow: 0 12px 28px rgba(11,79,113,0.12);
    }}

    .login-logo {{
        width: 76px;
        height: 76px;
        border-radius: 22px;
        background: linear-gradient(135deg, var(--sms-primary), var(--sms-accent));
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 36px;
        font-weight: 900;
        margin: 0 auto 14px auto;
        line-height: 1 !important;
    }}

    .login-title {{
        text-align: center;
        color: var(--sms-primary);
        font-size: 31px;
        line-height: 1.25 !important;
        font-weight: 900;
        margin: 0 0 8px 0;
        padding-top: 2px;
        letter-spacing: -0.2px;
    }}

    .login-subtitle {{
        text-align: center;
        color: var(--sms-muted);
        font-size: 14px;
        line-height: 1.45 !important;
        margin-bottom: 0;
    }}

    .top-nav {{
        background: var(--sms-card);
        border: 1px solid var(--sms-border);
        border-radius: 18px;
        padding: 14px 16px;
        margin-bottom: 18px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.05);
        color: var(--sms-text);
    }}

    .role-card, .quick-card {{
        background: var(--sms-card);
        border: 1px solid var(--sms-border);
        border-radius: 20px;
        padding: 18px;
        box-shadow: 0 1px 7px rgba(0,0,0,0.06);
        margin-bottom: 14px;
        min-height: 120px;
    }}

    .role-title, .quick-title {{
        color: var(--sms-primary);
        font-size: 21px;
        line-height: 1.25 !important;
        font-weight: 900;
        margin-bottom: 8px;
    }}

    .role-help, .quick-help {{
        color: var(--sms-muted);
        font-size: 14px;
        line-height: 1.5 !important;
    }}

    .nav-label {{
        color: var(--sms-primary);
        font-weight: 900;
        font-size: 17px;
        line-height: 1.35 !important;
        margin: 8px 0 10px 0;
    }}

    div[data-testid="stMetric"] {{
        background: var(--sms-card);
        border: 1px solid var(--sms-border);
        padding: 16px;
        border-radius: 16px;
        box-shadow: 0 1px 5px rgba(0,0,0,0.05);
    }}

    @media (max-width: 768px) {{
        .block-container {{
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1rem !important;
        }}

        .login-shell {{
            margin-top: 1vh;
            padding: 24px 18px 22px 18px;
            border-radius: 22px;
        }}

        .login-logo {{
            width: 64px;
            height: 64px;
            font-size: 30px;
            border-radius: 18px;
            margin-bottom: 12px;
        }}

        .login-title {{
            font-size: 24px;
            line-height: 1.3 !important;
        }}

        .login-subtitle {{
            font-size: 13px;
        }}

        .sms-title {{
            font-size: 24px;
            line-height: 1.3 !important;
        }}

        .role-card, .quick-card {{
            padding: 15px;
            min-height: auto;
        }}

        .role-title, .quick-title {{
            font-size: 18px;
        }}

        .stButton > button {{
            width: 100% !important;
            min-height: 48px !important;
            font-size: 15px !important;
        }}

        div[data-testid="column"] {{
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }}

        .top-nav {{
            padding: 12px;
            font-size: 13px;
        }}
    }}

    /* V20 mobile/card alignment refinements */
    .role-card, .quick-card {{
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
    }}

    .top-nav b {{
        color: var(--sms-primary);
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        flex-wrap: wrap;
    }}

    .stTabs [data-baseweb="tab"] {{
        border-radius: 10px;
        padding: 8px 12px;
    }}

    @media (max-width: 768px) {{
        .role-card, .quick-card {{
            margin-bottom: 8px;
            min-height: auto !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-size: 13px;
            padding: 6px 8px;
        }}
    }}


    /* V28 mobile salary summary */
    .summary-card-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin: 12px 0 18px 0;
    }}

    .summary-card {{
        background: #FFFFFF;
        border: 1px solid var(--sms-border);
        border-radius: 18px;
        padding: 14px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    }}

    .summary-card-label {{
        color: var(--sms-muted);
        font-size: 12px;
        line-height: 1.3 !important;
        margin-bottom: 6px;
    }}

    .summary-card-value {{
        color: var(--sms-primary);
        font-weight: 900;
        font-size: 20px;
        line-height: 1.25 !important;
    }}

    .salary-table-wrap {{
        width: 100%;
        overflow: auto;
        max-height: 62vh;
        border: 1px solid var(--sms-border);
        border-radius: 18px;
        background: #FFFFFF;
        box-shadow: 0 1px 7px rgba(0,0,0,0.06);
        margin-top: 8px;
        margin-bottom: 8px;
    }}

    .salary-table {{
        border-collapse: separate;
        border-spacing: 0;
        width: max-content;
        min-width: 100%;
        font-size: 13px;
    }}

    .salary-table th {{
        position: sticky;
        top: 0;
        background: #0B4F71;
        color: #FFFFFF;
        z-index: 2;
        padding: 10px 12px;
        text-align: right;
        white-space: nowrap;
        border-bottom: 1px solid #083A54;
    }}

    .salary-table td {{
        padding: 10px 12px;
        border-bottom: 1px solid #E6EEF3;
        text-align: right;
        white-space: nowrap;
        color: #172033;
    }}

    .salary-table th:first-child,
    .salary-table td:first-child {{
        position: sticky;
        left: 0;
        z-index: 3;
        text-align: left;
        min-width: 132px;
        max-width: 180px;
        box-shadow: 3px 0 6px rgba(0,0,0,0.06);
    }}

    .salary-table th:first-child {{
        background: #083A54;
        color: #FFFFFF;
    }}

    .salary-table td:first-child {{
        background: #FFFFFF;
        color: #0B4F71;
        font-weight: 800;
    }}

    .salary-table tr:nth-child(even) td {{
        background: #F8FBFD;
    }}

    .salary-table tr:nth-child(even) td:first-child {{
        background: #F8FBFD;
    }}

    .salary-helper {{
        color: var(--sms-muted);
        font-size: 12px;
        margin-top: 6px;
        margin-bottom: 6px;
    }}

    @media (max-width: 768px) {{
        .summary-card-grid {{
            grid-template-columns: 1fr;
            gap: 8px;
        }}
        .summary-card {{
            padding: 12px;
            border-radius: 14px;
        }}
        .summary-card-value {{
            font-size: 18px;
        }}
        .salary-table-wrap {{
            max-height: 58vh !important;
            margin-bottom: 4px !important;
        }}
        .salary-table {{
            font-size: 12px;
        }}
        .salary-table th, .salary-table td {{
            padding: 7px 8px;
        }}
        .salary-table th:first-child,
        .salary-table td:first-child {{
            min-width: 118px;
            max-width: 150px;
        }}
    }}


    /* V29 final phone + laptop optimisation */
    .responsive-section {{
        background: #FFFFFF;
        border: 1px solid var(--sms-border);
        border-radius: 18px;
        padding: 14px 16px;
        margin: 10px 0 14px 0;
        box-shadow: 0 1px 6px rgba(0,0,0,0.05);
    }}

    .stDataFrame, [data-testid="stDataFrame"] {{
        border-radius: 14px !important;
        overflow: hidden !important;
    }}

    [data-testid="stHorizontalBlock"] {{
        gap: 0.75rem !important;
    }}

    .stSelectbox, .stTextInput, .stNumberInput, .stDateInput, .stTextArea, .stFileUploader {{
        margin-bottom: 0.35rem !important;
    }}

    .stDownloadButton > button {{
        background-color: #176B45 !important;
        border-color: #176B45 !important;
        color: #FFFFFF !important;
    }}

    .stDownloadButton > button:hover {{
        background-color: #0F5132 !important;
        border-color: #0F5132 !important;
        color: #FFFFFF !important;
    }}

    div[data-testid="stExpander"] {{
        border: 1px solid var(--sms-border) !important;
        border-radius: 14px !important;
        background: #FFFFFF !important;
    }}

    .nav-label {{
        margin-top: 4px !important;
    }}

    /* Laptop layout: keep page centered and clean */
    @media (min-width: 1100px) {{
        .block-container {{
            max-width: 1180px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }}

        .login-shell {{
            max-width: 620px !important;
        }}
    }}

    /* Tablet layout */
    @media (min-width: 769px) and (max-width: 1099px) {{
        .block-container {{
            max-width: 960px !important;
            padding-left: 1.4rem !important;
            padding-right: 1.4rem !important;
        }}

        .login-shell {{
            max-width: 600px !important;
        }}
    }}

    /* Phone layout */
    @media (max-width: 768px) {{
        .block-container {{
            padding: 0.85rem 0.65rem 2rem 0.65rem !important;
            max-width: 100% !important;
        }}

        [data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
            gap: 0.45rem !important;
        }}

        div[data-testid="column"] {{
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }}

        .top-nav {{
            font-size: 12.5px !important;
            padding: 10px 12px !important;
            margin-bottom: 12px !important;
        }}

        .sms-title {{
            font-size: 22px !important;
            margin-top: 2px !important;
        }}

        .sms-subtitle {{
            font-size: 12.5px !important;
            margin-bottom: 10px !important;
        }}

        .login-shell {{
            margin: 0.5vh 0 12px 0 !important;
            padding: 20px 14px 18px 14px !important;
            border-radius: 18px !important;
        }}

        .login-title {{
            font-size: 22px !important;
        }}

        .login-subtitle {{
            font-size: 12.5px !important;
        }}

        .role-card, .quick-card, .summary-card, .responsive-section {{
            border-radius: 14px !important;
            padding: 12px !important;
            margin-bottom: 8px !important;
        }}

        .role-title, .quick-title {{
            font-size: 17px !important;
        }}

        .role-help, .quick-help {{
            font-size: 12.5px !important;
        }}

        .stButton > button,
        .stDownloadButton > button,
        .stFormSubmitButton > button {{
            min-height: 48px !important;
            width: 100% !important;
            font-size: 14px !important;
            padding: 0.65rem 0.8rem !important;
            white-space: normal !important;
        }}

        input, textarea {{
            font-size: 16px !important; /* avoids mobile browser zoom */
        }}

        .stTabs [data-baseweb="tab-list"] {{
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
            gap: 6px !important;
        }}

        .stTabs [data-baseweb="tab"] {{
            min-width: max-content !important;
            font-size: 12.5px !important;
        }}

        [data-testid="stMetric"] {{
            padding: 12px !important;
        }}

        [data-testid="stMetricValue"] {{
            font-size: 18px !important;
        }}

        [data-testid="stDataFrame"] {{
            max-width: 100% !important;
            overflow-x: auto !important;
        }}
    }}


    /* V44 demo-ready compact mobile reports */
    .salary-table-wrap {{
        max-height: 54vh !important;
        min-height: 0 !important;
        height: auto !important;
        overflow: auto !important;
        margin-top: 6px !important;
        margin-bottom: 6px !important;
    }}

    .salary-table th,
    .salary-table td {{
        padding-top: 6px !important;
        padding-bottom: 6px !important;
        line-height: 1.2 !important;
    }}

    .salary-helper {{
        margin: 4px 0 4px 0 !important;
        line-height: 1.25 !important;
    }}

    div[data-testid="stVerticalBlock"] {{
        gap: 0.45rem !important;
    }}

    @media (max-width: 768px) {{
        .salary-table-wrap {{
            max-height: 50vh !important;
            margin-top: 4px !important;
            margin-bottom: 4px !important;
        }}

        .salary-table th,
        .salary-table td {{
            padding: 5px 7px !important;
            font-size: 11.5px !important;
        }}

        .summary-card-grid {{
            gap: 6px !important;
            margin: 6px 0 8px 0 !important;
        }}

        .summary-card {{
            padding: 9px 10px !important;
            margin-bottom: 4px !important;
        }}

        .summary-card-value {{
            font-size: 16px !important;
        }}

        .stMarkdown, .stCaptionContainer {{
            margin-bottom: 0.2rem !important;
        }}
    }}


    /* V52 header visibility fix */
    .block-container {{
        padding-top: 3.2rem !important;
    }}

    .sms-title {{
        margin-top: 18px !important;
        padding-top: 14px !important;
        line-height: 1.35 !important;
        min-height: 46px !important;
        overflow: visible !important;
    }}

    .sms-subtitle {{
        margin-top: 2px !important;
        margin-bottom: 16px !important;
        line-height: 1.45 !important;
        overflow: visible !important;
    }}

    @media (max-width: 768px) {{
        .block-container {{
            padding-top: 3.6rem !important;
        }}

        .sms-title {{
            margin-top: 20px !important;
            padding-top: 16px !important;
            font-size: 22px !important;
            line-height: 1.4 !important;
            min-height: 44px !important;
        }}

        .sms-subtitle {{
            font-size: 12.5px !important;
            line-height: 1.45 !important;
            margin-bottom: 12px !important;
        }}
    }}


    /* V62 UX fixes: form clarity + mobile dark-theme button safety only */
    div[data-testid="stForm"] {{
        border: 1.5px solid rgba(11, 79, 113, 0.22) !important;
        border-radius: 18px !important;
        background: #FFFFFF !important;
        padding: 14px 14px 10px 14px !important;
        box-shadow: 0 1px 7px rgba(11,79,113,0.06) !important;
    }}

    .special-impact-heading {{
        background: #EAF5FA;
        border: 1px solid #CFE4EE;
        border-radius: 16px;
        padding: 12px 14px;
        margin: 12px 0 8px 0;
        color: #083A54;
        font-weight: 900;
    }}

    .recalc-action-heading {{
        background: #F7FBFD;
        border-left: 5px solid #0B4F71;
        border-radius: 12px;
        padding: 10px 12px;
        margin: 10px 0 10px 0;
        color: #083A54;
        font-weight: 800;
    }}

    @media (max-width: 768px) and (prefers-color-scheme: dark) {{
        /* Phone dark theme only: protect login/action buttons without changing laptop/light-theme behavior */
        .stFormSubmitButton > button,
        .stButton > button,
        .stDownloadButton > button {{
            background-color: #0B4F71 !important;
            border-color: #0B4F71 !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }}

        .stFormSubmitButton > button *,
        .stButton > button *,
        .stDownloadButton > button * {{
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }}

        div[data-testid="stForm"],
        .login-shell,
        .role-card,
        .quick-card,
        .summary-card,
        .salary-table-wrap {{
            background: #FFFFFF !important;
            color: #172033 !important;
        }}
    }}


    /* V73 Storage Health UX polish */
    .db-health-shell {{
        border: 1px solid #D8E3EA;
        border-radius: 18px;
        padding: 14px 16px;
        background: #FFFFFF;
        box-shadow: 0 2px 10px rgba(11,79,113,0.06);
        margin-bottom: 12px;
    }}
    .db-health-title {{
        font-weight: 900;
        font-size: 18px;
        color: #083A54;
        margin-bottom: 8px;
    }}
    .db-status-pill {{
        display: inline-block;
        padding: 7px 11px;
        border-radius: 999px;
        font-weight: 800;
        margin-bottom: 8px;
    }}
    .db-ok {{ background: #EAF7EF; color: #1F7A4D; border: 1px solid #BFE6CC; }}
    .db-warn {{ background: #FFF8E8; color: #B7791F; border: 1px solid #F3D38B; }}
    .db-danger {{ background: #FFF1F1; color: #B42318; border: 1px solid #F2B8B5; }}
    .db-health-help {{
        font-size: 13px;
        color: #52616F;
        margin-top: 4px;
    }}


    /* V85 micro polish pass */
    .ww-next-step {{
        border-left: 5px solid #0E9384;
        background: linear-gradient(90deg, #ECFDF7, #FFFFFF);
        border-radius: 14px;
        padding: 12px 14px;
        margin: 10px 0 14px 0;
        color: #172033;
        box-shadow: 0 2px 8px rgba(14,147,132,0.08);
    }}
    .nav-label {{
        margin-top: 10px !important;
        margin-bottom: 8px !important;
        font-size: 18px !important;
        color: #083A54 !important;
        font-weight: 800 !important;
    }}
    .ww-nav-group-title {{
        font-size: 16px;
        font-weight: 800;
        color: #0B4F71;
        margin-bottom: 12px;
        line-height: 1.2;
    }}
    .ww-helper-card {{
        background: linear-gradient(135deg, #0B4F71, #0E9384);
        color: white;
        border-radius: 18px;
        padding: 16px 16px;
        margin-top: 12px;
        box-shadow: 0 6px 18px rgba(11,79,113,0.18);
    }}
    .ww-helper-title {{
        font-size: 15px;
        font-weight: 800;
        margin-bottom: 6px;
    }}
    .ww-helper-text {{
        font-size: 14px;
        line-height: 1.45;
        opacity: 0.98;
    }}
    .top-nav {{
        background: #FFFFFF;
        border: 1px solid #DCE8EF;
        border-radius: 16px;
        padding: 12px 16px;
        margin-bottom: 12px;
        box-shadow: 0 3px 10px rgba(11,79,113,0.05);
    }}
    /* Streamlit bordered containers used for nav groups */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 18px !important;
        border: 1px solid #DCE8EF !important;
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FBFD 100%) !important;
        box-shadow: 0 4px 14px rgba(8,58,84,0.05) !important;
        padding: 6px 6px 2px 6px !important;
        margin-bottom: 14px !important;
    }}
    /* Button polish */
    div[data-testid="stButton"] > button {{
        border-radius: 14px !important;
        min-height: 48px !important;
        font-weight: 800 !important;
        border: 1px solid #D7E6EF !important;
        color: #10324A !important;
        background: #FFFFFF !important;
        box-shadow: 0 1px 4px rgba(11,79,113,0.03);
        text-align: center !important;
        justify-content: center !important;
        letter-spacing: 0.1px;
        padding-top: 0.3rem !important;
        padding-bottom: 0.3rem !important;
        margin-bottom: 8px !important;
    }}
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {{
        background: linear-gradient(135deg, #0B4F71, #0E9384) !important;
        border: 0 !important;
        color: #FFFFFF !important;
    }}
    div[data-testid="stMetric"] {{
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 10px 12px;
        box-shadow: 0 1px 7px rgba(11,79,113,0.05);
    }}
    div[data-testid="stInfo"], div[data-testid="stSuccess"], div[data-testid="stWarning"] {{
        border-radius: 14px !important;
    }}
    .block-container {{
        padding-top: 1.05rem !important;
        padding-bottom: 1rem !important;
        max-width: 1240px !important;
    }}
    @media (min-width: 769px) {{
        /* Nudge right-side large box to align visually with 3 left boxes */
        div[data-testid="column"]:nth-of-type(2) div[data-testid="stVerticalBlockBorderWrapper"] {{
            min-height: 392px;
        }}
    }}
    @media (max-width: 768px) {{
        .block-container {{
            padding-top: 0.8rem !important;
            padding-left: 0.7rem !important;
            padding-right: 0.7rem !important;
        }}
        div[data-testid="column"] {{
            width: 100% !important;
            flex: 1 1 100% !important;
        }}
        div[data-testid="stButton"] > button {{
            width: 100% !important;
            margin-bottom: 7px !important;
            min-height: 50px !important;
        }}
        .top-nav {{
            padding: 10px 12px;
        }}
    }}

    
    /* V95 login polish */
    .login-hero {{
        max-width: 820px;
        margin: 18px auto 18px auto;
        padding: 26px 24px;
        border-radius: 24px;
        background: radial-gradient(circle at top left, #E6FFF7 0%, #F7FBFD 40%, #FFFFFF 100%);
        border: 1px solid #D7E6EF;
        box-shadow: 0 12px 32px rgba(11,79,113,0.10);
        text-align: center;
    }}
    .login-badge {{
        display: inline-block;
        background: linear-gradient(135deg, #0B4F71, #0E9384);
        color: #FFFFFF;
        font-weight: 900;
        padding: 8px 18px;
        border-radius: 999px;
        margin-bottom: 12px;
        letter-spacing: 0.2px;
    }}
    .login-main-title {{
        font-size: 30px;
        line-height: 1.15;
        color: #083A54;
        font-weight: 900;
        margin-bottom: 8px;
    }}
    .login-main-subtitle {{
        font-size: 15px;
        color: #52616F;
        margin-bottom: 16px;
    }}
    .login-feature-row {{
        display: flex;
        justify-content: center;
        gap: 12px;
        flex-wrap: wrap;
        color: #0B4F71;
        font-weight: 800;
        font-size: 13px;
    }}
    .login-feature-row div {{
        background: #FFFFFF;
        border: 1px solid #DCE8EF;
        border-radius: 999px;
        padding: 7px 12px;
    }}
    .login-card-title {{
        font-weight: 900;
        color: #083A54;
        font-size: 18px;
        text-align: center;
        margin: 6px 0 10px 0;
    }}
    .login-help {{
        text-align: center;
        color: #6B7280;
        font-size: 13px;
        margin-top: 8px;
    }}
    @media (max-width: 768px) {{
        .login-hero {{
            margin: 8px auto 14px auto;
            padding: 20px 14px;
            border-radius: 20px;
        }}
        .login-main-title {{
            font-size: 24px;
        }}
        .login-feature-row {{
            gap: 8px;
        }}
    }}

    
    /* V99 phone-first polish */
    @media (max-width: 768px) {{
        .sms-title {{
            font-size: 24px !important;
            margin-bottom: 2px !important;
        }}
        .sms-subtitle {{
            font-size: 13px !important;
            margin-bottom: 8px !important;
        }}
        .nav-label {{
            font-size: 16px !important;
            margin-top: 4px !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            margin-bottom: 10px !important;
            padding: 4px !important;
        }}
        .ww-nav-group-title {{
            font-size: 15px !important;
            margin-bottom: 6px !important;
        }}
        .quick-card, .summary-card {{
            margin-bottom: 8px !important;
        }}
        .salary-helper {{
            font-size: 12px !important;
            padding: 8px 10px !important;
        }}
        .salary-table-wrap {{
            max-height: 72vh !important;
            overflow: auto !important;
        }}
        .salary-table th, .salary-table td {{
            font-size: 12px !important;
            padding: 8px 9px !important;
            white-space: nowrap !important;
        }}
        .summary-card-grid {{
            grid-template-columns: 1fr !important;
            gap: 8px !important;
        }}
        h2, h3 {{
            margin-top: 0.6rem !important;
        }}
        div[data-testid="stDataFrame"] {{
            font-size: 12px !important;
        }}
    }}

    
    /* V105 fuller login screen */
    .login-page-shell {{
        max-width: 980px;
        margin: 14px auto 10px auto;
    }}
    .login-primary-card {{
        background: #FFFFFF;
        border: 1px solid #D7E6EF;
        border-radius: 22px;
        padding: 18px 20px;
        margin: 8px 0 12px 0;
        box-shadow: 0 10px 28px rgba(11,79,113,0.08);
        text-align: center;
    }}
    .login-card-copy {{
        color: #52616F;
        font-weight: 600;
        font-size: 14px;
        line-height: 1.45;
        margin-top: 4px;
    }}
    .login-trust-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin: 12px auto 18px auto;
    }}
    .login-trust-card {{
        background: #FFFFFF;
        border: 1px solid #DCE8EF;
        border-radius: 18px;
        padding: 14px 14px;
        box-shadow: 0 6px 20px rgba(11,79,113,0.06);
        display: flex;
        align-items: center;
        gap: 10px;
        color: #17324D;
        font-weight: 750;
    }}
    .login-trust-card b {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 999px;
        background: #E6FFF7;
        color: #0E9384;
        font-weight: 900;
    }}
    @media (min-width: 900px) {{
        .login-hero {{
            min-height: 250px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .login-main-title {{
            font-size: 36px !important;
        }}
        .login-main-subtitle {{
            max-width: 640px;
            margin-left: auto;
            margin-right: auto;
            font-size: 16px !important;
        }}
    }}
    @media (max-width: 768px) {{
        .login-trust-grid {{
            grid-template-columns: 1fr;
            gap: 8px;
        }}
        .login-trust-card {{
            padding: 11px 12px;
        }}
    }}

    
    /* V106 mobile login compact fix */
    @media (max-width: 768px) {{
        .login-page-shell {{
            margin: 0 auto 4px auto !important;
        }}
        .login-hero {{
            min-height: auto !important;
            padding: 14px 12px !important;
            margin: 4px auto 8px auto !important;
            border-radius: 18px !important;
            box-shadow: 0 6px 16px rgba(11,79,113,0.08) !important;
        }}
        .login-badge {{
            padding: 5px 12px !important;
            margin-bottom: 7px !important;
            font-size: 12px !important;
        }}
        .login-main-title {{
            font-size: 21px !important;
            line-height: 1.12 !important;
            margin-bottom: 6px !important;
        }}
        .login-main-subtitle {{
            font-size: 12px !important;
            line-height: 1.32 !important;
            margin-bottom: 8px !important;
        }}
        .login-feature-row {{
            display: none !important;
        }}
        .login-trust-grid {{
            display: none !important;
        }}
        .login-primary-card {{
            padding: 10px 12px !important;
            margin: 4px 0 8px 0 !important;
            border-radius: 16px !important;
            box-shadow: 0 4px 12px rgba(11,79,113,0.06) !important;
        }}
        .login-card-title {{
            font-size: 15px !important;
            margin: 0 0 3px 0 !important;
        }}
        .login-card-copy {{
            font-size: 12px !important;
            line-height: 1.25 !important;
            margin-top: 2px !important;
        }}
        .login-help {{
            font-size: 11px !important;
            margin-top: 5px !important;
        }}
        div[data-testid="stButton"] button {{
            min-height: 42px !important;
            font-size: 15px !important;
            font-weight: 800 !important;
        }}
        div[data-testid="stExpander"] {{
            margin-top: 6px !important;
        }}
        .block-container {{
            padding-top: 0.75rem !important;
        }}
    }}

    
    /* V107 go-live UI polish */
    .login-trust-grid {{ display: none !important; }}
    .ww-nav-selected-note {{
        border: 1px solid #BEE3F8;
        background: #F0F9FF;
        border-radius: 14px;
        padding: 10px 12px;
        color: #17324D;
        font-weight: 750;
        margin: 8px 0 12px 0;
    }}
    div[data-testid="stButton"] button[kind="primary"] {{
        color: #FFFFFF !important;
    }}
    div[data-testid="stButton"] button:focus,
    div[data-testid="stButton"] button:hover {{
        color: #FFFFFF !important;
        border-color: #0B4F71 !important;
    }}
    .ww-nav-group-title {{
        margin-top: 2px !important;
    }}
    @media (min-width: 900px) {{
        .nav-label {{ margin-top: 8px !important; }}
    }}

    
    /* V108 auto-jump support */
    .ww-nav-selected-note {{
        position: relative;
    }}

    
    /* V109 navigation safety correction */
    .ww-nav-selected-note {{
        background: #E9F7EF !important;
        border: 1px solid #B7E4C7 !important;
        color: #103B2A !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] {{
        background: #0B4F71 !important;
        color: #FFFFFF !important;
        border: 1px solid #0B4F71 !important;
        font-weight: 850 !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] p {{
        color: #FFFFFF !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] {{
        color: #163B5C !important;
        background: #FFFFFF !important;
        border: 1px solid #D7E6EF !important;
        font-weight: 750 !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] p {{
        color: #163B5C !important;
    }}
    @media (max-width: 768px) {{
        .ww-helper-card {{
            margin-top: 8px !important;
        }}
    }}

    
    /* V110 compact navigation */
    .nav-label {{
        margin-top: 6px !important;
        margin-bottom: 4px !important;
    }}
    div[data-testid="stSelectbox"] {{
        margin-bottom: 6px !important;
    }}
    div[data-testid="stExpander"] details {{
        border-radius: 14px !important;
    }}
    .ww-nav-selected-note {{
        background: #E9F7EF !important;
        border: 1px solid #B7E4C7 !important;
        color: #103B2A !important;
        border-radius: 14px !important;
        padding: 9px 12px !important;
        margin: 6px 0 10px 0 !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] p {{
        color: #FFFFFF !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] p {{
        color: #163B5C !important;
    }}

    
    /* V111 button-grid navigation fix */
    .ww-nav-note {{
        background: #F8FBFD;
        border: 1px solid #DDEAF2;
        border-radius: 14px;
        padding: 8px 11px;
        color: #2D4A5F;
        font-size: 13px;
        font-weight: 650;
        margin: 4px 0 8px 0;
    }}
    .ww-nav-group-title {{
        font-size: 14px !important;
        font-weight: 900 !important;
        color: #0B4F71 !important;
        margin: 2px 0 6px 0 !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] {{
        background: #0B4F71 !important;
        color: #FFFFFF !important;
        border: 1px solid #0B4F71 !important;
        font-weight: 900 !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] p {{
        color: #FFFFFF !important;
        font-weight: 900 !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] {{
        color: #163B5C !important;
        background: #FFFFFF !important;
        border: 1px solid #D7E6EF !important;
        font-weight: 760 !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] p {{
        color: #163B5C !important;
        font-weight: 760 !important;
    }}
    @media (max-width: 768px) {{
        .ww-nav-note {{
            font-size: 12px !important;
            padding: 7px 9px !important;
            margin-bottom: 6px !important;
        }}
        .ww-nav-group-title {{
            font-size: 13px !important;
            margin-top: 0 !important;
        }}
        div[data-testid="stButton"] button {{
            min-height: 39px !important;
            padding: 6px 8px !important;
        }}
    }}

    
    /* V112 verified button-grid navigation */
    .ww-nav-note {{
        background: #F8FBFD;
        border: 1px solid #DDEAF2;
        border-radius: 14px;
        padding: 8px 11px;
        color: #2D4A5F;
        font-size: 13px;
        font-weight: 650;
        margin: 4px 0 8px 0;
    }}
    .ww-nav-group-title {{
        font-size: 14px !important;
        font-weight: 900 !important;
        color: #0B4F71 !important;
        margin: 2px 0 6px 0 !important;
    }}
    div[data-testid="stButton"] button[kind="primary"] p {{
        color: #FFFFFF !important;
        font-weight: 900 !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] p {{
        color: #163B5C !important;
        font-weight: 760 !important;
    }}

    
    /* V113 build marker, spacing and auto-scroll repair */
    .block-container {{
        padding-top: 1.15rem !important;
    }}
    .sms-title {{
        margin-top: 4px !important;
        line-height: 1.1 !important;
    }}
    .build-marker {{
        display: inline-block;
        vertical-align: middle;
        margin-left: 10px;
        padding: 3px 8px;
        border-radius: 999px;
        background: #E6FFF7;
        color: #0E7367;
        border: 1px solid #B7E4C7;
        font-size: 11px;
        font-weight: 850;
        letter-spacing: 0.02em;
    }}
    .top-nav {{
        margin-top: 10px !important;
        margin-bottom: 10px !important;
    }}
    .nav-label {{
        margin-top: 12px !important;
        margin-bottom: 7px !important;
        line-height: 1.15 !important;
    }}
    .ww-nav-note {{
        margin: 0 0 12px 0 !important;
        padding: 9px 12px !important;
        border-radius: 14px !important;
    }}
    .ww-nav-group-title {{
        margin: 6px 0 10px 0 !important;
        padding-left: 2px !important;
        line-height: 1.2 !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        margin-bottom: 12px !important;
    }}
    div[data-testid="stButton"] button {{
        margin-top: 2px !important;
        margin-bottom: 6px !important;
        min-height: 42px !important;
    }}
    .ww-content-anchor {{
        scroll-margin-top: 14px;
        height: 1px;
        margin-top: 8px;
    }}
    .ww-bottom-guidance-title {{
        color: #0B4F71;
        font-weight: 900;
        font-size: 15px;
        margin: 12px 0 6px 0;
    }}
    @media (max-width: 768px) {{
        .block-container {{
            padding-top: 0.75rem !important;
        }}
        .sms-title {{
            font-size: 24px !important;
            margin-top: 2px !important;
        }}
        .build-marker {{
            font-size: 10px;
            padding: 2px 7px;
            margin-left: 6px;
        }}
        .top-nav {{
            margin-top: 8px !important;
            margin-bottom: 8px !important;
        }}
        .nav-label {{
            margin-top: 10px !important;
            margin-bottom: 6px !important;
        }}
        .ww-nav-note {{
            font-size: 12px !important;
            margin-bottom: 10px !important;
        }}
        .ww-nav-group-title {{
            margin: 5px 0 8px 0 !important;
        }}
        div[data-testid="stButton"] button {{
            min-height: 40px !important;
            margin-bottom: 5px !important;
        }}
    }}

    
    /* V114 auto-scroll anchor hardening */
    .ww-content-anchor {{
        scroll-margin-top: 18px;
        height: 1px;
        width: 100%;
        display: block;
        margin-top: 4px;
    }}

    /* V115.4 clean notification + mobile auto-scroll + header cushion */
    .block-container {{
        padding-top: 1.8rem !important;
        padding-left: 1.05rem !important;
        padding-right: 1.05rem !important;
        max-width: 1240px !important;
    }}
    .ww-app-shell {{
        background: linear-gradient(135deg, #063F32 0%, #0B5A46 58%, #B98A35 100%);
        color: #FFFFFF !important;
        border-radius: 22px;
        padding: 42px 28px 28px 28px;
        margin: 22px 0 18px 0;
        box-shadow: 0 14px 34px rgba(6, 63, 50, 0.20);
        clear: both;
        position: relative;
        z-index: 5;
        overflow: hidden;
        display: block !important;
        width: 100% !important;
        min-height: 158px;
    }}
    .ww-primary-heading {{
        font-size: clamp(1.95rem, 4.6vw, 2.85rem);
        font-weight: 950;
        letter-spacing: -0.035em;
        line-height: 1.26;
        margin: 6px 0 10px 0;
        color: #FFFFFF !important;
        overflow-wrap: anywhere;
        text-shadow: 0 2px 10px rgba(0,0,0,.18);
        display: block !important;
        visibility: visible !important;
    }}
    .ww-secondary-heading {{
        font-size: clamp(1.05rem, 2.4vw, 1.32rem);
        font-weight: 850;
        line-height: 1.18;
        color: rgba(255,255,255,.94) !important;
        margin: 0 0 5px 0;
    }}
    .ww-subheader {{
        font-size: .95rem;
        line-height: 1.42;
        color: rgba(255,255,255,.82) !important;
        margin: 0;
        max-width: 900px;
    }}
    .build-marker {{
        background: rgba(255,255,255,.16) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255,255,255,.32) !important;
        white-space: nowrap !important;
    }}
    .top-nav, .nav-label, .ww-nav-note, .ww-nav-group-title {{
        clear: both !important;
        overflow-wrap: anywhere !important;
        white-space: normal !important;
    }}
    .top-nav {{
        display: block !important;
        width: 100% !important;
        margin: 4px 0 10px 0 !important;
        line-height: 1.35 !important;
        padding: 9px 12px !important;
        border-radius: 14px !important;
        background: #F8FBFD !important;
        border: 1px solid #DDEAF2 !important;
    }}
    .nav-label {{
        margin-top: 12px !important;
        margin-bottom: 6px !important;
        font-size: 15px !important;
        font-weight: 950 !important;
        color: #063F32 !important;
    }}
    .ww-nav-note {{
        margin: 0 0 10px 0 !important;
        line-height: 1.35 !important;
    }}
    .ww-nav-group-title {{
        font-size: 13px !important;
        line-height: 1.2 !important;
        margin: 4px 0 8px 0 !important;
    }}
    div[data-testid="stButton"] button {{
        white-space: normal !important;
        line-height: 1.2 !important;
        min-height: 42px !important;
        overflow: visible !important;
    }}
    div[data-testid="stButton"] button p {{
        white-space: normal !important;
        line-height: 1.2 !important;
        overflow-wrap: anywhere !important;
    }}
    .ww-app-shell * {{
        color: inherit !important;
        max-width: 100% !important;
    }}
    .ww-app-shell {{
        isolation: isolate !important;
        min-height: 112px;
    }}
    .ww-clean-confirmation {{
        background: #F4FFF8;
        border: 1px solid #B9E7C8;
        border-left: 7px solid #1E8F4D;
        color: #173B27 !important;
        border-radius: 16px;
        padding: 12px 15px;
        margin: 8px 0 12px 0;
        box-shadow: 0 8px 22px rgba(24,37,31,.07);
        animation: wwConfirmPulse 1.15s ease-in-out 2;
    }}
    .ww-clean-confirmation-title {{
        font-weight: 950;
        font-size: 14px;
        color: #115C32 !important;
        margin-bottom: 2px;
    }}
    .ww-clean-confirmation-text {{
        color: #244934 !important;
        font-size: 13px;
        line-height: 1.35;
    }}
    @keyframes wwConfirmPulse {{
        0% {{ transform: scale(1); box-shadow: 0 8px 22px rgba(24,37,31,.07); }}
        45% {{ transform: scale(1.008); box-shadow: 0 0 0 5px rgba(30,143,77,.13), 0 10px 24px rgba(24,37,31,.10); }}
        100% {{ transform: scale(1); box-shadow: 0 8px 22px rgba(24,37,31,.07); }}
    }}
    .ww-action-focus {{
        background: #F4FFF8;
        border: 1px solid #B9E7C8;
        border-left: 6px solid #1E8F4D;
        color: #173B27;
        border-radius: 16px;
        padding: 12px 14px;
        margin: 8px 0 12px 0;
        box-shadow: 0 8px 20px rgba(24,37,31,.06);
    }}
    .ww-action-focus-title {{
        font-weight: 950;
        font-size: 14px;
        margin-bottom: 2px;
        color: #115C32;
    }}
    .ww-action-focus-text {{
        font-size: 13px;
        line-height: 1.38;
        color: #244934;
    }}
    .ww-active-section-card {{
        background: #FFFCF5;
        border: 1px solid #E7DCC8;
        border-left: 6px solid #B98A35;
        border-radius: 16px;
        padding: 11px 14px;
        margin: 8px 0 10px 0;
        box-shadow: 0 8px 20px rgba(24,37,31,.05);
    }}
    .ww-active-section-title {{
        font-size: 15px;
        font-weight: 950;
        color: #172B22;
        margin-bottom: 2px;
    }}
    .ww-active-section-note {{
        color: #64746A;
        font-size: 13px;
        line-height: 1.35;
    }}
    .ww-section-update-wrap {{
        display: flex;
        justify-content: center;
        width: 100%;
        margin: 10px 0 16px 0;
        clear: both;
    }}
    .ww-section-update {{
        width: min(780px, 100%);
        background: #FFFFFF;
        border: 1px solid #E7DCC8;
        border-left: 6px solid #B98A35;
        border-radius: 18px;
        padding: 13px 16px;
        text-align: center;
        box-shadow: 0 10px 26px rgba(24,37,31,.08);
    }}
    .ww-section-update-kicker {{
        text-transform: uppercase;
        letter-spacing: .08em;
        font-weight: 900;
        font-size: 12px;
        color: #B98A35;
        margin-bottom: 2px;
    }}
    .ww-section-update-title {{
        font-size: 18px;
        font-weight: 950;
        color: #172B22;
        line-height: 1.22;
        margin-bottom: 2px;
    }}
    .ww-section-update-note {{
        color: #64746A;
        font-size: 13px;
        line-height: 1.38;
    }}
    .ww-page-heading-card {{
        background: #FFFFFF;
        border: 1px solid #DDEAF2;
        border-radius: 18px;
        padding: 12px 15px;
        margin: 8px 0 14px 0;
        box-shadow: 0 8px 20px rgba(24,37,31,.05);
    }}
    .ww-page-heading-primary {{
        font-size: 22px;
        font-weight: 950;
        color: #063F32;
        line-height: 1.18;
        margin: 0 0 3px 0;
    }}
    .ww-page-heading-secondary {{
        font-size: 14px;
        color: #5B6D63;
        line-height: 1.36;
        margin: 0;
    }}
    @media (max-width: 768px) {{
        .block-container {{
            padding-top: .75rem !important;
            padding-left: .70rem !important;
            padding-right: .70rem !important;
        }}
        .ww-app-shell {{
            border-radius: 18px;
            padding: 36px 18px 24px 18px !important;
            margin-top: 18px !important;
            margin-bottom: 14px;
            min-height: 154px;
        }}
        .ww-primary-heading {{
            font-size: 28px !important;
            line-height: 1.32 !important;
        }}
        .build-marker {{
            display: inline-block !important;
            margin-left: 4px !important;
            margin-top: 4px !important;
        }}
        .top-nav {{
            font-size: 12px !important;
            padding: 8px 10px !important;
        }}
        .ww-section-update {{
            padding: 12px 12px !important;
            border-radius: 16px !important;
        }}
        .ww-page-heading-primary {{
            font-size: 19px !important;
        }}
    }}

    </style>
    """, unsafe_allow_html=True)


def default_wagewise_user_rows():
    return [
        {
            "email": "admin@wagewise.local",
            "name": "WageWise Admin",
            "role": "Admin",
            "password_hash": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
            "active": True,
            "allow_admin": True,
            "allow_supervisor": True,
        },
        {
            "email": "supervisor@wagewise.local",
            "name": "WageWise Supervisor",
            "role": "Supervisor",
            "password_hash": "02423ab2e61297b8262449c93e19be42fb5bbb275860a7d93b1ebdc7b6535ed7",
            "active": True,
            "allow_admin": False,
            "allow_supervisor": True,
        },
    ]

def ensure_recovery_admin_exists(users):
    """Prevent accidental lockout.

    If there is no active Admin-access login, restore the default WageWise Admin.
    If there is no supervisor login, restore the default supervisor.
    """
    users = ensure_user_access_columns(users.copy()) if users is not None else pd.DataFrame()
    for col in REQUIRED_FILES.get("users", []):
        if col not in users.columns:
            users[col] = ""

    changed = False
    if users.empty:
        users = pd.DataFrame(default_wagewise_user_rows())
        changed = True
    else:
        active_mask = users.get("active", pd.Series([True] * len(users))).astype(str).str.lower().isin(["true", "1", "yes", "active"])
        admin_mask = users.get("allow_admin", pd.Series([False] * len(users))).astype(str).str.lower().isin(["true", "1", "yes", "active", "on", "allowed"])
        has_active_admin = bool((active_mask & admin_mask).any())

        if not has_active_admin:
            default_admin = default_wagewise_user_rows()[0]
            users = users[users["email"].astype(str).str.lower() != default_admin["email"]].copy()
            users.loc[len(users), list(default_admin.keys())] = list(default_admin.values())
            changed = True

        has_supervisor = users["email"].astype(str).str.lower().eq("supervisor@wagewise.local").any()
        if not has_supervisor:
            default_supervisor = default_wagewise_user_rows()[1]
            users.loc[len(users), list(default_supervisor.keys())] = list(default_supervisor.values())
            changed = True

    return users, changed


def ensure_users_table_storage_columns():
    """Repair sms_users table columns in Cloud Storage before user save.

    This is intentionally limited only to the users table because user access must not fail silently.
    """
    if not db_enabled():
        return True, "Local mode"
    try:
        engine = get_db_engine()
        with engine.begin() as conn:
            try:
                conn.execute(text('ALTER TABLE "sms_users" ADD COLUMN IF NOT EXISTS "allow_admin" TEXT DEFAULT \'True\''))
                conn.execute(text('ALTER TABLE "sms_users" ADD COLUMN IF NOT EXISTS "allow_supervisor" TEXT DEFAULT \'True\''))
            except Exception:
                # Some deployments may need public schema-qualified table reference
                conn.execute(text('ALTER TABLE public."sms_users" ADD COLUMN IF NOT EXISTS "allow_admin" TEXT DEFAULT \'True\''))
                conn.execute(text('ALTER TABLE public."sms_users" ADD COLUMN IF NOT EXISTS "allow_supervisor" TEXT DEFAULT \'True\''))
        return True, "Users table columns verified"
    except Exception as e:
        return False, str(e)

def force_write_users_to_active_storage(users):
    """Write users directly and verify active storage.

    The generic write_table path can silently fall back to local CSV if Cloud Storage has
    schema drift. For login users, that is not acceptable, so this function writes
    sms_users directly when Cloud Storage is enabled.
    """
    users = ensure_user_access_columns(users.copy())
    base_cols = ["email", "name", "role", "password_hash", "active", "allow_admin", "allow_supervisor"]
    for col in base_cols:
        if col not in users.columns:
            users[col] = ""
    users = users[base_cols].copy()

    try:
        if db_enabled():
            ok, msg = ensure_users_table_storage_columns()
            if not ok:
                return False, f"Users table column repair failed: {msg}"

            engine = get_db_engine()
            with engine.begin() as conn:
                try:
                    conn.execute(text("SET LOCAL statement_timeout = '60000'"))
                except Exception:
                    pass
                conn.execute(text('DELETE FROM "sms_users"'))

            if not users.empty:
                users.astype(str).to_sql("sms_users", engine, if_exists="append", index=False, method="multi", chunksize=100)

            fresh = pd.read_sql_query('SELECT "email", "name", "role", "password_hash", "active", "allow_admin", "allow_supervisor" FROM "sms_users"', engine)
        else:
            write_table_csv("users", users)
            fresh = read_table_csv("users")

        fresh = ensure_user_access_columns(fresh)
        clear_db_table_cache("users")
        st.session_state[db_table_cache_key("users")] = fresh.copy()
        if fresh.empty and not users.empty:
            return False, "Users table was empty after direct write."
        return True, fresh

    except Exception as e:
        return False, str(e)


def verify_user_write(expected_email):
    """Verify user write persisted to the active storage layer, bypassing stale cache."""
    try:
        clear_db_table_cache("users")
        if db_enabled():
            ensure_users_table_storage_columns()
            fresh = pd.read_sql_query('SELECT "email", "name", "role", "password_hash", "active", "allow_admin", "allow_supervisor" FROM "sms_users"', get_db_engine())
        else:
            fresh = read_table_csv("users")
        fresh = ensure_user_access_columns(fresh)
        st.session_state[db_table_cache_key("users")] = fresh.copy()
        return expected_email.strip().lower() in fresh["email"].astype(str).str.lower().tolist()
    except Exception:
        return False



def oidc_enabled():
    """Return True when Streamlit OIDC config is present in secrets."""
    try:
        if "auth" in st.secrets and "redirect_uri" in st.secrets["auth"]:
            return True
    except Exception:
        pass
    return False

def get_oidc_user_dict():
    """Read verified identity from Streamlit OIDC st.user using the same safe pattern as the minimal test app."""
    try:
        is_logged_in = bool(st.user.is_logged_in)
    except Exception:
        return None

    if not is_logged_in:
        return None

    try:
        details = st.user.to_dict()
    except Exception:
        try:
            details = dict(st.user)
        except Exception:
            details = {}

    email = details.get("email", "")
    name = details.get("name", "") or email
    if not email:
        return None
    return {"email": str(email).strip().lower(), "name": str(name).strip() or str(email).strip().lower()}

def lookup_user_access_by_email(email, display_name=None, auto_create=False):
    """Use WageWise users table for authorization after OIDC identity verification."""
    users = ensure_user_access_columns(read_table("users"))
    users, changed = ensure_recovery_admin_exists(users)
    if changed:
        try:
            write_table("users", users)
            clear_db_table_cache("users")
        except Exception:
            pass

    email = str(email).strip().lower()
    match = users[
        (users["email"].astype(str).str.lower() == email) &
        (users["active"].astype(str).str.lower().isin(["true", "1", "yes", "active"]))
    ]

    if not match.empty:
        user = match.iloc[0].to_dict()
        if display_name and not str(user.get("name", "")).strip():
            user["name"] = display_name
        return user

    if auto_create:
        new_row = {
            "email": email,
            "name": display_name or email,
            "role": "Supervisor",
            "password_hash": "",
            "active": True,
            "allow_admin": False,
            "allow_supervisor": True,
        }
        for col in new_row:
            if col not in users.columns:
                users[col] = ""
        users.loc[len(users), list(new_row.keys())] = list(new_row.values())
        try:
            write_table("users", users)
            clear_db_table_cache("users")
        except Exception:
            pass
        return new_row

    return None

def oidc_login_panel():
    st.markdown("""
    <div class='login-primary-card'>
        <div class='login-card-title'>Secure organisation login</div>
        <div class='login-card-copy'>Continue with Google. WageWise will verify your email and open only the areas enabled for you.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Continue with Google", on_click=st.login, use_container_width=True, type="primary", key="oidc_login_button")

def handle_oidc_authenticated_user():
    """Authorize a successfully logged-in OIDC user inside WageWise."""
    oidc_user = get_oidc_user_dict()
    if not oidc_user:
        return False

    # If already authorized in this Streamlit session, do not reprocess or rerun.
    existing = st.session_state.get("auth_user")
    if existing and str(existing.get("email", "")).strip().lower() == oidc_user["email"]:
        return True

    access_user = lookup_user_access_by_email(oidc_user["email"], display_name=oidc_user.get("name"))
    if not access_user:
        st.markdown("""
        <div class='login-hero'>
            <div class='login-badge'>WageWise</div>
            <div class='login-main-title'>Access not enabled</div>
            <div class='login-main-subtitle'>Your Google login worked, but this email is not enabled inside WageWise.</div>
        </div>
        """, unsafe_allow_html=True)
        st.error(f"Email not enabled in WageWise Access Manager: {oidc_user['email']}")
        st.info("Ask an Admin to add this exact Gmail ID under Setup & Controls → Access Manager.")
        st.button("Logout", on_click=st.logout, use_container_width=True)
        return True

    st.session_state.auth_user = access_user
    allowed_roles = user_allowed_roles(access_user)
    if len(allowed_roles) == 1:
        set_access_role_from_auth_user(access_user, allowed_roles[0])
    else:
        st.session_state.user = None
        st.session_state.access_role = None
        st.session_state.page = "Role Selection"
    st.rerun()
    return True



def oidc_access_user_password_hash(email):
    """Non-secret placeholder hash for OIDC-only access records.

    This is not a Gmail password. It simply prevents blank password_hash issues
    while keeping fallback login unusable unless a fallback password is explicitly set.
    """
    return hash_password(f"OIDC_ONLY::{str(email).strip().lower()}::NO_FALLBACK_PASSWORD")


def authenticate(email, password):
    users = ensure_user_access_columns(read_table("users"))
    users, changed = ensure_recovery_admin_exists(users)
    if changed:
        try:
            write_table("users", users)
            clear_db_table_cache("users")
        except Exception:
            pass
    match = users[
        (users["email"].astype(str).str.lower() == email.lower()) &
        (users["password_hash"] == hash_password(password)) &
        (users["active"].astype(str).str.lower().isin(["true", "1", "yes"]))
    ]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def boolish(value, default=True):
    if pd.isna(value):
        return default
    return str(value).strip().lower() in ["true", "1", "yes", "active", "on", "allowed"]

def user_allowed_roles(user):
    """Only two user-facing roles are allowed: Admin and Supervisor.

    Admin includes setup/system-admin utilities inside Admin navigation.
    Older users with Tech/System Admin access are safely mapped to Admin.
    """
    role_value = str(user.get("role", "All Access"))
    legacy_all = role_value in ["All Access", "Tech", "System Admin"]
    role_map = {
        "Admin": boolish(user.get("allow_admin", legacy_all or role_value == "Admin"), legacy_all or role_value == "Admin"),
        "Supervisor": boolish(user.get("allow_supervisor", legacy_all or role_value == "Supervisor"), legacy_all or role_value == "Supervisor"),
    }
    return [r for r, allowed in role_map.items() if allowed]

def ensure_user_access_columns(users):
    for col in ["allow_admin", "allow_supervisor"]:
        if col not in users.columns:
            users[col] = True
    return users


def login_screen():
    st.markdown("""
    <div class='login-page-shell'>
        <div class='login-hero'>
            <div class='login-badge'>WageWise</div>
            <div class='login-main-title'>Payroll clarity. Faster access.</div>
            <div class='login-main-subtitle'>Manage leaves, advances, payroll review and approvals in one guided workflow.</div>
            <div class='login-feature-row'>
                <div>✓ Google sign-in</div>
                <div>✓ Admin / Supervisor access</div>
                <div>✓ Mobile-ready workflow</div>
                <div>✓ Safer corrections</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    left, center, right = st.columns([0.75, 2.5, 0.75])
    with center:
        submitted = False
        if oidc_enabled():
            oidc_login_panel()
            with st.expander("Fallback / support login", expanded=False):
                st.caption("Use this only if Google login is not available and the administrator has issued a fallback password.")
                with st.form("single_login_form"):
                    email = st.text_input("Email", value="admin@wagewise.local", placeholder="name@wagewise.local")
                    password = st.text_input("Fallback password", type="password", placeholder="Enter fallback password")
                    submitted = st.form_submit_button("Login with fallback password", use_container_width=True)
        else:
            st.markdown("<div class='login-card-title'>Sign in to continue</div>", unsafe_allow_html=True)
            st.caption("Google login is not configured yet. Using fallback login.")
            with st.form("single_login_form"):
                email = st.text_input("Email", value="admin@wagewise.local", placeholder="name@wagewise.local")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                submitted = st.form_submit_button("Login securely", use_container_width=True, type="primary")

        st.markdown("<div class='login-help'>Access is controlled by your WageWise administrator.</div>", unsafe_allow_html=True)

    if submitted:
        user = authenticate(email, password)
        if user:
            st.session_state.auth_user = user
            allowed_roles = user_allowed_roles(user)
            if len(allowed_roles) == 1:
                set_access_role_from_auth_user(user, allowed_roles[0])
            else:
                st.session_state.user = None
                st.session_state.access_role = None
                st.session_state.page = "Role Selection"
            st.rerun()
        else:
            st.error("Invalid credentials or inactive user.")


def set_access_role_from_auth_user(auth_user, role_key):
    st.session_state.user = {
        "email": auth_user["email"] if role_key != "Supervisor" else auth_user.get("email", "supervisor@wagewise.local"),
        "name": auth_user.get("name", "User") if role_key != "Supervisor" else auth_user.get("name", "Supervisor"),
        "role": "Admin" if role_key == "Tech" else role_key,
        "active": True,
    }
    st.session_state.access_role = role_key
    st.session_state.page = "Dashboard"


def role_selection_page():
    auth_user = st.session_state.get("auth_user")
    if not auth_user:
        wagewise_logout()

    st.markdown("""
    <div class='login-shell'>
        <div class='login-logo'>✓</div>
        <div class='login-title'>Choose Role</div>
        <div class='login-subtitle'>One login gives access to your allowed WageWise areas.</div>
    </div>
    """, unsafe_allow_html=True)

    all_roles = [
        ("Admin", "Admin", "Payroll operations, setup, users, bulk upload, database health and payroll approval."),
        ("Supervisor", "Supervisor", "Simple daily flow with only two actions: Mark Leave and Add Advance."),
    ]
    allowed = set(user_allowed_roles(auth_user))
    roles = [r for r in all_roles if r[0] in allowed]

    if not roles:
        st.error("No role access is enabled for this login. Please contact the administrator.")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        return

    if len(roles) == 1:
        role_key = roles[0][0]
        set_access_role_from_auth_user(auth_user, role_key)
        st.rerun()

    cols = st.columns(len(roles))
    for col, (role_key, title, desc) in zip(cols, roles):
        with col:
            st.markdown(f"""
            <div class='role-card'>
                <div class='role-title'>{title}</div>
                <div class='role-help'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Open {title}", use_container_width=True):
                set_access_role_from_auth_user(auth_user, role_key)
                st.rerun()

    st.divider()
    if st.button("Logout", use_container_width=True):
        add_audit(auth_user["email"], "LOGOUT_FROM_ROLE_SELECTION", "Logged out before choosing role")
        wagewise_logout()



def wagewise_logout():
    st.session_state.clear()
    try:
        if oidc_enabled() and getattr(st.user, "is_logged_in", False):
            st.logout()
            return
    except Exception:
        pass
    st.rerun()


def active_employees_for_user():
    employees = read_table("employees")
    if employees.empty:
        return employees
    employees["Status"] = employees["Status"].fillna("Active").astype(str).str.strip()
    employees = employees[employees["Status"].str.lower() == "active"].copy()
    if "Supervisor_Email" not in employees.columns:
        employees["Supervisor_Email"] = ""

    if st.session_state.user["role"] == "Supervisor":
        user_email = str(st.session_state.user.get("email", "")).strip().lower()
        supervisor_col = employees["Supervisor_Email"].fillna("").astype(str).str.strip().str.lower()

        # Backward compatibility: old SMS data used supervisor@wagewise.local.
        legacy_email = user_email.replace("@wagewise.local", "@sms.local")
        direct_match = employees[(supervisor_col == user_email) | (supervisor_col == legacy_email)]

        if not direct_match.empty:
            return direct_match

        # If no employee is assigned to this supervisor, do not block the supervisor flow.
        # This avoids a broken demo/UAT state after domain migration from sms.local to wagewise.local.
        st.info("No employees are specifically mapped to this supervisor login yet. Showing all active employees for now. Admin can later assign Supervisor_Email in Employees.")
        return employees

    return employees


def generate_emp_id_from_name(name):
    clean = "".join(ch for ch in str(name).strip() if ch.isalnum())
    return f"E_{clean}" if clean else ""

def employee_choices(df=None):
    if df is None:
        df = active_employees_for_user()
    return [f"{r.Emp_ID} - {r.Name}" for r in df.itertuples()]

def extract_emp_id(choice):
    return str(choice).split(" - ")[0]

def month_label(year, month):
    return f"{calendar.month_abbr[int(month)]}-{int(year)}"

def parse_month_label(label):
    mon, yr = label.split("-")
    return int(yr), list(calendar.month_abbr).index(mon)


def month_label_to_date(month_text):
    """Convert Apr-2026 style month label to first date of that month for date_input."""
    try:
        y, m = parse_month_label(str(month_text))
        return date(int(y), int(m), 1)
    except Exception:
        return date.today().replace(day=1)

def date_to_month_label(dt):
    """Convert a date_input value to Apr-2026 style month label."""
    return month_label(int(dt.year), int(dt.month))


def normalize_month_label_value(value):
    """Normalize month values to app format like Apr-2026.

    Supports existing labels like Apr-2026, full month labels like April-2026,
    date-like values, and Timestamp/date values. Returns blank when it cannot parse.
    """
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, (pd.Timestamp, datetime, date)):
            return month_label(int(value.year), int(value.month))
        s = str(value).strip()
        if not s or s.lower() in ["nan", "nat", "none"]:
            return ""
        # Already in Apr-2026 format.
        try:
            y, m = parse_month_label(s)
            return month_label(y, m)
        except Exception:
            pass
        # Full month name format, e.g. April-2026.
        if "-" in s:
            left, right = s.split("-", 1)
            left_clean = left.strip()
            right_clean = right.strip()
            for idx, full_name in enumerate(calendar.month_name):
                if idx and left_clean.lower() == full_name.lower():
                    return month_label(int(right_clean), idx)
        parsed = pd.to_datetime(s, errors="coerce", dayfirst=True)
        if not pd.isna(parsed):
            return month_label(int(parsed.year), int(parsed.month))
    except Exception:
        return ""
    return ""


def month_sort_key(month_value):
    """Chronological sort key for month labels; unknown labels go last."""
    normalized = normalize_month_label_value(month_value)
    try:
        y, m = parse_month_label(normalized)
        return (int(y), int(m), str(normalized))
    except Exception:
        return (9999, 99, str(month_value))


def build_salary_summary_month_options(payroll=None):
    """Build month dropdown options for Salary Summary.

    Earlier versions only read payroll_items['Month']. If a month was recalculated
    through profile/schedule flows but month labels varied or were available through
    the linked logs/schedules first, April could disappear from the mobile summary
    selector. This merges all trusted payroll-related month sources and normalizes
    them before display.
    """
    months = []

    def add_months_from_df(df, column):
        try:
            if df is not None and not df.empty and column in df.columns:
                for value in df[column].dropna().astype(str).tolist():
                    norm = normalize_month_label_value(value)
                    if norm:
                        months.append(norm)
        except Exception:
            pass

    if payroll is None:
        payroll = normalize_payroll_columns(read_table("payroll_items"))
    add_months_from_df(payroll, "Month")
    add_months_from_df(read_table("leave_adjustment_log"), "Month")
    add_months_from_df(read_table("advance_schedule"), "Deduction_Month")

    # Preserve a recently selected/recalculated month if present in session state.
    for key in ["salary_summary_selected_month", "last_recalculated_month", "current_month"]:
        norm = normalize_month_label_value(st.session_state.get(key, ""))
        if norm:
            months.append(norm)

    unique = sorted(set([m for m in months if m]), key=month_sort_key)
    return unique




def apply_v116_1_backend_requested_actions():
    """Idempotent backend correction requested before final shipment.

    Actions:
    1) Rebuild missing advance master records from advance schedule rows for Apr-2026 onwards.
    2) Mark employee-specific holiday exclusions for E_Vivek from 2026-05-01 to 2026-05-12.

    This is intentionally conservative: it only creates missing rows and does not delete/replace
    existing advance or holiday data.
    """
    session_key = "v116_1_backend_actions_applied"
    if st.session_state.get(session_key):
        return

    now_ts = datetime.now().isoformat(timespec="seconds")
    actor = "backend@wagewise.local"
    changed_advance_cases = 0
    changed_holidays = 0

    try:
        schedule = normalize_required_columns("advance_schedule", read_table("advance_schedule"))
        cases = normalize_required_columns("advance_cases", read_table("advance_cases"))

        if cases.empty:
            cases = pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
        if schedule.empty:
            schedule = pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])

        existing_adv_ids = set(cases.get("Advance_ID", pd.Series(dtype=str)).astype(str).tolist()) if "Advance_ID" in cases.columns else set()
        schedule_rows = []
        cutoff = date(2026, 4, 1)

        if not schedule.empty and "Advance_ID" in schedule.columns:
            for row in schedule.to_dict("records"):
                adv_id = str(row.get("Advance_ID", "")).strip()
                emp_id = str(row.get("Emp_ID", "")).strip()
                deduction_month = str(row.get("Deduction_Month", "")).strip()
                if not adv_id or not emp_id or not deduction_month:
                    continue
                deduction_date = month_label_to_date(deduction_month)
                if deduction_date < cutoff:
                    continue
                schedule_rows.append({**row, "_deduction_date": deduction_date})

        by_advance = {}
        for row in schedule_rows:
            by_advance.setdefault(str(row.get("Advance_ID", "")).strip(), []).append(row)

        for adv_id, rows in by_advance.items():
            if not adv_id or adv_id in existing_adv_ids:
                continue
            rows = sorted(rows, key=lambda r: r["_deduction_date"])
            emp_id = str(rows[0].get("Emp_ID", "")).strip()
            if not emp_id:
                continue
            total_amount = 0.0
            first_deduction = 0.0
            first_month = str(rows[0].get("Deduction_Month", "")).strip()
            first_date = rows[0]["_deduction_date"]
            distinct_months = []
            for r in rows:
                deduction_value = safe_float(r.get("Final_Deduction", 0))
                if deduction_value == 0:
                    deduction_value = safe_float(r.get("Admin_Updated_Deduction", 0))
                if deduction_value == 0:
                    deduction_value = safe_float(r.get("Scheduled_Deduction", 0))
                total_amount += deduction_value
                if str(r.get("Deduction_Month", "")).strip() == first_month:
                    first_deduction += deduction_value
                month_text = str(r.get("Deduction_Month", "")).strip()
                if month_text and month_text not in distinct_months:
                    distinct_months.append(month_text)

            if total_amount <= 0:
                continue

            cases.loc[len(cases)] = [
                adv_id,
                emp_id,
                str(first_date),
                round(total_amount, 2),
                first_month,
                round(first_deduction, 2),
                max(len(distinct_months) - 1, 0),
                "Open",
                "V116.1 backend reconciliation: advance case created from advance schedule.",
                actor,
                now_ts,
            ]
            existing_adv_ids.add(adv_id)
            changed_advance_cases += 1

        if changed_advance_cases:
            write_table("advance_cases", cases)

        holidays = normalize_required_columns("employee_holidays", read_table("employee_holidays"))
        if holidays.empty:
            holidays = pd.DataFrame(columns=REQUIRED_FILES["employee_holidays"])

        holiday_emp = "E_Vivek"
        holiday_remark = "started on 13th May"
        holiday_name = "Employee-specific holiday"
        for day in range(1, 13):
            holiday_date = date(2026, 5, day).isoformat()
            duplicate = False
            if not holidays.empty and {"Date", "Emp_ID"}.issubset(holidays.columns):
                duplicate = (
                    (holidays["Date"].astype(str) == holiday_date)
                    & (holidays["Emp_ID"].astype(str) == holiday_emp)
                ).any()
            if duplicate:
                continue
            holidays.loc[len(holidays)] = [
                f"HOL-E-VIVEK-202605{day:02d}",
                holiday_date,
                holiday_emp,
                holiday_name,
                holiday_remark,
                actor,
                now_ts,
            ]
            changed_holidays += 1

        if changed_holidays:
            write_table("employee_holidays", holidays)

        if changed_advance_cases or changed_holidays:
            add_audit(
                actor,
                "V116_1_BACKEND_ACTIONS",
                f"Created {changed_advance_cases} missing advance case(s) from schedules; added {changed_holidays} E_Vivek holiday exclusion row(s).",
            )

        st.session_state[session_key] = True
    except Exception as e:
        st.session_state[session_key] = True
        st.session_state["v116_1_backend_actions_warning"] = str(e)

def add_months(year, month, n):
    month_index = (year * 12 + (month - 1)) + n
    return month_index // 12, (month_index % 12) + 1

def cleanse_data():
    employees = read_table("employees")
    leave_entries = read_table("leave_entries")
    advance_cases = read_table("advance_cases")
    schedule = read_table("advance_schedule")

    before = len(employees)
    employees = employees.drop_duplicates(subset=["Emp_ID"], keep="last")
    if len(employees) < before:
        add_clean_log("Employees", "Duplicate Emp_ID", "Kept latest row", "Emp_ID")

    for idx, row in employees.iterrows():
        if normalize_employee_level(row.get("Level")) not in LEVEL_OPTIONS:
            employees.at[idx, "Level"] = "L1"
            add_clean_log("Employees", "Invalid Level", "Defaulted to L1", str(row.get("Emp_ID")))
        else:
            employees.at[idx, "Level"] = normalize_employee_level(row.get("Level"))
        employees.at[idx, "Monthly_Salary"] = max(0, pd.to_numeric(row.get("Monthly_Salary", 0), errors="coerce") or 0)
        employees.at[idx, "Extra_Paid_Leaves"] = max(0, pd.to_numeric(row.get("Extra_Paid_Leaves", 0), errors="coerce") or 0)

    valid_emp = set(employees["Emp_ID"].astype(str))
    valid_leave = set(LEAVE_UNITS.keys())

    before = len(leave_entries)
    leave_entries = leave_entries[leave_entries["Emp_ID"].astype(str).isin(valid_emp)]
    if len(leave_entries) < before:
        add_clean_log("Leaves", "Unknown Emp_ID", "Removed invalid leave rows", "bulk")

    before = len(leave_entries)
    leave_entries = leave_entries[leave_entries["Leave_Type"].astype(str).isin(valid_leave)]
    if len(leave_entries) < before:
        add_clean_log("Leaves", "Invalid Leave_Type", "Removed invalid leave rows", "bulk")

    if not leave_entries.empty:
        leave_entries["Date"] = parse_app_date_series(leave_entries["Date"]).dt.date.astype(str)
        leave_entries = leave_entries[leave_entries["Date"] != "NaT"]
        before = len(leave_entries)
        leave_entries = leave_entries.drop_duplicates(subset=["Date", "Emp_ID"], keep="last")
        if len(leave_entries) < before:
            add_clean_log("Leaves", "Duplicate date + employee", "Kept latest row", "bulk")

    for tbl_name, tbl in [("Advance Cases", advance_cases), ("Advance Schedule", schedule)]:
        if not tbl.empty and "Emp_ID" in tbl.columns:
            before = len(tbl)
            tbl = tbl[tbl["Emp_ID"].astype(str).isin(valid_emp)]
            if len(tbl) < before:
                add_clean_log(tbl_name, "Unknown Emp_ID", "Removed invalid advance rows", "bulk")
        if tbl_name == "Advance Cases":
            advance_cases = tbl
        else:
            schedule = tbl

    if not advance_cases.empty:
        advance_cases["Amount_Given"] = pd.to_numeric(advance_cases["Amount_Given"], errors="coerce").fillna(0).clip(lower=0)
        advance_cases["First_Month_Deduction"] = pd.to_numeric(advance_cases["First_Month_Deduction"], errors="coerce").fillna(0).clip(lower=0)
        advance_cases["Remaining_Months"] = pd.to_numeric(advance_cases["Remaining_Months"], errors="coerce").fillna(0).clip(lower=0)

    if not schedule.empty:
        for col in ["Scheduled_Deduction", "Admin_Updated_Deduction", "Final_Deduction"]:
            schedule[col] = pd.to_numeric(schedule[col], errors="coerce").fillna(0).clip(lower=0)

    write_table("employees", employees)
    write_table("leave_entries", leave_entries)
    write_table("advance_cases", advance_cases)
    write_table("advance_schedule", schedule)

def create_advance_schedule(advance_id, emp_id, amount, start_year, start_month, first_deduction, remaining_months):
    schedule = read_table("advance_schedule")
    first_deduction = min(float(first_deduction), float(amount))
    remaining_amount = max(0, float(amount) - first_deduction)
    rows = []
    y, m = start_year, start_month
    if first_deduction > 0:
        rows.append([advance_id, emp_id, month_label(y, m), first_deduction, "", first_deduction, "Open", "", ""])
    if remaining_months > 0 and remaining_amount > 0:
        per_month = remaining_amount / int(remaining_months)
        for i in range(int(remaining_months)):
            y2, m2 = add_months(start_year, start_month, i + 1)
            rows.append([advance_id, emp_id, month_label(y2, m2), round(per_month, 2), "", round(per_month, 2), "Open", "", ""])
    for row in rows:
        schedule.loc[len(schedule)] = row
    write_table("advance_schedule", schedule)


def default_special_impact_config():
    # Regular payroll must not apply special impact automatically.
    # Special impact is activated only from Employee Profile for a selected employee.
    return {
        "apply_uninformed": False,
        "uninformed_penalty_per_leave": 50.0,
        "apply_collaborative": False,
        "collaborative_mode": "Deduct as leave days",
        "collaborative_value": 1.5,
    }

def calculate_special_impact(uninformed_count, collaborative_count, config):
    cfg = default_special_impact_config()
    if config:
        cfg.update(config)

    uninformed_amount = 0.0
    collaborative_amount = 0.0

    if cfg.get("apply_uninformed", True):
        uninformed_amount = float(uninformed_count) * safe_float(cfg.get("uninformed_penalty_per_leave", 50.0))

    if cfg.get("apply_collaborative", True):
        mode = str(cfg.get("collaborative_mode", "Deduct as leave days"))
        value = safe_float(cfg.get("collaborative_value", 1.5))

        if mode == "Deduct as leave days":
            # Day mode changes leave units only. No rupee special amount is added here.
            collaborative_amount = 0.0
        elif mode == "Additional amount per collaborative leave":
            # Amount mode: value is rupees per collaborative leave, never leave days.
            collaborative_amount = float(collaborative_count) * value
        elif mode == "Fixed total collaborative deduction":
            # Fixed amount mode: value is total rupee deduction for the selected employee/month.
            collaborative_amount = value
        else:
            collaborative_amount = 0.0

    return round(uninformed_amount, 2), round(collaborative_amount, 2), round(uninformed_amount + collaborative_amount, 2), cfg

def collaborative_leave_units(config):
    cfg = default_special_impact_config()
    if config:
        cfg.update(config)

    if not cfg.get("apply_collaborative", True):
        return 1.0

    mode = str(cfg.get("collaborative_mode", "Deduct as leave days"))
    value = safe_float(cfg.get("collaborative_value", 1.5))

    if mode == "Deduct as leave days":
        # Only day mode changes leave units. Cap protects against accidental 50-day impact.
        return min(max(value, 0.0), 10.0)

    # Amount modes keep collaborative leave as 1 leave day and apply rupee impact separately.
    return 1.0


def calculate_employee_payroll(emp, year, month, extra_leave_override=None, special_override=None, advance_override=None, special_config=None):
    leave_entries = normalize_leave_entries_for_payroll(read_table("leave_entries"))
    employee_holidays = read_table("employee_holidays")
    schedule = read_table("advance_schedule")
    advance_cases = read_table("advance_cases")

    total_days = calendar.monthrange(year, month)[1]
    current_month = month_label(year, month)
    month_start = pd.Timestamp(year=year, month=month, day=1)
    month_end = pd.Timestamp(year=year, month=month, day=total_days)

    emp_id = str(emp["Emp_ID"])
    level = normalize_employee_level(emp["Level"])
    eligible_for_month, service_start, service_days, service_fraction, join_dt = employee_service_window_for_month(emp, year, month)
    if not eligible_for_month:
        return None, []

    salary_value = safe_float(emp.get("Monthly_Salary", 0))
    if is_contractor_level(level):
        # L0 contractor: stored salary field is treated as the defined per-day rate.
        daily_wage = salary_value
        monthly_salary = round(daily_wage * service_days, 2)
        base_extra = 0.0
        extra = 0.0
    else:
        full_month_salary = salary_value
        daily_wage = full_month_salary / total_days if total_days else 0.0
        monthly_salary = round(daily_wage * service_days, 2)
        base_extra = float(emp.get("Extra_Paid_Leaves", 0) or 0)
        extra = base_extra if extra_leave_override is None else float(extra_leave_override)

    emp_holidays = employee_holidays[employee_holidays["Emp_ID"].astype(str) == emp_id].copy() if not employee_holidays.empty else employee_holidays.copy()
    if not emp_holidays.empty:
        emp_holidays["Date_dt"] = parse_app_date_series(emp_holidays["Date"])
        emp_holidays = emp_holidays[(emp_holidays["Date_dt"] >= service_start) & (emp_holidays["Date_dt"] <= month_end)]
    holiday_exclusions = float(len(emp_holidays))

    if is_contractor_level(level):
        paid_leave_allowed = 0.0
    else:
        paid_leave_allowed = prorate_paid_leave_quota(level, service_fraction) + extra + holiday_exclusions

    if leave_entries.empty:
        emp_leaves = pd.DataFrame(columns=list(leave_entries.columns) + ["Date_dt"])
    else:
        valid_emp_ids = {emp_id, normalize_emp_id_value(emp_id), normalize_emp_id_value(emp.get("Name", ""))}
        emp_leaves = leave_entries[leave_entries["Emp_ID"].astype(str).apply(lambda x: normalize_emp_id_value(x) in valid_emp_ids)].copy()
        if not emp_leaves.empty:
            emp_leaves["Date_dt"] = parse_app_date_series(emp_leaves["Date"])
            emp_leaves = emp_leaves[(emp_leaves["Date_dt"] >= service_start) & (emp_leaves["Date_dt"] <= month_end)]

    # V116.2 guard: if the employee has no leave rows after filtering,
    # emp_leaves may be an empty DataFrame without Date_dt. Payroll must
    # continue instead of crashing on sort_values("Date_dt").
    if "Date_dt" not in emp_leaves.columns:
        emp_leaves["Date_dt"] = pd.NaT

    impact_cfg = default_special_impact_config()
    if special_config:
        impact_cfg.update(special_config)
    collaborative_units_value = collaborative_leave_units(impact_cfg)

    leave_units = 0.0
    regular_leave_units_before_special = 0.0
    uninformed_count = 0
    collaborative_count = 0
    paid_balance = paid_leave_allowed
    leave_log_rows = []

    for _, leave in emp_leaves.sort_values("Date_dt", na_position="last").iterrows():
        status_value = str(leave.get("Status", "Approved")).strip().lower()
        if status_value in ["rejected", "cancelled", "canceled"]:
            continue

        leave_type = normalize_leave_type(leave.get("Leave_Type", ""))
        units = float(LEAVE_UNITS.get(leave_type, 0))

        if units == 0:
            compact_type = canonical_text(leave_type)
            fallback_units = {
                "leavefullday": 1.0,
                "fullday": 1.0,
                "leavehalfday": 0.5,
                "halfday": 0.5,
                "leaveuninformed": 1.0,
                "uninformed": 1.0,
                "leavecollaborative": 1.5,
                "collaborative": 1.5,
                "collaborated": 1.5,
            }
            units = float(fallback_units.get(compact_type, 0))

        # Regular payroll view: collaborative leave is counted as 1 normal leave.
        regular_units = 1.0 if leave_type == "Leave - Collaborative" else units

        # Special impact view: collaborative can become 1.5 or other configured value only when activated.
        if leave_type == "Leave - Collaborative":
            units = collaborative_units_value

        paid_used = min(paid_balance, units)
        lop_created = max(0, units - paid_used)
        paid_before = paid_balance
        paid_balance = max(0, paid_balance - paid_used)
        special = 50 if leave_type == "Leave - Uninformed" else 0
        uninformed_count += 1 if leave_type == "Leave - Uninformed" else 0
        collaborative_count += 1 if leave_type == "Leave - Collaborative" else 0
        regular_leave_units_before_special += regular_units
        leave_units += units
        leave_log_rows.append({
            "Month": current_month,
            "Date": leave["Date"],
            "Emp_ID": emp_id,
            "Original_Leave_Type": leave_type,
            "Leave_Units": units,
            "Regular_Leave_Units_Before_Special": regular_units,
            "Special_Impact_Difference": units - regular_units,
            "Paid_Leave_Before": paid_before,
            "Paid_Leave_Used": paid_used,
            "LOP_Created": lop_created,
            "Special_Deduction": special,
            "Remarks": leave.get("Remarks", ""),
            "Supervisor": leave.get("Supervisor", ""),
            "Timestamp": leave.get("Timestamp", ""),
        })

    if not emp_leaves.empty and leave_units == 0:
        leave_log_rows.append({
            "Month": current_month,
            "Date": "",
            "Emp_ID": emp_id,
            "Original_Leave_Type": "DIAGNOSTIC",
            "Leave_Units": 0,
            "Paid_Leave_Before": paid_balance,
            "Paid_Leave_Used": 0,
            "LOP_Created": 0,
            "Special_Deduction": 0,
            "Remarks": "Leave rows were found but did not match allowed leave type values.",
            "Supervisor": "",
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
        })

    special_impact_leave_difference = round(leave_units - regular_leave_units_before_special, 2)

    paid_leave_used = min(leave_units, paid_leave_allowed)
    lop_days = max(0, leave_units - paid_leave_allowed)
    present_days = max(0.0, service_days - lop_days)
    unused_leaves = max(0, paid_leave_allowed - paid_leave_used)
    encashment = unused_leaves * daily_wage

    uninformed_special_amount, collaborative_special_amount, default_special_deduction, final_impact_cfg = calculate_special_impact(
        uninformed_count, collaborative_count, impact_cfg
    )
    special_applied = default_special_deduction if special_override is None else float(special_override)

    # Advance logic:
    # - Monthly salary deduction comes only from the selected month's repayment schedule.
    # - Deduction is capped by outstanding advance balance to avoid over-deduction.
    # - Future advances should not affect the current payroll.
    if not advance_cases.empty:
        advance_cases = advance_cases.copy()
        advance_cases["Advance_Date_dt"] = parse_app_date_series(advance_cases["Advance_Date"])
        emp_cases_all = advance_cases[
            (advance_cases["Emp_ID"].astype(str) == emp_id) &
            (advance_cases.get("Status", "Open").astype(str).apply(advance_status_is_active))
        ].copy()
        emp_cases_until_month = emp_cases_all[
            emp_cases_all["Advance_Date_dt"].notna() &
            (emp_cases_all["Advance_Date_dt"] <= month_end)
        ].copy() if not emp_cases_all.empty else emp_cases_all.head(0)
        emp_cases_month = emp_cases_until_month[
            (emp_cases_until_month["Advance_Date_dt"] >= month_start) &
            (emp_cases_until_month["Advance_Date_dt"] <= month_end)
        ] if not emp_cases_until_month.empty else emp_cases_until_month.head(0)
        emp_cases_prior = emp_cases_until_month[
            emp_cases_until_month["Advance_Date_dt"] < month_start
        ] if not emp_cases_until_month.empty else emp_cases_until_month.head(0)

        advance_given_this_month = safe_numeric_series(emp_cases_month["Amount_Given"]).sum() if not emp_cases_month.empty and "Amount_Given" in emp_cases_month.columns else 0.0
        prior_advance_given = safe_numeric_series(emp_cases_prior["Amount_Given"]).sum() if not emp_cases_prior.empty and "Amount_Given" in emp_cases_prior.columns else 0.0
        total_advance_given_until_month = prior_advance_given + advance_given_this_month
        eligible_advance_ids = set(emp_cases_until_month["Advance_ID"].astype(str)) if not emp_cases_until_month.empty and "Advance_ID" in emp_cases_until_month.columns else set()
        prior_advance_ids = set(emp_cases_prior["Advance_ID"].astype(str)) if not emp_cases_prior.empty and "Advance_ID" in emp_cases_prior.columns else set()
    else:
        advance_given_this_month = 0.0
        prior_advance_given = 0.0
        total_advance_given_until_month = 0.0
        eligible_advance_ids = set()
        prior_advance_ids = set()

    if not schedule.empty:
        schedule_emp = schedule[
            (schedule["Emp_ID"].astype(str) == emp_id) &
            (schedule.get("Status", "Open").astype(str).str.lower().isin(["open", "paid", "deducted", "closed", ""]))
        ].copy()

        # If advance master is present, ignore schedule rows linked to future/missing advances.
        if eligible_advance_ids and "Advance_ID" in schedule_emp.columns:
            schedule_emp = schedule_emp[schedule_emp["Advance_ID"].astype(str).isin(eligible_advance_ids)].copy()

        current_month_deductions = 0.0
        prior_deducted_before_current = 0.0
        prior_deducted_upto_current = 0.0
        total_deducted_before_current = 0.0
        total_deducted_upto_current_raw = 0.0

        for _, srow in schedule_emp.iterrows():
            mt = schedule_month_tuple_value(srow.get("Deduction_Month", ""))
            if mt is None:
                continue
            amt = max(0.0, safe_float(srow.get("Final_Deduction", 0)))

            if mt < (year, month):
                total_deducted_before_current += amt
                if str(srow.get("Advance_ID", "")) in prior_advance_ids:
                    prior_deducted_before_current += amt

            if mt == (year, month):
                current_month_deductions += amt

            if mt <= (year, month):
                total_deducted_upto_current_raw += amt
                if str(srow.get("Advance_ID", "")) in prior_advance_ids:
                    prior_deducted_upto_current += amt
    else:
        current_month_deductions = 0.0
        prior_deducted_before_current = 0.0
        prior_deducted_upto_current = 0.0
        total_deducted_before_current = 0.0
        total_deducted_upto_current_raw = 0.0

    default_advance = current_month_deductions
    requested_advance_deduction = default_advance if advance_override is None else safe_float(advance_override)
    advance_balance_before_current_month = max(0.0, total_advance_given_until_month - total_deducted_before_current)
    advance_deduction = min(max(0.0, requested_advance_deduction), advance_balance_before_current_month)

    # Balance calculations should not become negative even if schedule data is duplicated/dirty.
    total_deducted_upto_current = min(total_advance_given_until_month, total_deducted_before_current + advance_deduction)
    advance_prior_month = max(0.0, prior_advance_given - prior_deducted_upto_current)
    advance_balance_open = advance_balance_before_current_month
    advance_balance_close = max(0.0, total_advance_given_until_month - total_deducted_upto_current)

    final_without_special = (present_days * daily_wage) + encashment - advance_deduction
    final_with_special = final_without_special - special_applied

    item = {
        "Month": current_month,
        "Emp_ID": emp_id,
        "Name": emp["Name"],
        "Level": level,
        "Monthly_Salary": monthly_salary,
        "Date_of_Joining": "" if pd.isna(join_dt) else str(pd.Timestamp(join_dt).date()),
        "Service_Days_For_Month": service_days,
        "Total_Days": total_days,
        "Daily_Wage": round(daily_wage, 2),
        "Leave_Units": leave_units,
        "Regular_Leave_Units_Before_Special": round(regular_leave_units_before_special, 2),
        "Special_Impact_Leave_Units": round(leave_units, 2),
        "Special_Impact_Leave_Difference": special_impact_leave_difference,
        "Holiday_Exclusions": holiday_exclusions,
        "Extra_Paid_Leaves": extra,
        "Paid_Leave_Allowed": paid_leave_allowed,
        "Paid_Leave_Used": paid_leave_used,
        "Leaves_After_Allowed_And_Exclusions": lop_days,
        "LOP_Days": lop_days,
        "Leave_Deduction_Cost": round(lop_days * daily_wage, 2),
        "Present_Days": present_days,
        "Unused_Leaves": unused_leaves,
        "Encashment": round(encashment, 2),
        "Uninformed_Count": uninformed_count,
        "Collaborative_Count": collaborative_count,
        "Special_Deductions": default_special_deduction,
        "Special_Deductions_Applied": special_applied,
        "Uninformed_Special_Amount": uninformed_special_amount,
        "Collaborative_Special_Amount": collaborative_special_amount,
        "Apply_Uninformed_Impact": "Yes" if final_impact_cfg.get("apply_uninformed", True) else "No",
        "Uninformed_Penalty_Per_Leave": safe_float(final_impact_cfg.get("uninformed_penalty_per_leave", 50.0)),
        "Apply_Collaborative_Impact": "Yes" if final_impact_cfg.get("apply_collaborative", True) else "No",
        "Collaborative_Impact_Mode": final_impact_cfg.get("collaborative_mode", "Deduct as leave days"),
        "Collaborative_Impact_Value": safe_float(final_impact_cfg.get("collaborative_value", 1.5)),
        "Advance_Prior_Month": round(advance_prior_month, 2),
        "Advance_Given_This_Month": round(advance_given_this_month, 2),
        "Advance_Deduction": round(advance_deduction, 2),
        "Advance_Balance_Open": round(advance_balance_open, 2),
        "Advance_Balance_Close": round(advance_balance_close, 2),
        "Final_Salary_Without_Special": round(final_without_special, 2),
        "Final_Salary_With_Special": round(final_with_special, 2),
        "Admin_Override_Extra_Leaves": "" if extra_leave_override is None else extra_leave_override,
        "Admin_Override_Special_Deduction": "" if special_override is None else special_override,
        "Admin_Override_Advance_Deduction": "" if advance_override is None else advance_override,
        "Payroll_Status": "Calculated" if extra_leave_override is None and special_override is None and advance_override is None else "Adjusted",
        "Approved_By": "",
        "Approved_At": "",
        "Locked": False,
        "Last_Recalculated_By": st.session_state.user["email"] if "user" in st.session_state else "",
        "Last_Recalculated_At": datetime.now().isoformat(timespec="seconds"),
    }
    return item, leave_log_rows


def reconcile_payroll_month(month_value, payroll_df=None):
    """Ensure selected payroll month has one row for every active employee.

    This protects against a profile recalculation accidentally leaving an active employee,
    such as Faizan, missing from Payroll/Salary Summary.
    """
    payroll = normalize_payroll_columns(payroll_df.copy() if payroll_df is not None else read_table("payroll_items"))
    employees = read_table("employees")
    if employees.empty:
        return payroll

    employees["Status"] = employees["Status"].fillna("Active").astype(str).str.strip()
    active = employees[employees["Status"].str.lower() == "active"].copy()
    if active.empty:
        return payroll

    try:
        yr, mon = parse_month_label(str(month_value))
    except Exception:
        return payroll

    if payroll.empty:
        existing_emp_ids = set()
    else:
        existing_emp_ids = set(payroll[payroll["Month"].astype(str) == str(month_value)]["Emp_ID"].astype(str))

    rows_to_add = []
    for _, emp in active.iterrows():
        emp_id = str(emp["Emp_ID"])
        eligible, _, _, _, _ = employee_service_window_for_month(emp, yr, mon)
        if not eligible:
            continue
        if emp_id not in existing_emp_ids:
            item, _ = calculate_employee_payroll(emp, yr, mon)
            if item is None:
                continue
            item["Payroll_Status"] = "Reconciled"
            rows_to_add.append(item)

    if rows_to_add:
        payroll = pd.concat([payroll, pd.DataFrame(rows_to_add)], ignore_index=True)
        add_audit(
            st.session_state.user["email"] if "user" in st.session_state else "system",
            "RECONCILE_PAYROLL_MONTH",
            f"{month_value}: restored missing employees {', '.join([str(x['Emp_ID']) for x in rows_to_add])}"
        )

    return normalize_payroll_columns(payroll)

def upsert_employee_payroll_row(payroll, item, month_value, emp_id):
    """Replace one employee payroll row and then reconcile missing active employees."""
    payroll = normalize_payroll_columns(payroll.copy())
    if not payroll.empty:
        payroll = payroll[~((payroll["Emp_ID"].astype(str) == str(emp_id)) & (payroll["Month"].astype(str) == str(month_value)))]
    payroll = pd.concat([payroll, pd.DataFrame([item])], ignore_index=True)
    payroll = reconcile_payroll_month(month_value, payroll)
    return normalize_payroll_columns(payroll)


def calculate_payroll(year, month, special_config=None):
    cleanse_data()
    employees = read_table("employees")
    employees = employees[employees["Status"].astype(str).str.lower() == "active"].copy()
    rows, logs = [], []
    for _, emp in employees.iterrows():
        eligible, _, _, _, _ = employee_service_window_for_month(emp, year, month)
        if not eligible:
            continue
        item, leave_logs = calculate_employee_payroll(emp, year, month, special_config=special_config)
        if item is None:
            continue
        rows.append(item)
        logs.extend(leave_logs)
    payroll_df = pd.DataFrame(rows)
    payroll_df = reconcile_payroll_month(month_label(year, month), payroll_df)
    return payroll_df, pd.DataFrame(logs)


def is_demo_mode():
    return bool(st.session_state.get("demo_mode", False))

def demo_mode_panel(location=""):
    c1, c2 = st.columns([2.6, 1])
    with c1:
        if is_demo_mode():
            st.success("Demo Mode is ON — technical clutter is hidden and business-friendly guidance is shown.")
        else:
            st.caption("Demo Mode is OFF — full operational details remain available.")
    with c2:
        st.toggle("Demo Mode", key="demo_mode", help="Turn ON during client walkthroughs to simplify screens and hide technical noise.")

def show_demo_tip(message):
    if is_demo_mode():
        st.info(message)




def set_action_focus(message, page=None):
    """Store a short guidance message so the next rerun clearly tells the user what happened."""
    st.session_state.action_focus_message = message
    if page:
        st.session_state.action_focus_page = page

def show_action_focus(default_message=None):
    msg = st.session_state.pop("action_focus_message", None)
    page = st.session_state.pop("action_focus_page", None)
    if msg:
        st.markdown(
            f"""
            <div class='ww-action-focus'>
                <div class='ww-action-focus-title'>Action completed / focus updated</div>
                <div class='ww-action-focus-text'>{msg}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif default_message:
        st.markdown(
            f"""
            <div class='ww-action-hint'>
                <b>Tip:</b> {default_message}
            </div>
            """,
            unsafe_allow_html=True,
        )

def focus_message_for_page(page_name):
    mapping = {
        "Dashboard": "Dashboard opened. Review monthly status and continue from Payroll Control Centre.",
        "Payroll Control Centre": "Payroll Control Centre opened. Start here to check readiness and continue the payroll flow.",
        "Salary Summary": "Salary Summary opened. Review employee-wise salary cards and then move to Payroll Approval.",
        "Leave": "Leave page opened. Fill the leave form below and click Save Leave.",
        "Holiday": "Holiday page opened. Add or review employee-specific holiday exclusions.",
        "Advance": "Advance page opened. Fill advance details and create the repayment schedule.",
        "Employee Profile": "Employee Profile opened. Select an employee for individual review or recalculation.",
        "Payroll Calculation": "Payroll Calculation opened. Select month and generate/recalculate payroll.",
        "Payroll Approval": "Payroll Approval opened. Use only after Salary Summary is reviewed.",
        "Employees": "Employees page opened. Add/edit active employees and supervisor mapping.",
        "Advance Master": "Advance Master opened. Review and safely reconcile backend-created advances.",
        "Advance Master": "Advance Master opened. Review and safely reconcile backend-created advances.",
        "Access Manager": "Access Manager opened. Manage login users, role cards and access permissions.",
        "Recovery": "Recovery opened. Roll back a selected section from saved backups.",
        "Technical Checks": "Technical Checks opened. Review storage and readiness only when needed.",
        "Demo Mode Guide": "Demo Mode Guide opened. Review demo/client mode behaviour.",
        "Recovery": "Recovery opened. Roll back a selected section from saved backups.",
        "Technical Checks": "Technical Checks opened. Review storage and readiness only when needed.",
        "Demo Mode Guide": "Demo Mode Guide opened. Review demo/client mode behaviour.",
        "Bulk Leave Upload": "Bulk Leave Upload opened. Upload the leave file, validate, then confirm bulk upload.",
        "System Health": "System Health opened. Review system status and storage health only when needed.",
        "Logs": "Logs opened. Review audit entries and activity history.",
    }
    return mapping.get(page_name, f"{page_name} opened. Continue with the highlighted section below.")





def render_selected_content_anchor():
    """Stable anchor placed immediately before the selected section content."""
    page_name = st.session_state.get("page", "selected section")
    st.markdown(
        f'<div id="ww-section-content-anchor" class="ww-content-anchor" aria-label="Loaded section: {page_name}"></div>',
        unsafe_allow_html=True,
    )

def trigger_auto_scroll_to_content():
    """V115.4: mobile-strengthened delayed auto-scroll after Streamlit rerun.

    Uses multiple scroll targets and retry attempts because Streamlit rerenders the
    parent document and mobile browsers can ignore the first scroll command.
    """
    if not st.session_state.get("pending_auto_scroll_to_content"):
        return

    st.session_state.pop("pending_auto_scroll_to_content", None)
    target_label = str(st.session_state.get("page", "selected section")).replace("'", "")
    components.html(
        f"""
        <script>
        (function() {{
            const targetId = "ww-section-content-anchor";
            const label = "{target_label}";
            let attempts = 0;
            const maxAttempts = 22;

            function parentDocument() {{
                try {{ return window.parent.document; }} catch (e) {{ return document; }}
            }}

            function parentWindow() {{
                try {{ return window.parent; }} catch (e) {{ return window; }}
            }}

            function findTarget() {{
                const doc = parentDocument();
                return doc.getElementById(targetId) || document.getElementById(targetId);
            }}

            function getScrollContainer(doc) {{
                return doc.querySelector('[data-testid="stAppViewContainer"]')
                    || doc.querySelector('.main')
                    || doc.scrollingElement
                    || doc.documentElement
                    || doc.body;
            }}

            function stableScroll() {{
                attempts += 1;
                const doc = parentDocument();
                const win = parentWindow();
                const target = findTarget();
                if (target) {{
                    const rect = target.getBoundingClientRect();
                    const currentY = win.pageYOffset || doc.documentElement.scrollTop || doc.body.scrollTop || 0;
                    const offset = 14;
                    const desiredY = Math.max(0, currentY + rect.top - offset);
                    try {{
                        win.scrollTo({{ top: desiredY, behavior: 'smooth' }});
                    }} catch(e) {{
                        win.scrollTo(0, desiredY);
                    }}
                    try {{
                        target.scrollIntoView({{ behavior: 'smooth', block: 'start', inline: 'nearest' }});
                    }} catch(e) {{
                        target.scrollIntoView(true);
                    }}
                    try {{
                        const container = getScrollContainer(doc);
                        if (container && container.scrollTo) {{
                            container.scrollTo({{ top: Math.max(0, target.offsetTop - offset), behavior: 'smooth' }});
                        }}
                    }} catch(e) {{}}
                    return;
                }}
                if (attempts < maxAttempts) {{
                    setTimeout(stableScroll, 140);
                }}
            }}

            setTimeout(stableScroll, 220);
            setTimeout(stableScroll, 650);
            setTimeout(stableScroll, 1100);
        }})();
        </script>
        """,
        height=0,
        scrolling=False,
    )


def page_heading_text(page_name):
    mapping = {
        "Dashboard": ("Dashboard", "Monthly status, quick actions and guided payroll readiness."),
        "Payroll Control Centre": ("Payroll Control Centre", "Start here to review readiness before payroll actions."),
        "Payroll Calculation": ("Payroll Calculation", "Generate or recalculate payroll after validating leave, advances and holidays."),
        "Salary Summary": ("Salary Summary", "Review employee-wise salary impact before approval."),
        "Payroll Approval": ("Payroll Approval", "Approve payroll only after the summary has been reviewed."),
        "Leave": ("Leave Management", "Record leave entries and review their payroll impact."),
        "Holiday": ("Holiday Management", "Maintain employee-specific holiday exclusions."),
        "Advance": ("Advance Entry", "Create advances and repayment schedules."),
        "Employee Profile": ("Employee Profile", "Review individual employee payroll and leave details."),
        "Employees": ("Employee Master", "Create and maintain employees, salary setup and supervisor mapping."),
        "Access Manager": ("Access Manager", "Manage users, roles, activation status and access permissions."),
        "Advance Master": ("Advance Master", "Reconcile and safely edit backend-created advance schedules."),
        "Bulk Leave Upload": ("Bulk Leave Upload", "Upload, validate and confirm monthly leave entries in bulk."),
        "Recovery": ("Recovery", "Restore one section from saved backups without resetting the full app."),
        "Technical Checks": ("Technical Checks", "Review storage and readiness only when troubleshooting."),
        "System Health": ("System Health", "Check table health, missing columns and readiness."),
        "Demo Mode Guide": ("Demo Mode Guide", "Control client-facing demo simplification."),
        "Logs": ("Logs", "Review audit and cleansing activity."),
    }
    return mapping.get(page_name, (page_name, "Continue with the selected WageWise section."))


def render_wagewise_header():
    st.markdown(
        f"""
        <div class='ww-app-shell'>
            <div class='ww-primary-heading'>WageWise <span class='build-marker'>Build {BUILD_VERSION}</span></div>
            <div class='ww-secondary-heading'>Salary Management System</div>
            <div class='ww-subheader'>Leave, advances, payroll, access control and readiness checks in one governed workspace.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_update(page_name):
    title, note = page_heading_text(page_name)
    st.markdown(
        f"""
        <div class='ww-section-update-wrap'>
            <div class='ww-section-update'>
                <div class='ww-section-update-kicker'>Section update</div>
                <div class='ww-section-update-title'>{title}</div>
                <div class='ww-section-update-note'>{note}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_heading(page_name):
    title, note = page_heading_text(page_name)
    st.markdown(
        f"""
        <div class='ww-page-heading-card'>
            <div class='ww-page-heading-primary'>{title}</div>
            <div class='ww-page-heading-secondary'>{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_nav_group(title, page_names, current_page, key_prefix):
    st.markdown(f"<div class='ww-nav-group-title'>{title}</div>", unsafe_allow_html=True)
    for page_name in page_names:
        is_active = current_page == page_name
        label = f"✓ {page_name}" if is_active else page_name
        if st.button(
            label,
            use_container_width=True,
            key=f"{key_prefix}_{title}_{page_name}",
            type="primary" if is_active else "secondary",
        ):
            st.session_state.page = page_name
            st.session_state.nav_compact_after_selection = True
            set_confirmation(f"{page_name} opened.", celebrate=False)
            st.session_state.scroll_target_note = f"You are now in {page_name}."
            st.session_state.pending_auto_scroll_to_content = True
            st.rerun()


def page_navigation():
    user = st.session_state.user
    auth_user = st.session_state.get("auth_user", user)
    demo_badge = " &nbsp;&nbsp; | &nbsp;&nbsp; <b>Demo Mode:</b> ON" if is_demo_mode() else ""
    display_name = auth_user.get("name", user.get("name", "User"))
    st.markdown(
        f"<div class='top-nav'><b>Logged in:</b> {display_name} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Current Role:</b> {user['role']}{demo_badge}</div>",
        unsafe_allow_html=True,
    )

    if user["role"] == "Supervisor":
        nav_groups = {"Supervisor": ["Dashboard"]}
    else:
        nav_groups = {
            "Daily Work": ["Dashboard", "Leave", "Holiday", "Advance", "Employee Profile"],
            "Payroll Flow": ["Payroll Control Centre", "Payroll Calculation", "Salary Summary", "Payroll Approval"],
            "Setup & Controls": ["Employees", "Access Manager", "Advance Master", "Bulk Leave Upload"],
            "Recovery & Technical": ["Recovery", "Technical Checks", "System Health", "Demo Mode Guide", "Logs"],
        }

    pages = [p for group in nav_groups.values() for p in group]
    if "page" not in st.session_state or st.session_state.page not in pages:
        st.session_state.page = pages[0]

    def _render_full_navigation(key_suffix="accordion"):
        if user["role"] == "Supervisor":
            with st.container(border=True):
                render_nav_group("Supervisor", nav_groups["Supervisor"], st.session_state.page, f"nav_supervisor_{key_suffix}")
        else:
            left_col, right_col = st.columns([1.0, 1.0], gap="medium")
            with left_col:
                with st.container(border=True):
                    render_nav_group("Daily Work", nav_groups["Daily Work"], st.session_state.page, f"nav_{key_suffix}")
                with st.container(border=True):
                    render_nav_group("Payroll Flow", nav_groups["Payroll Flow"], st.session_state.page, f"nav_{key_suffix}")
            with right_col:
                with st.container(border=True):
                    render_nav_group("Setup & Controls", nav_groups["Setup & Controls"], st.session_state.page, f"nav_{key_suffix}")
                with st.container(border=True):
                    render_nav_group("Recovery & Technical", nav_groups["Recovery & Technical"], st.session_state.page, f"nav_{key_suffix}")

    # V115.4: keep one notification only. The page heading below shows the active section.
    # Delayed JS auto-scroll is attempted after rerun, while accordion remains the fallback.
    with st.expander("Open / change section", expanded=False):
        st.markdown(
            "<div class='ww-nav-note'>Select a section. The selected area opens below and auto-scroll will try to bring it into view.</div>",
            unsafe_allow_html=True,
        )
        _render_full_navigation("accordion")

    allowed_roles_for_login = user_allowed_roles(auth_user)
    show_switch_role = len(allowed_roles_for_login) > 1

    if show_switch_role:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c2:
            if st.button("Switch Role", use_container_width=True):
                st.session_state.user = None
                st.session_state.access_role = None
                st.session_state.page = "Role Selection"
                st.rerun()
        with c3:
            if st.button("Logout", use_container_width=True):
                add_audit(auth_user.get("email", user.get("email", "")), "LOGOUT", "User logged out")
                wagewise_logout()
    else:
        c1, c3 = st.columns([4, 1])
        with c3:
            if st.button("Logout", use_container_width=True):
                add_audit(auth_user.get("email", user.get("email", "")), "LOGOUT", "User logged out")
                wagewise_logout()

    return st.session_state.page


def supervisor_dashboard_page():
    st.subheader("Supervisor Quick Actions")
    st.caption("Only two actions are available for fast daily mobile usage.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class='quick-card'>
            <div class='quick-title'>Mark Leave</div>
            <div class='quick-help'>Select employee, leave type and remarks.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("➕ Mark Leave", use_container_width=True):
            st.session_state.quick_action = "leave"
            set_action_focus("Mark Leave selected. The leave form is now ready below — fill employee, leave type and save.", page="Supervisor Mark Leave")
            st.rerun()

    with c2:
        st.markdown("""
        <div class='quick-card'>
            <div class='quick-title'>Add Advance</div>
            <div class='quick-help'>Record advance and repayment schedule.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("💰 Add Advance", use_container_width=True):
            st.session_state.quick_action = "advance"
            set_action_focus("Add Advance selected. The advance form is now ready below — fill amount and repayment schedule.", page="Supervisor Add Advance")
            st.rerun()

    st.divider()
    action = st.session_state.get("quick_action", "")

    if action == "leave":
        st.markdown("### Mark Leave")
        st.success("You are now in Mark Leave. Complete the form below and click Save Leave.")
        quick_leave_form()
    elif action == "advance":
        st.markdown("### Add Advance")
        st.success("You are now in Add Advance. Complete the form below and click Create Advance & Schedule.")
        quick_advance_form()
    else:
        st.info("Choose one action above.")

    st.markdown("### Recent Entries")
    leaves = read_table("leave_entries")
    advances = read_table("advance_cases")
    user_email = st.session_state.user["email"]

    recent_leaves = leaves[leaves["Supervisor"].astype(str).str.lower() == user_email.lower()].tail(5) if (not leaves.empty and "Supervisor" in leaves.columns) else leaves
    recent_advances = advances[advances["Created_By"].astype(str).str.lower() == user_email.lower()].tail(5) if (not advances.empty and "Created_By" in advances.columns) else advances

    tab1, tab2 = st.tabs(["Recent Leaves", "Recent Advances"])
    with tab1:
        st.dataframe(recent_leaves, use_container_width=True)
    with tab2:
        st.dataframe(recent_advances, use_container_width=True)


def quick_leave_form():
    employees = active_employees_for_user()
    choices = employee_choices(employees)
    if not choices:
        st.info("No active employees available.")
        return

    with st.form("quick_leave_form"):
        att_date = st.date_input("Leave date", value=date.today(), max_value=date.today())
        employee_pick = st.selectbox("Employee", choices)
        leave_type = st.selectbox("Leave type", list(LEAVE_UNITS.keys()))
        remarks = st.text_area("Remarks", placeholder="Mandatory for uninformed leave.")
        submitted = st.form_submit_button("Save Leave")
    if submitted:
        lock_month = month_label(att_date.year, att_date.month)
        if is_month_locked(lock_month):
            st.error(f"Payroll for {lock_month} is approved and locked. Leave changes are not allowed.")
            return
        if leave_type == "Leave - Uninformed" and not remarks.strip():
            st.error("Remarks are mandatory for Uninformed Leave.")
            return
        emp_id = extract_emp_id(employee_pick)
        df = read_table("leave_entries")
        key_exists = ((df["Date"].astype(str) == str(att_date)) & (df["Emp_ID"].astype(str) == emp_id)).any()
        if key_exists:
            st.error("Duplicate blocked: this employee already has a leave entry for this date.")
            return
        new_leave_row = {
            "Date": str(att_date),
            "Emp_ID": emp_id,
            "Leave_Type": leave_type,
            "Remarks": remarks,
            "Supervisor": st.session_state.user["email"],
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "Status": "Approved",
        }
        for col in new_leave_row:
            if col not in df.columns:
                df[col] = ""
        df.loc[len(df), list(new_leave_row.keys())] = list(new_leave_row.values())
        write_table("leave_entries", df)
        add_audit(st.session_state.user["email"], "SUPERVISOR_QUICK_SAVE_LEAVE", f"{att_date} {emp_id} {leave_type}")
        set_confirmation("Leave saved successfully.", celebrate=True)
        st.session_state.quick_action = ""
        st.rerun()


def quick_advance_form():
    employees = active_employees_for_user()
    choices = employee_choices(employees)
    if not choices:
        st.info("No active employees available.")
        return

    with st.form("quick_advance_form"):
        employee_pick = st.selectbox("Employee", choices)
        adv_date = st.date_input("Date of giving advance", value=date.today())
        amount = st.number_input("Amount given", min_value=0.0, step=500.0)
        st.caption("Example: ₹4000 taken, ₹2000 first month, remaining over 2 months = ₹1000/month.")
        c1, c2, c3 = st.columns(3)
        start_month = c1.selectbox("Refund start month", list(range(1, 13)), index=date.today().month - 1, format_func=lambda m: calendar.month_name[m])
        start_year = c2.number_input("Refund start year", min_value=2020, max_value=2100, value=date.today().year, step=1)
        first_deduction = c3.number_input("First month deduction", min_value=0.0, step=500.0)
        remaining_months = st.number_input("Remaining months after first deduction", min_value=0, step=1)
        remarks = st.text_area("Advance remarks")
        submitted = st.form_submit_button("Create Advance")
    if submitted:
        emp_id = extract_emp_id(employee_pick)
        if is_month_locked(month_label(int(start_year), int(start_month))):
            st.error("Refund start month is already approved and locked. Advance schedule cannot start in a locked month.")
            return
        if amount <= 0:
            st.error("Advance amount must be greater than 0.")
            return
        if first_deduction > amount:
            st.error("First month deduction cannot be greater than amount given.")
            return
        if first_deduction <= 0 and int(remaining_months) <= 0:
            st.error("Please define at least one deduction: first month deduction or remaining months.")
            return
        cases = read_table("advance_cases")
        schedule = read_table("advance_schedule")
        advance_id = f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cases.loc[len(cases)] = [advance_id, emp_id, str(adv_date), amount, month_label(int(start_year), int(start_month)), first_deduction, remaining_months, "Open", remarks, st.session_state.user["email"], datetime.now().isoformat(timespec="seconds")]
        new_sched = rebuild_schedule_rows_for_advance(advance_id, emp_id, amount, int(start_year), int(start_month), first_deduction, remaining_months, updated_by=st.session_state.user["email"])
        if not new_sched.empty:
            schedule = pd.concat([schedule, new_sched], ignore_index=True)
        b1, b2 = safe_write_advance_tables(cases, schedule, label="before_quick_advance_create", selected_advance_id=advance_id)
        add_audit(st.session_state.user["email"], "SUPERVISOR_QUICK_CREATE_ADVANCE", f"{advance_id} {emp_id} ₹{amount}; backups: {b1}, {b2}")
        set_confirmation("Advance and schedule created successfully.", celebrate=True)
        st.session_state.quick_action = ""
        st.rerun()



def BACKUP_DIR():
    p = APP_DIR / "backups"
    p.mkdir(exist_ok=True)
    return p

def backup_table(name, label="backup"):
    """Create a timestamped CSV backup of a table and return backup path."""
    try:
        df = read_table(name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = BACKUP_DIR() / f"{name}_{label}_{ts}.csv"
        df.to_csv(path, index=False)
        return str(path)
    except Exception as e:
        return f"Backup failed for {name}: {e}"



def list_section_backups(table_name):
    """List local CSV backups for a table, newest first."""
    try:
        backup_dir = BACKUP_DIR()
        files = sorted(backup_dir.glob(f"{table_name}_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files
    except Exception:
        return []

def restore_table_from_backup(table_name, backup_path):
    """Restore one table from a selected backup without touching other sections."""
    backup_path = Path(backup_path)
    if not backup_path.exists():
        return False, "Backup file not found."
    try:
        backup_table(table_name, "before_section_rollback")
        df = pd.read_csv(backup_path)
        df = normalize_required_columns(table_name, df)
        write_table(table_name, df, allow_empty_restore=True)
        clear_db_table_cache(table_name)
        return True, f"{table_name} restored from {backup_path.name}."
    except Exception as e:
        return False, str(e)

def section_rollback_panel():
    st.markdown("### Section Rollback")
    st.caption("Restore one section from a saved backup. This does not reset the whole app.")
    section_map = {
        "Advances - cases": "advance_cases",
        "Advances - repayment schedule": "advance_schedule",
        "Leave entries": "leave_entries",
        "Access Manager": "users",
        "Employees": "employees",
        "Payroll rows": "payroll_items",
    }
    section_label = st.selectbox("Section to rollback", list(section_map.keys()))
    table_name = section_map[section_label]
    backups = list_section_backups(table_name)
    if not backups:
        st.warning("No local backups found for this section yet. Backups are created before safe corrections and guarded writes.")
        return
    selected = st.selectbox("Select backup point", backups, format_func=lambda p: f"{p.name} · {datetime.fromtimestamp(p.stat().st_mtime).strftime('%d %b %Y, %I:%M %p')}")
    try:
        preview = pd.read_csv(selected).head(20)
        st.caption(f"Preview: first 20 rows from {selected.name}")
        st.dataframe(preview, use_container_width=True, height=240)
    except Exception as e:
        st.warning(f"Could not preview backup: {e}")
    confirm = st.checkbox(f"I confirm rollback of only {section_label}")
    if st.button("Rollback selected section", use_container_width=True, type="primary"):
        if not confirm:
            st.error("Please tick confirmation before rollback.")
            return
        ok, msg = restore_table_from_backup(table_name, selected)
        if ok:
            add_audit(st.session_state.user["email"], "SECTION_ROLLBACK", f"{section_label}: {selected.name}")
            set_confirmation(msg, celebrate=True)
            st.rerun()
        else:
            st.error(f"Rollback failed: {msg}")


def backup_advance_tables(label="advance_correction"):
    """Backup advance tables before any admin correction."""
    p1 = backup_table("advance_cases", label)
    p2 = backup_table("advance_schedule", label)
    return p1, p2

def rebuild_schedule_rows_for_advance(advance_id, emp_id, amount, start_year, start_month, first_deduction, remaining_months, updated_by=""):
    """Return repayment schedule rows for one advance without writing whole table."""
    first_deduction = min(float(first_deduction), float(amount))
    remaining_amount = max(0, float(amount) - first_deduction)
    rows = []
    if first_deduction > 0:
        rows.append({
            "Advance_ID": advance_id,
            "Emp_ID": emp_id,
            "Deduction_Month": month_label(start_year, start_month),
            "Scheduled_Deduction": round(first_deduction, 2),
            "Admin_Updated_Deduction": "",
            "Final_Deduction": round(first_deduction, 2),
            "Status": "Open",
            "Updated_By": updated_by,
            "Updated_At": datetime.now().isoformat(timespec="seconds"),
        })
    if int(remaining_months) > 0 and remaining_amount > 0:
        per_month = round(remaining_amount / int(remaining_months), 2)
        running_total = 0.0
        for i in range(int(remaining_months)):
            y2, m2 = add_months(start_year, start_month, i + 1)
            amt = per_month
            if i == int(remaining_months) - 1:
                amt = round(remaining_amount - running_total, 2)
            running_total += amt
            rows.append({
                "Advance_ID": advance_id,
                "Emp_ID": emp_id,
                "Deduction_Month": month_label(y2, m2),
                "Scheduled_Deduction": round(amt, 2),
                "Admin_Updated_Deduction": "",
                "Final_Deduction": round(amt, 2),
                "Status": "Open",
                "Updated_By": updated_by,
                "Updated_At": datetime.now().isoformat(timespec="seconds"),
            })
    return pd.DataFrame(rows, columns=REQUIRED_FILES["advance_schedule"])




def advance_integrity_report(cases, schedule):
    """Return lightweight safety checks for advance master/schedule consistency."""
    issues = []
    cases = normalize_required_columns("advance_cases", cases.copy()) if cases is not None else pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
    schedule = normalize_required_columns("advance_schedule", schedule.copy()) if schedule is not None else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])
    if not cases.empty and "Advance_ID" in cases.columns:
        duplicate_cases = cases[cases["Advance_ID"].astype(str).duplicated(keep=False)]
        if not duplicate_cases.empty:
            issues.append(f"Duplicate Advance_ID found in master: {duplicate_cases['Advance_ID'].astype(str).nunique()} duplicate ID(s).")
    if not schedule.empty and "Advance_ID" in schedule.columns and not cases.empty and "Advance_ID" in cases.columns:
        case_ids = set(cases["Advance_ID"].astype(str))
        orphan_schedule = schedule[~schedule["Advance_ID"].astype(str).isin(case_ids)]
        if not orphan_schedule.empty:
            issues.append(f"Orphan schedule rows found without master advance: {len(orphan_schedule)} row(s).")
    if not cases.empty and "Advance_ID" in cases.columns and not schedule.empty and "Advance_ID" in schedule.columns:
        for adv_id in cases["Advance_ID"].astype(str).unique():
            case_rows = cases[cases["Advance_ID"].astype(str) == adv_id]
            sched_rows = schedule[schedule["Advance_ID"].astype(str) == adv_id]
            amount = safe_float(case_rows.iloc[0].get("Amount_Given", 0)) if not case_rows.empty else 0.0
            sched_total = safe_numeric_series(sched_rows.get("Final_Deduction", pd.Series(dtype=float))).sum() if not sched_rows.empty else 0.0
            if amount > 0 and sched_total - amount > 0.01:
                issues.append(f"Advance {adv_id}: schedule total exceeds amount by ₹{sched_total-amount:,.2f}.")
    return issues


def validate_advance_write_safety(old_cases, new_cases, old_schedule, new_schedule, selected_advance_id=None):
    """Block advance writes that could blank the master/schedule or alter unrelated master rows."""
    old_cases = normalize_required_columns("advance_cases", old_cases.copy()) if old_cases is not None else pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
    new_cases = normalize_required_columns("advance_cases", new_cases.copy()) if new_cases is not None else pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
    old_schedule = normalize_required_columns("advance_schedule", old_schedule.copy()) if old_schedule is not None else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])
    new_schedule = normalize_required_columns("advance_schedule", new_schedule.copy()) if new_schedule is not None else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])

    if len(old_cases) > 0 and new_cases.empty:
        raise ValueError("Advance safety blocked this save because it would blank the Advance Cases table.")
    if len(old_schedule) > 0 and new_schedule.empty:
        raise ValueError("Advance safety blocked this save because it would blank the Advance Schedule table.")
    if selected_advance_id and "Advance_ID" in old_cases.columns and "Advance_ID" in new_cases.columns:
        adv = str(selected_advance_id)
        old_other = old_cases[old_cases["Advance_ID"].astype(str) != adv].reset_index(drop=True)
        new_other = new_cases[new_cases["Advance_ID"].astype(str) != adv].reset_index(drop=True)
        # Compare unrelated master rows after aligning to strings; selected row may change, others must not disappear.
        if len(new_other) < len(old_other):
            raise ValueError("Advance safety blocked this save because unrelated advance master rows would be removed.")
        missing_ids = set(old_other["Advance_ID"].astype(str)) - set(new_other["Advance_ID"].astype(str))
        if missing_ids:
            raise ValueError(f"Advance safety blocked this save because unrelated Advance IDs would be lost: {', '.join(sorted(missing_ids)[:5])}.")
    issues = advance_integrity_report(new_cases, new_schedule)
    severe = [i for i in issues if "exceeds amount" in i or "Duplicate Advance_ID" in i]
    if severe:
        raise ValueError("Advance safety blocked this save: " + " | ".join(severe[:3]))
    return True


def safe_write_advance_tables(new_cases, new_schedule, label="advance_safe_write", selected_advance_id=None):
    """Write both advance tables only after backup + integrity guardrails."""
    old_cases = read_table("advance_cases")
    old_schedule = read_table("advance_schedule")
    b1, b2 = backup_advance_tables(label)
    validate_advance_write_safety(old_cases, new_cases, old_schedule, new_schedule, selected_advance_id=selected_advance_id)
    write_table("advance_cases", normalize_required_columns("advance_cases", new_cases).reset_index(drop=True))
    write_table("advance_schedule", normalize_required_columns("advance_schedule", new_schedule).reset_index(drop=True))
    return b1, b2


def backup_leave_table(label="leave_correction"):
    """Backup leave_entries before any admin leave correction."""
    return backup_table("leave_entries", label)


def month_readiness(month_value):
    employees = read_table("employees")
    leaves = read_table("leave_entries")
    cases = read_table("advance_cases")
    schedule = read_table("advance_schedule")
    payroll = normalize_payroll_columns(read_table("payroll_items"))

    active = employees[employees["Status"].astype(str).str.lower() == "active"] if (not employees.empty and "Status" in employees.columns) else employees
    yr, mon = parse_month_label(str(month_value))
    start_dt = pd.Timestamp(year=yr, month=mon, day=1)
    end_dt = pd.Timestamp(year=yr, month=mon, day=calendar.monthrange(yr, mon)[1])

    leaves_in_month = pd.DataFrame()
    if not leaves.empty and "Date" in leaves.columns:
        temp = leaves.copy()
        temp["Date_dt"] = parse_app_date_series(temp["Date"])
        leaves_in_month = temp[(temp["Date_dt"] >= start_dt) & (temp["Date_dt"] <= end_dt)]

    schedule_in_month = schedule[schedule["Deduction_Month"].astype(str) == str(month_value)] if (not schedule.empty and "Deduction_Month" in schedule.columns) else pd.DataFrame()
    payroll_in_month = payroll[payroll["Month"].astype(str) == str(month_value)] if (not payroll.empty and "Month" in payroll.columns) else pd.DataFrame()

    locked = False
    if not payroll_in_month.empty and "Locked" in payroll_in_month.columns:
        locked = payroll_in_month["Locked"].astype(str).str.lower().isin(["true", "1", "yes"]).any()

    return {
        "month": month_value,
        "active_employees": len(active),
        "leave_rows": len(leaves_in_month),
        "advance_cases": len(cases),
        "advance_schedule_rows": len(schedule_in_month),
        "payroll_rows": len(payroll_in_month),
        "payroll_generated": len(payroll_in_month) > 0,
        "locked": locked,
        "storage": "Cloud Storage" if db_enabled() else "CSV",
    }

def readiness_status(value, target=1):
    try:
        return "Done" if int(value) >= target else "Pending"
    except Exception:
        return "Pending"

def render_month_readiness(month_value):
    info = month_readiness(month_value)
    st.markdown("#### Month Readiness Check")
    cols = st.columns(5)
    cards = [
        ("Employees", info["active_employees"], "Done" if info["active_employees"] > 0 else "Pending"),
        ("Leaves", info["leave_rows"], "Done" if info["leave_rows"] > 0 else "No leaves"),
        ("Advance schedules", info["advance_schedule_rows"], "Done" if info["advance_schedule_rows"] > 0 else "No schedules"),
        ("Payroll", info["payroll_rows"], "Done" if info["payroll_generated"] else "Pending"),
        ("Locked", "Yes" if info["locked"] else "No", "Locked" if info["locked"] else "Open"),
    ]
    for col, (label, value, status) in zip(cols, cards):
        col.metric(label, value, status)
    st.caption(f"Storage: {info['storage']} | Month: {month_value}")
    return info

def payroll_control_centre_page():
    st.subheader("Payroll Control Centre")
    demo_mode_panel("payroll_control_centre")
    st.caption("Control Centre is a guided status page. It does not replace Payroll or Payroll Approval; it tells users what is ready and where to go next.")
    show_demo_tip("Recommended demo flow: verify readiness → generate payroll → review salary summary → approve/lock.")
    with st.expander("How this relates to Payroll and Payroll Approval", expanded=False):
        st.markdown("""
        **Payroll Control Centre** = command/checklist page. Use it to see readiness and navigate.

        **Payroll Calculation** = calculation page. Use it to generate or recalculate salary for the selected month.

        **Payroll Approval** = final control page. Use it after review to approve and lock payroll.

        Recommended flow: **Control Centre → Payroll Calculation → Salary Summary → Payroll Approval**.
        """)

    today = date.today()
    c1, c2 = st.columns(2)
    year = c1.number_input("Year", min_value=2020, max_value=2100, value=today.year, step=1, key="pcc_year")
    month = c2.selectbox("Month", list(range(1, 13)), index=today.month - 1, format_func=lambda m: calendar.month_name[m], key="pcc_month")
    selected_month = month_label(int(year), int(month))

    info = render_month_readiness(selected_month)
    render_monthly_close_checklist(selected_month)
    render_next_step("Use Payroll Calculation after inputs are reviewed, then review Salary Summary before Payroll Approval.")

    st.markdown("#### Guided Monthly Flow")
    flow = [
        ("1. Employees Ready", "Active employee master available", "Employees", info["active_employees"] > 0),
        ("2. Leaves Uploaded", "Leave rows detected for selected month", "Leave", info["leave_rows"] > 0),
        ("3. Advances Ready", "Advance schedule rows detected for selected month", "Advance", info["advance_schedule_rows"] > 0),
        ("4. Payroll Calculated", "Payroll rows available for selected month", "Payroll Calculation", info["payroll_generated"]),
        ("5. Review & Lock", "Approve payroll after review", "Payroll Approval", info["locked"]),
    ]
    for title, desc, go_page, done in flow:
        c_status, c_text, c_action = st.columns([0.8, 3, 1.2])
        c_status.markdown("✅" if done else "⚠️")
        c_text.markdown(f"**{title}**  \n{desc}")
        if c_action.button(f"Go to {go_page}", key=f"pcc_go_{go_page}", use_container_width=True):
            st.session_state.page = go_page
            set_action_focus(focus_message_for_page(go_page), page=go_page)
            st.rerun()

def explain_salary_row(row):
    name = row.get("Name", row.get("Emp_ID", "Employee"))
    total = row.get("Total Pay", row.get("Monthly_Salary", ""))
    daily = row.get("Daily Wage", row.get("Daily_Wage", ""))
    leaves = row.get("Total Leaves Taken", row.get("Leaves Taken", row.get("Leave_Units", "")))
    leave_cost = row.get("Leave Deduction Cost on extra leaves", row.get("Leave Deduction Cost", row.get("Leave_Deduction_Cost", "")))
    total_adv = row.get("Total Advance", "")
    adv_ded = row.get("Deduction for the Month", row.get("Advance_Deduction", ""))
    net = row.get("Net Salary to be Paid", row.get("Final_Salary_With_Special", ""))
    return f"{name}: Total Pay {total}, Daily Wage {daily}, Total Leaves Taken {leaves}, Leave Deduction Cost on extra leaves {leave_cost}, Total Advance {total_adv}, Monthly Advance Deduction {adv_ded}, Net Salary {net}."



def safe_latest_timestamp(df, columns=None):
    if df is None or df.empty:
        return "No update yet"
    columns = columns or ["Timestamp", "Updated_At", "Approved_At", "Last_Recalculated_At"]
    for col in columns:
        if col in df.columns:
            vals = pd.to_datetime(df[col], errors="coerce").dropna()
            if not vals.empty:
                return vals.max().strftime("%d %b %Y, %I:%M %p")
    return "No update yet"

def render_next_step(message):
    st.markdown(
        f"""
        <div class="ww-next-step">
            <b>Next step:</b> {message}
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_monthly_close_checklist(month_value):
    st.markdown("#### Monthly Close Checklist")
    info = month_readiness(month_value)
    checklist = [
        ("Employees reviewed", info["active_employees"] > 0),
        ("Leaves reviewed", info["leave_rows"] >= 0),
        ("Advances reviewed", info["advance_cases"] >= 0),
        ("Payroll generated", info["payroll_generated"]),
        ("Salary Summary reviewed", info["payroll_generated"]),
        ("Approval / lock ready", True),
    ]
    for label, done in checklist:
        st.write(("✅ " if done else "⬜ ") + label)

def create_payroll_snapshot(month_value):
    try:
        snap_dir = BACKUP_DIR() / f"payroll_snapshot_{str(month_value).replace('-', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        snap_dir.mkdir(parents=True, exist_ok=True)
        for name in ["payroll_items", "leave_entries", "advance_schedule", "advance_cases", "employees"]:
            df = read_table(name)
            df.to_csv(snap_dir / f"{name}.csv", index=False)
        return str(snap_dir)
    except Exception as e:
        return f"Snapshot failed: {e}"


def dashboard_page():
    if st.session_state.user["role"] == "Supervisor":
        supervisor_dashboard_page()
        return
    demo_mode_panel("dashboard")
    show_demo_tip("Client walkthrough tip: Start from Payroll Control Centre, then open Salary Summary for the final business view.")
    employees = read_table("employees")
    leaves = read_table("leave_entries")
    schedules = read_table("advance_schedule")
    payroll = read_table("payroll_items")

    active = employees[employees["Status"].astype(str).str.lower() == "active"] if (not employees.empty and "Status" in employees.columns) else employees
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Employees", len(active))
    c2.metric("Leave Entries", len(leaves))
    open_adv = schedules[schedules["Status"].astype(str).str.lower() == "open"] if not schedules.empty else schedules
    c3.metric("Open Advance Schedules", len(open_adv))
    if not payroll.empty and "Final_Salary_With_Special" in payroll:
        total = pd.to_numeric(payroll["Final_Salary_With_Special"], errors="coerce").fillna(0).sum()
    else:
        total = 0
    c4.metric("Latest Payroll Total", f"₹{total:,.0f}")

    st.subheader("Client Confidence View")
    current_month = month_label(date.today().year, date.today().month)
    render_month_readiness(current_month)
    st.markdown("#### Last Updated")
    u1, u2, u3 = st.columns(3)
    u1.info(f"Leaves: {safe_latest_timestamp(leaves)}")
    u2.info(f"Advances: {safe_latest_timestamp(schedules)}")
    u3.info(f"Payroll: {safe_latest_timestamp(payroll)}")
    render_next_step("Open Payroll Control Centre to continue the monthly payroll process.")
    if st.button("Open Payroll Control Centre", use_container_width=True, type="primary"):
        st.session_state.page = "Payroll Control Centre"
        st.rerun()

    st.subheader("Recent Leave Updates")
    st.dataframe(leaves.tail(8), use_container_width=True)

    st.subheader("Recent Payroll")
    st.dataframe(payroll.tail(8), use_container_width=True)



def summarize_leave_rows(df, month_value=None):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Emp_ID", "Rows", "Units"])
    temp = normalize_leave_entries_for_payroll(df.copy()) if "normalize_leave_entries_for_payroll" in globals() else df.copy()
    if month_value:
        try:
            yr, mon = parse_month_label(str(month_value))
            start_dt = pd.Timestamp(year=yr, month=mon, day=1)
            end_dt = pd.Timestamp(year=yr, month=mon, day=calendar.monthrange(yr, mon)[1])
            temp["Date_dt"] = parse_app_date_series(temp["Date"])
            temp = temp[(temp["Date_dt"] >= start_dt) & (temp["Date_dt"] <= end_dt)]
        except Exception:
            pass
    if temp.empty:
        return pd.DataFrame(columns=["Emp_ID", "Rows", "Units"])
    temp["Units"] = temp["Leave_Type"].apply(lambda x: float(LEAVE_UNITS.get(normalize_leave_type(x), 0)))
    return temp.groupby("Emp_ID", as_index=False).agg(Rows=("Date", "count"), Units=("Units", "sum"))


def bulk_leave_upload_page():
    st.subheader("Bulk Leave Upload - One Time Exercise")
    st.caption("Upload multiple leave records in one CSV. This is intended for one-time data migration or cleanup.")

    if st.session_state.get("bulk_upload_message"):
        st.success(st.session_state.bulk_upload_message)
        st.caption("Completion animation was triggered after upload. If your browser blocks animations, this message confirms completion.")
        if st.session_state.get("last_bulk_leave_backup_path"):
            st.info(f"Backup available for undo: {st.session_state.last_bulk_leave_backup_path}")
            if st.button("Undo Last Bulk Upload", use_container_width=True, key="undo_last_bulk_upload"):
                try:
                    backup_df = pd.read_csv(st.session_state.last_bulk_leave_backup_path)
                    write_table("leave_entries", backup_df)
                    msg = "Last bulk upload undone. Leave entries restored from backup."
                    st.session_state.bulk_upload_message = msg
                    set_confirmation(msg, celebrate=True)
                    st.rerun()
                except Exception as e:
                    st.error(f"Undo failed: {e}")
        if st.session_state.get("last_bulk_upload_summary"):
            st.markdown("#### Last saved upload summary")
            st.dataframe(pd.DataFrame(st.session_state.last_bulk_upload_summary), use_container_width=True, height=min(260, 80 + len(st.session_state.last_bulk_upload_summary) * 35))

    if st.session_state.user["role"] != "Tech":
        st.warning("Open the System Admin role to use bulk upload.")
        return

    st.markdown("#### Required CSV columns")
    st.code("Date, Emp_ID, Leave_Type, Status, Remarks")

    template = """Date,Emp_ID,Leave_Type,Status,Remarks
2026-04-01,E_Gudiya,Leave - Full Day,Approved,Sample full day leave
2026-04-02,E_Asha,Leave - Half Day,Approved,Sample half day leave
2026-04-03,E_Pooja,Leave - Uninformed,Approved,Sample uninformed leave
2026-04-04,E_Kiran,Leave - Collaborative,Approved,Sample collaborative leave
"""
    st.download_button(
        "Download Bulk Leave Upload Template",
        template.encode("utf-8"),
        file_name="bulk_leave_upload_template.csv",
        mime="text/csv",
        on_click=download_ack,
        args=("Bulk leave upload template",)
    )

    st.markdown("#### Allowed Leave_Type values")
    st.write(", ".join(LEAVE_UNITS.keys()))

    uploaded = st.file_uploader("Upload completed CSV file", type=["csv"])
    if uploaded is None:
        st.info("Download the template, fill it, then upload it here.")
        return

    try:
        upload_df = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    # Clean column names to avoid hidden spaces from Excel.
    upload_df.columns = [str(c).strip() for c in upload_df.columns]

    required_cols = ["Date", "Emp_ID", "Leave_Type", "Status", "Remarks"]
    missing = [c for c in required_cols if c not in upload_df.columns]
    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}")
        return

    total_uploaded = len(upload_df)
    st.info(f"Rows detected in uploaded file: {total_uploaded}")

    upload_mode = st.radio(
        "Upload mode",
        ["Replace entire leave data for uploaded month", "Append / replace matching rows"],
        horizontal=False,
        index=0,
        help="For demo and one-time migration, keep 'Replace entire leave data for uploaded month'. It ensures saved rows match the uploaded file for that month.",
        key="bulk_upload_mode_v74"
    )
    st.warning("After validation, the final upload button appears directly below the validation summary. Large previews are collapsed to keep the page fast.")

    employees = read_table("employees")
    active_emp_ids = set(employees[employees["Status"].astype(str).str.lower() == "active"]["Emp_ID"].astype(str))
    valid_leave_types = set(LEAVE_UNITS.keys())

    # Performance: read payroll lock data once instead of calling is_month_locked() for every uploaded row.
    payroll_for_locks = normalize_payroll_columns(read_table("payroll_items"))
    locked_months = set()
    if not payroll_for_locks.empty and "Month" in payroll_for_locks.columns and "Locked" in payroll_for_locks.columns:
        locked_rows = payroll_for_locks[payroll_for_locks["Locked"].astype(str).str.lower().isin(["true", "1", "yes"])]
        locked_months = set(locked_rows["Month"].astype(str))

    clean_rows = []
    error_rows = []

    with st.spinner("Validating uploaded file..."):
        for idx, row in upload_df.iterrows():
            row_num = idx + 2
            raw_date = row.get("Date", "")
            emp_id = normalize_emp_id_value(row.get("Emp_ID", ""))
            leave_type = normalize_leave_type(row.get("Leave_Type", ""))
            status = str(row.get("Status", "")).strip() if not pd.isna(row.get("Status", "")) else "Approved"
            remarks = "" if pd.isna(row.get("Remarks", "")) else str(row.get("Remarks", "")).strip()

            parsed_date = parse_app_date_value(raw_date)
            if pd.isna(parsed_date):
                error_rows.append({"Row": row_num, "Issue": "Invalid Date", "Value": raw_date})
                continue
            leave_date = parsed_date.date()

            if emp_id not in active_emp_ids:
                error_rows.append({"Row": row_num, "Issue": "Invalid or inactive Emp_ID", "Value": emp_id})
                continue

            if leave_type not in valid_leave_types:
                error_rows.append({"Row": row_num, "Issue": "Invalid Leave_Type", "Value": row.get("Leave_Type", "")})
                continue

            if leave_type == "Leave - Uninformed" and not remarks:
                error_rows.append({"Row": row_num, "Issue": "Remarks mandatory for Uninformed Leave", "Value": emp_id})
                continue

            lock_month = month_label(leave_date.year, leave_date.month)
            if lock_month in locked_months:
                error_rows.append({"Row": row_num, "Issue": f"Month locked: {lock_month}", "Value": emp_id})
                continue

            clean_rows.append({
                "Date": str(leave_date),
                "Emp_ID": emp_id,
                "Leave_Type": leave_type,
                "Status": status or "Approved",
                "Remarks": remarks,
                "Supervisor": st.session_state.user["email"],
                "Timestamp": datetime.now().isoformat(timespec="seconds"),
            })

    st.markdown("#### Validation Result")
    c1, c2, c3 = st.columns(3)
    c1.metric("Uploaded rows", total_uploaded)
    c2.metric("Valid rows", len(clean_rows))
    c3.metric("Error rows", len(error_rows))

    if error_rows:
        st.error("Some rows have errors. Download the error file, fix it, and upload again.")
        err_df = pd.DataFrame(error_rows)
        st.dataframe(err_df, use_container_width=True)
        st.download_button(
            "Download Error Rows",
            err_df.to_csv(index=False).encode("utf-8"),
            file_name="bulk_leave_upload_errors.csv",
            mime="text/csv",
            on_click=download_ack,
            args=("Bulk leave upload error rows",)
        )
        return

    if not clean_rows:
        st.warning("No valid rows to upload.")
        return

    clean_df = pd.DataFrame(clean_rows)
    same_day_dupes = clean_df[clean_df.duplicated(["Date", "Emp_ID"], keep=False)]
    if not same_day_dupes.empty:
        st.warning(f"{len(same_day_dupes)} rows have the same Date + Emp_ID. They will still be saved in replace-month mode and not collapsed.")

    with st.expander("Preview valid rows", expanded=False):
        st.dataframe(clean_df[["Date", "Emp_ID", "Leave_Type", "Status", "Remarks"]], use_container_width=True, height=320)

    duplicate_policy = "Replace duplicates"

    if st.button("✅ Confirm Bulk Upload Now", use_container_width=True, type="primary", key="confirm_bulk_upload_v74"):
        leave_df = read_table("leave_entries")
        preferred_cols = ["Date", "Emp_ID", "Leave_Type", "Remarks", "Supervisor", "Timestamp", "Status"]

        for col in preferred_cols:
            if col not in leave_df.columns:
                leave_df[col] = ""

        clean_df = clean_df[preferred_cols].copy()
        clean_df["_Date_dt"] = parse_app_date_series(clean_df["Date"])

        uploaded_months = []
        for _, dt in clean_df["_Date_dt"].dropna().items():
            uploaded_months.append(month_label(int(dt.year), int(dt.month)))
        uploaded_months = sorted(set(uploaded_months))

        removed_existing = 0
        if upload_mode == "Replace entire leave data for uploaded month" and uploaded_months:
            # Strict month replacement:
            # Remove every existing saved row that belongs to any uploaded month.
            # This avoids the previous issue where old rows remained and 63 uploaded rows became 100 saved rows.
            def _row_month_label(value):
                dt = parse_app_date_value(value)
                if pd.isna(dt):
                    return ""
                return month_label(int(dt.year), int(dt.month))

            leave_df["_Upload_Month_Label"] = leave_df["Date"].apply(_row_month_label)
            remove_mask = leave_df["_Upload_Month_Label"].isin(uploaded_months)
            removed_existing = int(remove_mask.sum())
            leave_df = leave_df[~remove_mask].drop(columns=["_Upload_Month_Label"], errors="ignore").copy()

        added = 0
        replaced = 0

        upload_rows = clean_df.drop(columns=["_Date_dt"], errors="ignore").copy()

        if upload_mode == "Replace entire leave data for uploaded month":
            # Important: do NOT collapse by Date + Emp_ID in replace-month mode.
            # Save every uploaded row exactly because bulk files may contain multiple leave rows
            # for the same employee/date/status during migration.
            leave_df = pd.concat([leave_df[preferred_cols], upload_rows[preferred_cols]], ignore_index=True)
            added = len(upload_rows)
            replaced = removed_existing
        else:
            # Append mode uses a full-row key, not only Date + Emp_ID, to avoid accidental row loss.
            for _, r in upload_rows.iterrows():
                mask = (
                    (leave_df["Date"].astype(str) == str(r["Date"])) &
                    (leave_df["Emp_ID"].astype(str) == str(r["Emp_ID"])) &
                    (leave_df["Leave_Type"].astype(str) == str(r["Leave_Type"])) &
                    (leave_df["Status"].astype(str) == str(r["Status"])) &
                    (leave_df["Remarks"].astype(str) == str(r["Remarks"]))
                )
                new_row = {col: r[col] for col in preferred_cols}

                if mask.any():
                    first_index = leave_df[mask].index[0]
                    for col, val in new_row.items():
                        leave_df.loc[first_index, col] = val
                    replaced += 1
                else:
                    leave_df.loc[len(leave_df)] = new_row
                    added += 1

        other_cols = [c for c in leave_df.columns if c not in preferred_cols]
        leave_df = leave_df[preferred_cols + other_cols]
        backup_path = backup_table("leave_entries", "before_bulk_upload")
        st.session_state.last_bulk_leave_backup_path = backup_path
        write_table("leave_entries", leave_df)

        # Critical: immediate re-read verification from disk/app storage.
        saved_df = read_table("leave_entries")

        def _saved_row_month_label(value):
            dt = parse_app_date_value(value)
            if pd.isna(dt):
                return ""
            return month_label(int(dt.year), int(dt.month))

        if not saved_df.empty:
            saved_df["_Saved_Month_Label"] = saved_df["Date"].apply(_saved_row_month_label)
            saved_month_df = saved_df[saved_df["_Saved_Month_Label"].isin(uploaded_months)].drop(columns=["_Saved_Month_Label"], errors="ignore")
        else:
            saved_month_df = saved_df

        # Physical row count is the only correct verification for migration upload.
        # Summary by employee can look smaller because it groups rows.
        saved_physical_rows = int(len(saved_month_df))
        expected_valid_rows = int(len(clean_rows))

        saved_summary = summarize_leave_rows(saved_month_df)
        msg = (
            f"Bulk upload complete. Uploaded: {total_uploaded}, Valid: {expected_valid_rows}, "
            f"Added: {added}, Replaced: {replaced}, Removed existing month rows: {removed_existing}, "
            f"Saved physical rows in uploaded month(s): {saved_physical_rows}."
        )

        if upload_mode == "Replace entire leave data for uploaded month" and saved_physical_rows != expected_valid_rows:
            st.error(f"Save verification failed: expected {expected_valid_rows} physical rows but found {saved_physical_rows}. Do not proceed to payroll.")
            st.warning("The file was written, but verification failed. Download All Leave Entries from Leave page and share it if this repeats.")
            st.markdown("#### Saved employee summary after failed verification")
            st.dataframe(saved_summary, use_container_width=True)
            st.markdown("#### Saved physical rows found for uploaded month")
            st.dataframe(saved_month_df, use_container_width=True, height=min(300, 80 + len(saved_month_df) * 25))
            return

        st.session_state.bulk_upload_message = msg
        st.session_state.last_bulk_upload_summary = saved_summary.to_dict("records")
        add_audit(st.session_state.user["email"], "BULK_LEAVE_UPLOAD", msg)
        set_confirmation(msg, celebrate=True)
        st.markdown("#### Saved employee summary after upload")
        st.dataframe(saved_summary, use_container_width=True, height=min(260, 80 + len(saved_summary) * 35))



def require_admin_change_remark(remark):
    if st.session_state.user.get("role") == "Admin" and not str(remark).strip():
        st.error("Admin correction remark is mandatory for edit/delete changes.")
        return False
    return True

def row_display_label(df, idx, cols):
    parts = []
    for c in cols:
        if c in df.columns:
            parts.append(f"{c}: {df.loc[idx, c]}")
    return f"Row {idx} | " + " | ".join(parts)



def build_leave_correction_view(all_leaves):
    """Return a filtered leave table for Admin correction without hiding rows silently."""
    if all_leaves is None or all_leaves.empty:
        return pd.DataFrame()

    view = all_leaves.copy()
    view["_row_id"] = view.index
    if "Date" in view.columns:
        view["_Date_dt"] = parse_app_date_series(view["Date"])
        view["_Month"] = view["_Date_dt"].dt.strftime("%b-%Y").fillna("Unknown")
    else:
        view["_Month"] = "Unknown"

    st.markdown("##### Find leave row")
    c1, c2, c3 = st.columns(3)

    month_options = ["All"] + sorted([m for m in view["_Month"].astype(str).unique().tolist() if m and m != "nan"])
    selected_month_filter = c1.selectbox("Filter month", month_options, key="leave_corr_month_filter")

    emp_options = ["All"]
    if "Emp_ID" in view.columns:
        emp_options += sorted(view["Emp_ID"].dropna().astype(str).unique().tolist())
    selected_emp_filter = c2.selectbox("Filter employee", emp_options, key="leave_corr_emp_filter")

    status_options = ["All"]
    if "Status" in view.columns:
        status_options += sorted(view["Status"].fillna("").astype(str).replace("", "Blank").unique().tolist())
    selected_status_filter = c3.selectbox("Filter status", status_options, key="leave_corr_status_filter")

    if selected_month_filter != "All":
        view = view[view["_Month"].astype(str) == selected_month_filter]
    if selected_emp_filter != "All" and "Emp_ID" in view.columns:
        view = view[view["Emp_ID"].astype(str) == selected_emp_filter]
    if selected_status_filter != "All" and "Status" in view.columns:
        if selected_status_filter == "Blank":
            view = view[view["Status"].fillna("").astype(str).eq("")]
        else:
            view = view[view["Status"].astype(str) == selected_status_filter]

    sort_cols = [c for c in ["_Date_dt", "Emp_ID", "Leave_Type"] if c in view.columns]
    if sort_cols:
        view = view.sort_values(sort_cols, ascending=[False] + [True] * (len(sort_cols) - 1))

    show_cols = [c for c in ["_row_id", "Date", "Emp_ID", "Leave_Type", "Status", "Remarks", "Supervisor", "Timestamp"] if c in view.columns]
    st.caption(f"Total saved leave rows: {len(all_leaves)} | Rows matching current filters: {len(view)}")
    st.dataframe(view[show_cols] if show_cols else view, use_container_width=True, height=min(360, 80 + max(1, len(view)) * 32))
    return view


def leave_page():
    st.subheader("Leave Updation")
    st.caption("Admin corrections use safe edit/cancel with mandatory remark and backup. Cancelled leaves remain in audit history and are ignored by payroll.")
    employees = active_employees_for_user()
    choices = employee_choices(employees)
    if not choices:
        st.info("No active employees available.")
        return

    with st.form("leave_form"):
        att_date = st.date_input("Leave date", value=date.today(), max_value=date.today())
        employee_pick = st.selectbox("Employee", choices)
        leave_type = st.selectbox("Leave type", list(LEAVE_UNITS.keys()))
        remarks = st.text_area("Remarks", placeholder="Keep short. Mandatory for uninformed leave.")
        submitted = st.form_submit_button("Save Leave")
    if submitted:
        lock_month = month_label(att_date.year, att_date.month)
        if is_month_locked(lock_month):
            st.error(f"Payroll for {lock_month} is approved and locked. Leave changes are not allowed.")
            return
        if leave_type == "Leave - Uninformed" and not remarks.strip():
            st.error("Remarks are mandatory for Uninformed Leave.")
            return
        emp_id = extract_emp_id(employee_pick)
        df = read_table("leave_entries")
        key_exists = ((df["Date"].astype(str) == str(att_date)) & (df["Emp_ID"].astype(str) == emp_id)).any()
        if key_exists:
            st.error("Duplicate blocked: this employee already has a leave entry for this date.")
            return
        new_leave_row = {
            "Date": str(att_date),
            "Emp_ID": emp_id,
            "Leave_Type": leave_type,
            "Remarks": remarks,
            "Supervisor": st.session_state.user["email"],
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "Status": "Approved",
        }
        for col in new_leave_row:
            if col not in df.columns:
                df[col] = ""
        df.loc[len(df), list(new_leave_row.keys())] = list(new_leave_row.values())
        write_table("leave_entries", df)
        add_audit(st.session_state.user["email"], "SAVE_LEAVE", f"{att_date} {emp_id} {leave_type}")
        set_confirmation("Leave saved and will flow into payroll calculation.", celebrate=True)
        set_action_focus("Leave saved. You can add another leave entry or review Recent Entries below.", page="Leave Saved")
        st.rerun()

    st.markdown("#### Leave entries")
    all_leaves = read_table("leave_entries")
    st.caption(f"Total leave rows saved: {len(all_leaves)}")
    if all_leaves.empty:
        st.info("No leave entries recorded yet. This is valid — payroll will treat everyone as present unless leave is added.")
        display_leaves = all_leaves
    else:
        sort_cols = [c for c in ["Date", "Emp_ID"] if c in all_leaves.columns]
        display_leaves = all_leaves.sort_values(sort_cols, ascending=[False, True][:len(sort_cols)]) if sort_cols else all_leaves
    st.dataframe(display_leaves, use_container_width=True, height=320)

    if st.session_state.user.get("role") == "Admin" and not all_leaves.empty:
        st.markdown("#### Admin correction: edit/cancel leave")
        st.caption("Safe correction mode: creates backup first, edits only selected row, and cancels instead of deleting. Admin correction remark is mandatory.")
        correction_view = build_leave_correction_view(all_leaves)

        if correction_view.empty:
            st.warning("No leave rows match the selected filters. Change filters to see more rows.")
        else:
            correction_view = correction_view.copy()
            correction_view["_select_label"] = correction_view.apply(
                lambda r: f"Row {int(r['_row_id'])} | {r.get('Date', '')} | {r.get('Emp_ID', '')} | {r.get('Leave_Type', '')} | {r.get('Status', '')}",
                axis=1
            )
            selected_label = st.selectbox("Select leave row to correct", correction_view["_select_label"].tolist(), key="leave_corr_selected_label")
            selected_idx = int(correction_view[correction_view["_select_label"] == selected_label]["_row_id"].iloc[0])
            selected = all_leaves.loc[selected_idx]

            with st.form("admin_leave_safe_correction_form"):
                action = st.radio("Action", ["Edit leave", "Cancel leave"], horizontal=True)
                c1, c2 = st.columns(2)
                parsed_date = pd.to_datetime(selected.get("Date"), errors="coerce")
                new_date = c1.date_input("Leave date", value=parsed_date.date() if not pd.isna(parsed_date) else date.today())
                current_type = selected.get("Leave_Type", list(LEAVE_UNITS.keys())[0])
                type_index = list(LEAVE_UNITS.keys()).index(current_type) if current_type in list(LEAVE_UNITS.keys()) else 0
                new_leave_type = c2.selectbox("Leave type", list(LEAVE_UNITS.keys()), index=type_index)

                if action == "Edit leave":
                    current_status = selected.get("Status", "Approved")
                    status_options = ["Approved", "Rejected", "Cancelled"]
                    status_index = status_options.index(current_status) if current_status in status_options else 0
                    new_status = st.selectbox("Status", status_options, index=status_index)
                else:
                    new_status = "Cancelled"
                    st.warning("Cancel will not delete the leave row. It will mark Status = Cancelled so payroll ignores it while audit remains intact.")

                correction_remark = st.text_area("Mandatory admin correction remark", value="")
                submitted_correction = st.form_submit_button("Apply Leave Correction Safely")

            if submitted_correction:
                if not require_admin_change_remark(correction_remark):
                    return

                b1 = backup_leave_table("before_admin_leave_correction")
                fresh_leaves = read_table("leave_entries")
                if fresh_leaves.empty:
                    st.error("Leave table is empty. Correction stopped.")
                    return
                if selected_idx not in list(fresh_leaves.index):
                    st.error("Selected leave row no longer exists. Please refresh before editing.")
                    return

                if action == "Edit leave":
                    lock_month = month_label(new_date.year, new_date.month)
                    if is_month_locked(lock_month):
                        st.error(f"Payroll for {lock_month} is approved and locked. Leave changes are not allowed.")
                        return

                for col in ["Date", "Emp_ID", "Leave_Type", "Remarks", "Supervisor", "Timestamp", "Status"]:
                    if col not in fresh_leaves.columns:
                        fresh_leaves[col] = ""

                existing_remark = str(fresh_leaves.loc[selected_idx, "Remarks"])
                fresh_leaves.loc[selected_idx, "Date"] = str(new_date)
                fresh_leaves.loc[selected_idx, "Leave_Type"] = new_leave_type
                fresh_leaves.loc[selected_idx, "Status"] = new_status
                fresh_leaves.loc[selected_idx, "Remarks"] = f"{existing_remark} | ADMIN CORRECTION: {correction_remark}".strip(" |")
                fresh_leaves.loc[selected_idx, "Supervisor"] = st.session_state.user["email"]
                fresh_leaves.loc[selected_idx, "Timestamp"] = datetime.now().isoformat(timespec="seconds")

                write_table("leave_entries", fresh_leaves.reset_index(drop=True))
                action_name = "CANCEL_LEAVE_ADMIN_SAFE" if action == "Cancel leave" else "EDIT_LEAVE_ADMIN_SAFE"
                add_audit(st.session_state.user["email"], action_name, f"row {selected_idx}; remark: {correction_remark}; backup: {b1}")
                msg = "Leave cancelled safely with backup." if action == "Cancel leave" else "Leave updated safely with backup."
                set_confirmation(msg, celebrate=True)
                st.info(f"Backup created: {b1}")
                st.rerun()

    st.download_button(
        "Download All Leave Entries",
        all_leaves.to_csv(index=False).encode("utf-8"),
        file_name="leave_entries.csv",
        mime="text/csv",
        on_click=download_ack,
        args=("Leave entries CSV",)
    )


def holiday_page():
    st.subheader("Individual Festival / Holiday Exclusions")
    st.caption("Use this when a holiday is applicable to selected employees based on their festival. Select multiple employees together.")

    employees = active_employees_for_user()
    choices = employee_choices(employees)
    if not choices:
        st.info("No active employees available.")
        return

    with st.form("holiday_form"):
        holiday_date = st.date_input("Holiday date", value=date.today())
        selected_employees = st.multiselect("Select employees for this holiday", choices, help="You can select multiple employees at the same time.")
        festival = st.text_input("Festival / holiday name", placeholder="Example: Eid, Diwali, Christmas, Chhath")
        remarks = st.text_area("Remarks", placeholder="Optional")
        submitted = st.form_submit_button("Mark Holiday for Selected Employees")
    if submitted:
        lock_month = month_label(holiday_date.year, holiday_date.month)
        if is_month_locked(lock_month):
            st.error(f"Payroll for {lock_month} is approved and locked. Holiday changes are not allowed.")
            return
        if not festival.strip():
            st.error("Festival / holiday name is required.")
            return
        if not selected_employees:
            st.error("Please select at least one employee.")
            return

        holidays = read_table("employee_holidays")
        added = 0
        skipped = 0
        for employee_pick in selected_employees:
            emp_id = extract_emp_id(employee_pick)
            duplicate = ((holidays["Date"].astype(str) == str(holiday_date)) & (holidays["Emp_ID"].astype(str) == emp_id)).any() if not holidays.empty else False
            if duplicate:
                skipped += 1
                continue
            holiday_id = f"HOL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{emp_id}"
            holidays.loc[len(holidays)] = [holiday_id, str(holiday_date), emp_id, festival.strip(), remarks, st.session_state.user["email"], datetime.now().isoformat(timespec="seconds")]
            added += 1

        write_table("employee_holidays", holidays)
        add_audit(st.session_state.user["email"], "MARK_MULTI_EMPLOYEE_HOLIDAY", f"{holiday_date} {festival} added={added} skipped={skipped}")
        st.success(f"Holiday marked for {added} employee(s). Skipped {skipped} duplicate(s).")
        st.rerun()

    st.markdown("#### Holiday exclusions")
    holidays = read_table("employee_holidays")
    if holidays.empty:
        st.info("No holiday exclusions marked yet.")
    else:
        search = st.text_input("Search holiday records", placeholder="Search by employee ID, festival, date...")
        display = holidays.copy()
        if search.strip():
            s = search.strip().lower()
            display = display[display.astype(str).apply(lambda row: row.str.lower().str.contains(s, na=False).any(), axis=1)]
        st.dataframe(display.tail(100), use_container_width=True)


def advance_page():
    st.subheader("Advance Updation")
    st.caption("Advance entered here creates the repayment schedule. Salary Summary shows Total Advance taken up to recalculation date, while monthly deduction follows the selected month’s schedule.")
    employees = active_employees_for_user()
    choices = employee_choices(employees)
    if not choices:
        st.info("No active employees available.")
        return

    with st.form("advance_form"):
        employee_pick = st.selectbox("Employee", choices)
        adv_date = st.date_input("Date of giving advance", value=date.today())
        amount = st.number_input("Amount given", min_value=0.0, step=500.0)
        st.caption("Example: ₹4000 taken, ₹2000 deducted in first month, remaining over 2 months = ₹1000/month.")
        c1, c2, c3 = st.columns(3)
        start_month = c1.selectbox("Refund start month", list(range(1, 13)), index=date.today().month - 1, format_func=lambda m: calendar.month_name[m])
        start_year = c2.number_input("Refund start year", min_value=2020, max_value=2100, value=date.today().year, step=1)
        first_deduction = c3.number_input("First month deduction", min_value=0.0, step=500.0)
        remaining_months = st.number_input("Remaining months after first deduction", min_value=0, step=1)
        remarks = st.text_area("Advance remarks")
        submitted = st.form_submit_button("Create Advance & Schedule")
    if submitted:
        emp_id = extract_emp_id(employee_pick)
        if is_month_locked(month_label(int(start_year), int(start_month))):
            st.error("Refund start month is already approved and locked. Advance schedule cannot start in a locked month.")
            return
        if amount <= 0:
            st.error("Advance amount must be greater than 0.")
            return
        if first_deduction > amount:
            st.error("First month deduction cannot be greater than amount given.")
            return
        if first_deduction <= 0 and int(remaining_months) <= 0:
            st.error("Please define at least one deduction: first month deduction or remaining months.")
            return
        cases = read_table("advance_cases")
        schedule = read_table("advance_schedule")
        advance_id = f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cases.loc[len(cases)] = [advance_id, emp_id, str(adv_date), amount, month_label(int(start_year), int(start_month)), first_deduction, remaining_months, "Open", remarks, st.session_state.user["email"], datetime.now().isoformat(timespec="seconds")]
        new_sched = rebuild_schedule_rows_for_advance(advance_id, emp_id, amount, int(start_year), int(start_month), first_deduction, remaining_months, updated_by=st.session_state.user["email"])
        if not new_sched.empty:
            schedule = pd.concat([schedule, new_sched], ignore_index=True)
        b1, b2 = safe_write_advance_tables(cases, schedule, label="before_advance_create", selected_advance_id=advance_id)
        add_audit(st.session_state.user["email"], "CREATE_ADVANCE", f"{advance_id} {emp_id} ₹{amount}; backups: {b1}, {b2}")
        set_confirmation("Advance and repayment schedule created.", celebrate=True)
        set_action_focus("Advance saved. You can add another advance or review Recent Entries / Salary Summary.", page="Advance Saved")
        st.rerun()

    cases = read_table("advance_cases")
    schedule = read_table("advance_schedule")
    advance_issues = advance_integrity_report(cases, schedule)
    if advance_issues:
        st.warning("Advance safety review: " + " | ".join(advance_issues[:3]))
    st.markdown("#### Advance cases")
    st.dataframe(cases.tail(20), use_container_width=True, height=280)

    if st.session_state.user.get("role") == "Admin" and not cases.empty:
        st.markdown("#### Admin correction: edit advance")
        st.caption("Safe edit mode: creates backup first, edits only selected advance ID, and rebuilds only that advance’s repayment schedule. Admin correction remark is mandatory.")
        selected_idx = st.selectbox(
            "Select advance case to edit",
            list(cases.index),
            format_func=lambda i: row_display_label(cases, i, ["Advance_ID", "Emp_ID", "Advance_Date", "Amount_Given", "Status"])
        )
        selected = cases.loc[selected_idx]
        adv_id = str(selected.get("Advance_ID", ""))
        with st.form("admin_advance_edit_form"):
            c1, c2 = st.columns(2)
            parsed_date = pd.to_datetime(selected.get("Advance_Date"), errors="coerce")
            new_adv_date = c1.date_input("Advance date", value=parsed_date.date() if not pd.isna(parsed_date) else date.today())
            new_amount = c2.number_input("Amount given", min_value=0.0, step=50.0, value=safe_float(selected.get("Amount_Given", 0)))
            c3, c4, c5 = st.columns(3)
            selected_start = str(selected.get("Refund_Start_Month", month_label(date.today().year, date.today().month)))
            try:
                sy, sm = parse_month_label(selected_start)
            except Exception:
                sy, sm = date.today().year, date.today().month
            new_start_month = c3.selectbox("Refund start month", list(range(1, 13)), index=int(sm)-1, format_func=lambda m: calendar.month_name[m])
            new_start_year = c4.number_input("Refund start year", min_value=2020, max_value=2100, value=int(sy), step=1)
            new_first_deduction = c5.number_input("First month deduction", min_value=0.0, step=50.0, value=safe_float(selected.get("First_Month_Deduction", 0)))
            new_remaining_months = st.number_input("Remaining months after first deduction", min_value=0, step=1, value=int(safe_float(selected.get("Remaining_Months", 0))))
            new_status = st.selectbox("Status", ["Open", "Closed", "Cancelled"], index=["Open", "Closed", "Cancelled"].index(selected.get("Status", "Open")) if selected.get("Status", "Open") in ["Open", "Closed", "Cancelled"] else 0)
            correction_remark = st.text_area("Mandatory admin correction remark", value="")
            submitted_correction = st.form_submit_button("Update Selected Advance Safely")

        if submitted_correction:
            if not require_admin_change_remark(correction_remark):
                return
            if new_amount <= 0:
                st.error("Advance amount must be greater than 0.")
                return
            if new_first_deduction > new_amount:
                st.error("First month deduction cannot be greater than amount given.")
                return
            if new_first_deduction <= 0 and int(new_remaining_months) <= 0:
                st.error("Please define at least one deduction: first month deduction or remaining months.")
                return

            b1, b2 = backup_advance_tables("before_admin_advance_edit")
            fresh_cases = read_table("advance_cases")
            fresh_schedule = read_table("advance_schedule")
            if fresh_cases.empty or "Advance_ID" not in fresh_cases.columns:
                st.error("Advance table is empty or malformed. Edit stopped. Use backup/recovery before proceeding.")
                return
            if adv_id not in fresh_cases["Advance_ID"].astype(str).tolist():
                st.error("Selected advance ID no longer exists. Please refresh before editing.")
                return

            mask = fresh_cases["Advance_ID"].astype(str) == adv_id
            emp_id_selected = str(fresh_cases.loc[mask, "Emp_ID"].iloc[0])
            fresh_cases.loc[mask, "Advance_Date"] = str(new_adv_date)
            fresh_cases.loc[mask, "Amount_Given"] = new_amount
            fresh_cases.loc[mask, "Refund_Start_Month"] = month_label(int(new_start_year), int(new_start_month))
            fresh_cases.loc[mask, "First_Month_Deduction"] = new_first_deduction
            fresh_cases.loc[mask, "Remaining_Months"] = int(new_remaining_months)
            fresh_cases.loc[mask, "Status"] = new_status
            fresh_cases.loc[mask, "Remarks"] = f"{str(fresh_cases.loc[mask, 'Remarks'].iloc[0])} | ADMIN CORRECTION: {correction_remark}"
            fresh_cases.loc[mask, "Created_By"] = st.session_state.user["email"]
            fresh_cases.loc[mask, "Timestamp"] = datetime.now().isoformat(timespec="seconds")

            for col in REQUIRED_FILES["advance_schedule"]:
                if col not in fresh_schedule.columns:
                    fresh_schedule[col] = ""
            if "Advance_ID" in fresh_schedule.columns:
                fresh_schedule = fresh_schedule[fresh_schedule["Advance_ID"].astype(str) != adv_id].copy()
            new_sched = rebuild_schedule_rows_for_advance(
                adv_id, emp_id_selected, new_amount, int(new_start_year), int(new_start_month),
                new_first_deduction, int(new_remaining_months), updated_by=st.session_state.user["email"]
            )
            fresh_schedule = pd.concat([fresh_schedule, new_sched], ignore_index=True)

            try:
                validate_advance_write_safety(read_table("advance_cases"), fresh_cases, read_table("advance_schedule"), fresh_schedule, selected_advance_id=adv_id)
                write_table("advance_cases", fresh_cases.reset_index(drop=True))
                write_table("advance_schedule", fresh_schedule.reset_index(drop=True))
            except Exception as e:
                st.error(f"Advance safety guard stopped this edit: {e}")
                return
            add_audit(st.session_state.user["email"], "EDIT_ADVANCE_ADMIN_SAFE", f"{adv_id}; remark: {correction_remark}; backups: {b1}, {b2}")
            set_confirmation("Selected advance updated safely. Backup was created before change.", celebrate=True)
            st.info(f"Backup created: {b1} and {b2}")
            st.rerun()

        with st.expander("Danger zone: cancel selected advance", expanded=False):
            st.warning("This does not physically delete the row. It marks the selected advance as Cancelled and removes future schedule impact.")
            cancel_remark = st.text_area("Mandatory cancellation remark", key="cancel_advance_remark")
            if st.button("Cancel Selected Advance", use_container_width=True):
                if not require_admin_change_remark(cancel_remark):
                    return
                b1, b2 = backup_advance_tables("before_admin_advance_cancel")
                fresh_cases = read_table("advance_cases")
                fresh_schedule = read_table("advance_schedule")
                if adv_id not in fresh_cases["Advance_ID"].astype(str).tolist():
                    st.error("Selected advance ID no longer exists. Please refresh.")
                    return
                fresh_cases.loc[fresh_cases["Advance_ID"].astype(str) == adv_id, "Status"] = "Cancelled"
                fresh_cases.loc[fresh_cases["Advance_ID"].astype(str) == adv_id, "Remarks"] = fresh_cases.loc[fresh_cases["Advance_ID"].astype(str) == adv_id, "Remarks"].astype(str) + f" | CANCELLED: {cancel_remark}"
                if not fresh_schedule.empty and "Advance_ID" in fresh_schedule.columns:
                    fresh_schedule.loc[fresh_schedule["Advance_ID"].astype(str) == adv_id, "Status"] = "Cancelled"
                    fresh_schedule.loc[fresh_schedule["Advance_ID"].astype(str) == adv_id, "Updated_By"] = st.session_state.user["email"]
                    fresh_schedule.loc[fresh_schedule["Advance_ID"].astype(str) == adv_id, "Updated_At"] = datetime.now().isoformat(timespec="seconds")
                try:
                    validate_advance_write_safety(read_table("advance_cases"), fresh_cases, read_table("advance_schedule"), fresh_schedule, selected_advance_id=adv_id)
                    write_table("advance_cases", fresh_cases.reset_index(drop=True))
                    write_table("advance_schedule", fresh_schedule.reset_index(drop=True))
                except Exception as e:
                    st.error(f"Advance safety guard stopped this cancellation: {e}")
                    return
                add_audit(st.session_state.user["email"], "CANCEL_ADVANCE_ADMIN_SAFE", f"{adv_id}; remark: {cancel_remark}; backups: {b1}, {b2}")
                set_confirmation("Selected advance cancelled safely with backup.", celebrate=True)
                st.rerun()

    st.markdown("#### Repayment schedule")
    st.caption("If a correction goes wrong, check the app backups folder for advance_cases_before_admin_advance_* and advance_schedule_before_admin_advance_* CSV files.")
    st.dataframe(read_table("advance_schedule").tail(50), use_container_width=True, height=320)


def clean_summary_rows(summary):
    if summary.empty:
        return summary
    cleaned = summary.copy()
    # Remove fully empty rows and rows without employee/name.
    cleaned = cleaned.dropna(how="all")
    if "Name" in cleaned.columns:
        cleaned = cleaned[cleaned["Name"].astype(str).str.strip().ne("")]
        cleaned = cleaned[cleaned["Name"].astype(str).str.lower().ne("nan")]
    return cleaned.reset_index(drop=True)

def format_money(value):
    try:
        return f"₹{float(value):,.0f}"
    except Exception:
        return str(value)

def render_salary_summary_cards(summary):
    employees_count = len(summary)
    total_net = summary["Net Salary to be Paid"].sum() if "Net Salary to be Paid" in summary else 0
    total_adv_left = summary["Advance Left"].sum() if "Advance Left" in summary else 0
    total_leave_cost = summary["Leave Deduction Cost on extra leaves"].sum() if "Leave Deduction Cost on extra leaves" in summary else 0
    html = f"""
    <div class='summary-card-grid'>
        <div class='summary-card'>
            <div class='summary-card-label'>Employees</div>
            <div class='summary-card-value'>{employees_count}</div>
        </div>
        <div class='summary-card'>
            <div class='summary-card-label'>Net Salary to be Paid</div>
            <div class='summary-card-value'>{format_money(total_net)}</div>
        </div>
        <div class='summary-card'>
            <div class='summary-card-label'>Advance Left</div>
            <div class='summary-card-value'>{format_money(total_adv_left)}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_sticky_salary_table(summary):
    import html as html_lib
    money_cols = {
        "Total Pay", "Daily Wage", "Advance Prior Month", "Advance Current Month",
        "Total Advance", "Deduction for the Month", "Leave Deduction Cost on extra leaves",
        "Net Salary to be Paid", "Advance Left"
    }
    cols = list(summary.columns)
    thead = "".join(f"<th>{html_lib.escape(str(c))}</th>" for c in cols)
    rows = []
    for _, r in summary.iterrows():
        cells = []
        for c in cols:
            val = r[c]
            if c in money_cols:
                val = format_money(val)
            else:
                try:
                    if isinstance(val, float) and val.is_integer():
                        val = int(val)
                except Exception:
                    pass
            cells.append(f"<td>{html_lib.escape(str(val))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    table_html = f"""
    <div class='salary-helper'><b>App-style summary</b> · Swipe left/right to view all columns. Name stays fixed.</div>
    <div class='salary-table-wrap' style='height: auto;'>
        <table class='salary-table'>
            <thead><tr>{thead}</tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)



def render_sticky_report_table(df, title="Report"):
    """Render any report with Name column sticky, falling back gracefully when empty."""
    if df is None or df.empty:
        st.info(f"No data available for {title}.")
        return
    import html as html_lib
    display = df.copy().dropna(how="all")
    if display.empty:
        st.info(f"No data available for {title}.")
        return

    cols = list(display.columns)
    sticky_col = "Name" if "Name" in cols else cols[0]
    # Put Name first visually for better frozen-column experience.
    if sticky_col in cols and cols[0] != sticky_col:
        cols = [sticky_col] + [c for c in cols if c != sticky_col]
        display = display[cols]

    numeric_like = []
    for c in cols:
        if c != sticky_col:
            converted = pd.to_numeric(display[c], errors="coerce")
            if converted.notna().sum() > 0:
                numeric_like.append(c)

    thead = "".join(f"<th>{html_lib.escape(str(c))}</th>" for c in cols)
    rows = []
    for _, r in display.iterrows():
        cells = []
        for c in cols:
            val = r[c]
            if c in numeric_like:
                try:
                    fval = float(pd.to_numeric(val, errors="coerce"))
                    val = f"₹{fval:,.0f}" if any(k in str(c).lower() for k in ["salary", "pay", "advance", "deduction", "cost", "encashment", "wage"]) else (int(fval) if fval.is_integer() else round(fval, 2))
                except Exception:
                    pass
            cells.append(f"<td>{html_lib.escape(str(val))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")

    st.markdown(f"""
    <div class='salary-helper'><b>{html_lib.escape(title)}</b> · Scroll right to view all columns. {html_lib.escape(sticky_col)} stays fixed.</div>
    <div class='salary-table-wrap' style='height: auto;'>
        <table class='salary-table'>
            <thead><tr>{thead}</tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

def salary_summary_page():
    st.subheader("Mobile Salary Summary")
    payroll = normalize_payroll_columns(read_table("payroll_items"))
    if payroll.empty:
        st.info("No payroll generated yet. Generate payroll first.")
        return

    months = build_salary_summary_month_options(payroll)
    if not months:
        st.info("No payroll month is available yet. Generate or recalculate payroll first.")
        return

    default_month = normalize_month_label_value(st.session_state.get("salary_summary_selected_month", ""))
    default_index = months.index(default_month) if default_month in months else len(months) - 1
    selected_month = st.selectbox("Select month", months, index=default_index, key="salary_summary_selected_month")
    selected_month = normalize_month_label_value(selected_month) or selected_month

    reconciled_payroll = reconcile_payroll_month(selected_month, payroll)
    if len(reconciled_payroll) != len(payroll):
        write_table("payroll_items", reconciled_payroll)
        st.warning("Payroll month had missing active employees and has been reconciled automatically. Please refresh summary if needed.")

    summary = build_mobile_salary_summary(selected_month)
    summary = clean_summary_rows(summary)

    if summary.empty:
        st.info("No summary available for selected month.")
        return

    st.caption("Default view is app-style and phone-friendly. Swipe left/right in the summary table; Name stays fixed.")
    render_next_step("After reviewing salary summary, proceed to Payroll Approval only when figures are final.")
    st.info("Advance logic: Total Advance shows advance taken up to recalculation date. Deduction for the Month uses only the selected month’s repayment schedule and is capped to remaining advance balance.")

    render_salary_summary_cards(summary)
    render_sticky_salary_table(summary)

    with st.expander("Salary calculation explanation", expanded=False):
        st.caption("Quick trust-building view for end users. Use this to explain why net salary is coming as shown.")
        for _, row in summary.iterrows():
            st.write("• " + explain_salary_row(row))

    with st.expander("Audit view / spreadsheet view"):
        st.caption("Use this only when you want a raw table for checking or audit. The app-style view above is the recommended daily view.")
        st.dataframe(summary, use_container_width=True, height=min(240, 70 + len(summary) * 28))

    st.download_button(
        "Download Salary Summary CSV",
        summary.to_csv(index=False).encode("utf-8"),
        file_name=f"salary_summary_{selected_month}.csv",
        mime="text/csv",
        on_click=download_ack,
        args=("Salary summary CSV",)
    )


def payroll_page():
    st.subheader("Payroll")
    st.caption("This page performs the salary calculation/recalculation. Use Payroll Approval only after Salary Summary review.")
    today = date.today()
    c1, c2 = st.columns(2)
    year = c1.number_input("Payroll year", min_value=2020, max_value=2100, value=today.year, step=1)
    month = c2.selectbox("Payroll month", list(range(1, 13)), index=today.month - 1, format_func=lambda m: calendar.month_name[m])

    selected_month = month_label(int(year), int(month))
    leave_entries = read_table("leave_entries")
    month_start = pd.Timestamp(year=int(year), month=int(month), day=1)
    month_end = pd.Timestamp(year=int(year), month=int(month), day=calendar.monthrange(int(year), int(month))[1])
    leaves_in_month = pd.DataFrame()
    if not leave_entries.empty:
        tmp_leaves = leave_entries.copy()
        tmp_leaves["Date_dt"] = parse_app_date_series(tmp_leaves["Date"])
        leaves_in_month = tmp_leaves[(tmp_leaves["Date_dt"] >= month_start) & (tmp_leaves["Date_dt"] <= month_end)]
    st.info(f"Preview payroll can be calculated anytime. Before approval/lock, recalculate on or after {first_lock_allowed_date(int(year), int(month))}. Leaves detected for {selected_month}: {len(leaves_in_month)}.")
    if len(leaves_in_month) == 0 and len(leave_entries) > 0:
        st.warning("Leave file has rows, but none matched the selected month. Check date format in Leave Matching Diagnostics.")

    readiness = render_month_readiness(selected_month)
    render_next_step("After calculation, open Salary Summary to review employee-wise salary before approval.")
    if readiness["active_employees"] == 0:
        st.error("No active employees found. Payroll should not be generated until employee master is ready.")
    with st.expander("Leave matching diagnostics"):
        diag = build_leave_match_diagnostics(selected_month)
        if diag.empty:
            st.info("No leave diagnostics available.")
        else:
            render_sticky_report_table(diag, "Leave Matching Diagnostics")
            if not diag.empty and "Uploaded Leave Rows" in diag.columns:
                total_rows = pd.to_numeric(diag[diag["Emp_ID"].astype(str) != "TOTAL"]["Uploaded Leave Rows"], errors="coerce").fillna(0).sum()
                total_units = pd.to_numeric(diag[diag["Emp_ID"].astype(str) != "TOTAL"]["Counted Leave Units"], errors="coerce").fillna(0).sum()
                st.success(f"Diagnostics total: {int(total_rows)} uploaded leave rows and {total_units:g} counted leave units for selected month.")

    st.caption("Step 1: Generate regular overall payroll only. Collaborative leave is counted as 1 leave here; special 1.5 impact or penalties are applied only from Employee Profile for selected employees.")

    if st.button("Generate Monthly Payroll"):
        if is_month_locked(selected_month):
            st.error(f"Payroll for {selected_month} is approved and locked. Regeneration is blocked.")
            return
        payroll, logs = calculate_payroll(int(year), int(month))
        payroll = normalize_payroll_columns(payroll)
        write_table("payroll_items", payroll)
        write_table("leave_adjustment_log", logs)
        st.session_state.last_recalculated_month = selected_month
        st.session_state.salary_summary_selected_month = selected_month
        add_audit(st.session_state.user["email"], "GENERATE_PAYROLL", selected_month)
        set_confirmation("Payroll calculated after month-end rule check. Admin can now review individual profiles and recalculate if needed.", celebrate=True)
        st.rerun()

    payroll = read_table("payroll_items")
    if not payroll.empty and "Month" in payroll.columns and len(payroll["Month"].dropna().astype(str).unique()) > 0:
        latest_display_month = payroll["Month"].dropna().astype(str).unique()[-1]
        reconciled_payroll = reconcile_payroll_month(latest_display_month, payroll)
        if len(reconciled_payroll) != len(payroll):
            write_table("payroll_items", reconciled_payroll)
            payroll = reconciled_payroll
            st.warning(f"Payroll for {latest_display_month} had missing active employees and was reconciled automatically.")
    if not payroll.empty:
        st.markdown("#### Payroll report")
        st.caption("This report reflects regular payroll plus any individual recalculations saved from Employee Profile.")
        render_sticky_report_table(payroll, "Payroll Report")
        with st.expander("Audit spreadsheet view"):
            st.dataframe(payroll, use_container_width=True, height=min(420, 80 + len(payroll) * 36))
        st.download_button("Download Payroll CSV", payroll.to_csv(index=False).encode("utf-8"), "payroll.csv", "text/csv", on_click=download_ack, args=("Payroll CSV",))
        if "Month" in payroll.columns and len(payroll["Month"].dropna().unique()) > 0:
            latest_month = payroll["Month"].dropna().unique()[-1]
            st.download_button(
                "Download Final Monthly Excel",
                payroll_excel_bytes(latest_month),
                file_name=f"salary_month_end_{latest_month}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click=download_ack,
                args=("Final monthly Excel",)
            )
        c1, c2 = st.columns(2)
        c1.metric("Total without special deductions", f"₹{pd.to_numeric(payroll['Final_Salary_Without_Special'], errors='coerce').fillna(0).sum():,.0f}")
        c2.metric("Total with special deductions", f"₹{pd.to_numeric(payroll['Final_Salary_With_Special'], errors='coerce').fillna(0).sum():,.0f}")
    else:
        st.info("No payroll generated yet.")


def payroll_approval_page():
    st.subheader("Payroll Approval")
    st.caption("Final approval and lock page. Use only after payroll calculation and salary summary review.")
    st.info("Before final approval, create a payroll snapshot backup for recovery and audit.")
    if st.button("Create Payroll Snapshot Backup", use_container_width=True, key="manual_payroll_snapshot"):
        snap = create_payroll_snapshot(selected_month if "selected_month" in locals() else month_label(date.today().year, date.today().month))
        set_confirmation(f"Payroll snapshot created: {snap}", celebrate=True)
        st.rerun()

    if st.session_state.user["role"] != "Admin":
        st.warning("Only Admin can approve or unlock payroll.")
        return

    payroll = normalize_payroll_columns(read_table("payroll_items"))
    if payroll.empty:
        st.info("No payroll generated yet. Generate payroll first.")
        return

    months = payroll["Month"].dropna().astype(str).unique().tolist()
    selected_month = st.selectbox("Select payroll month", months, index=len(months)-1)
    selected_year, selected_month_num = parse_month_label(selected_month)
    lock_allowed_date = first_lock_allowed_date(selected_year, selected_month_num)

    month_df = payroll[payroll["Month"].astype(str) == selected_month].copy()
    is_locked = month_df["Locked"].astype(str).str.lower().isin(["true", "1", "yes"]).any()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Employees", len(month_df))
    c2.metric("Total Without Special", f"₹{pd.to_numeric(month_df['Final_Salary_Without_Special'], errors='coerce').fillna(0).sum():,.0f}")
    c3.metric("Total With Special", f"₹{pd.to_numeric(month_df['Final_Salary_With_Special'], errors='coerce').fillna(0).sum():,.0f}")
    c4.metric("Status", "Locked" if is_locked else str(month_df["Payroll_Status"].iloc[0]))

    st.markdown("#### Review flags")
    flags = []
    for _, r in month_df.iterrows():
        if pd.to_numeric(r.get("Advance_Deduction", 0), errors="coerce") > pd.to_numeric(r.get("Monthly_Salary", 0), errors="coerce"):
            flags.append({"Emp_ID": r["Emp_ID"], "Name": r["Name"], "Flag": "Advance deduction greater than monthly salary"})
        if pd.to_numeric(r.get("LOP_Days", 0), errors="coerce") > 3:
            flags.append({"Emp_ID": r["Emp_ID"], "Name": r["Name"], "Flag": "High LOP days > 3"})
        if pd.to_numeric(r.get("Special_Deductions_Applied", 0), errors="coerce") > 0:
            flags.append({"Emp_ID": r["Emp_ID"], "Name": r["Name"], "Flag": "Special deduction applied"})
    if flags:
        st.warning("Please review flagged employees before approval.")
        render_sticky_report_table(pd.DataFrame(flags), "Review Flags")
    else:
        st.success("No major review flags found.")

    st.markdown("#### Employee-wise final month details")
    display_cols = [
        "Month", "Emp_ID", "Name", "Level", "Monthly_Salary", "Total_Days", "Daily_Wage",
        "Leave_Units", "Holiday_Exclusions", "Extra_Paid_Leaves", "Paid_Leave_Allowed", "Paid_Leave_Used", 
        "Leaves_After_Allowed_And_Exclusions", "LOP_Days", "Unused_Leaves",
        "Encashment", "Special_Deductions_Applied", "Uninformed_Special_Amount", "Collaborative_Special_Amount", "Apply_Uninformed_Impact", "Apply_Collaborative_Impact", "Collaborative_Impact_Mode", "Collaborative_Impact_Value", "Advance_Prior_Month", "Advance_Given_This_Month", "Advance_Deduction",
        "Advance_Balance_Open", "Advance_Balance_Close",
        "Final_Salary_Without_Special", "Final_Salary_With_Special",
        "Payroll_Status", "Approved_By", "Approved_At", "Locked"
    ]
    approval_display = month_df[[c for c in display_cols if c in month_df.columns]]
    render_sticky_report_table(approval_display, "Employee-wise Final Month Details")
    with st.expander("Audit spreadsheet view"):
        st.dataframe(approval_display, use_container_width=True, height=min(420, 80 + len(approval_display) * 36))

    st.download_button(
        "Download Final Monthly Excel",
        payroll_excel_bytes(selected_month),
        file_name=f"salary_month_end_{selected_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click=download_ack,
        args=("Final monthly Excel",)
    )

    if is_locked:
        st.info("This payroll is approved and locked. Editing/recalculation is blocked.")
        with st.expander("Admin emergency unlock"):
            reason = st.text_area("Reason for unlock")
            if st.button("Unlock Payroll"):
                if not reason.strip():
                    st.error("Unlock reason is mandatory.")
                else:
                    set_month_status(selected_month, "Unlocked", "", "", False)
                    add_audit(st.session_state.user["email"], "UNLOCK_PAYROLL", f"{selected_month}: {reason}")
                    st.success("Payroll unlocked. Adjustments are now allowed.")
                    st.rerun()
        return

    st.info(f"Lock rule: payroll can be approved only from {lock_allowed_date} and only after the payroll rows have been recalculated on/after that date.")

    with st.form("approve_payroll"):
        st.warning("Approval will lock this month. Leave, advance schedule, recalculation and profile adjustments will be blocked.")
        confirm = st.checkbox(f"I confirm payroll for {selected_month} is reviewed and ready for approval.")
        submitted = st.form_submit_button("Approve & Lock Payroll")
    if submitted:
        if not confirm:
            st.error("Please tick the confirmation checkbox.")
            return

        if not can_lock_payroll_month(selected_year, selected_month_num):
            st.error(payroll_lock_rule_message(selected_year, selected_month_num))
            return

        # Must be recalculated on/after the first lock-allowed date.
        recalculated_dates = pd.to_datetime(month_df.get("Last_Recalculated_At", pd.Series(dtype=str)), errors="coerce")
        if recalculated_dates.isna().all() or recalculated_dates.min().date() < lock_allowed_date:
            st.error(f"Please recalculate payroll on or after {lock_allowed_date} before approving/locking {selected_month}.")
            return

        now = datetime.now().isoformat(timespec="seconds")
        set_month_status(selected_month, "Approved", st.session_state.user["email"], now, True)
        add_audit(st.session_state.user["email"], "APPROVE_LOCK_PAYROLL", selected_month)
        set_confirmation(f"Payroll for {selected_month} approved and locked.", celebrate=True)
        st.rerun()


def employee_profile_page():
    st.subheader("Employee Payroll Profile")
    if st.session_state.user["role"] != "Admin":
        st.warning("Only Admin can review and update payroll profiles.")
        return

    employees = active_employees_for_user()
    choices = employee_choices(employees)
    if not choices:
        st.info("No active employees.")
        return

    payroll = read_table("payroll_items")
    current_months = payroll["Month"].dropna().unique().tolist() if not payroll.empty else []
    default_month = current_months[-1] if current_months else month_label(date.today().year, date.today().month)

    employee_pick = st.selectbox("Select employee", choices)
    selected_emp = extract_emp_id(employee_pick)
    selected_month = st.text_input("Payroll month", value=default_month, help="Format example: Apr-2026")

    emp = employees[employees["Emp_ID"].astype(str) == selected_emp].iloc[0]
    yr, mon = parse_month_label(selected_month)

    if is_month_locked(selected_month):
        st.error(f"{selected_month} payroll is approved and locked. Adjustments are disabled.")
        existing_locked = payroll[(payroll["Emp_ID"].astype(str) == selected_emp) & (payroll["Month"].astype(str) == selected_month)] if not payroll.empty else pd.DataFrame()
        if not existing_locked.empty:
            render_sticky_report_table(existing_locked, "Locked Payroll Calculation")
        return

    existing = payroll[(payroll["Emp_ID"].astype(str) == selected_emp) & (payroll["Month"].astype(str) == selected_month)] if not payroll.empty else pd.DataFrame()

    schedule = read_table("advance_schedule")
    emp_schedule_current = schedule[
        (schedule["Emp_ID"].astype(str) == selected_emp) &
        (schedule["Deduction_Month"].astype(str) == selected_month) &
        (schedule["Status"].astype(str).str.lower() == "open")
    ].copy() if not schedule.empty else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])
    scheduled_adv_default = pd.to_numeric(emp_schedule_current["Final_Deduction"], errors="coerce").fillna(0).sum() if not emp_schedule_current.empty else 0

    if not existing.empty:
        st.markdown("#### Current payroll calculation")
        render_sticky_report_table(existing, "Current Payroll Calculation")
        row = existing.iloc[0]
        default_extra = safe_float(row["Extra_Paid_Leaves"])
        default_special = safe_float(row["Special_Deductions_Applied"])
        default_adv = scheduled_adv_default if scheduled_adv_default > 0 else safe_float(row["Advance_Deduction"])
    else:
        st.info("No existing payroll row found. You can still calculate this employee.")
        default_extra = safe_float(emp.get("Extra_Paid_Leaves", 0))
        default_special = 0.0
        default_adv = scheduled_adv_default

    if st.session_state.get("last_special_impact_note"):
        st.success(st.session_state.last_special_impact_note)

    st.markdown("#### Leave matching check")
    leave_diag = build_leave_match_diagnostics(selected_month)
    if not leave_diag.empty:
        selected_diag = leave_diag[leave_diag["Emp_ID"].astype(str) == selected_emp]
        render_sticky_report_table(selected_diag, "Selected Employee Leave Match")
    st.markdown("#### Step 2: Person-wise Payroll Exclusions / Deductions")
    st.caption("Use this page only when you intentionally want to recalculate one selected employee. Special Impact Tools are intentionally available only here to avoid global payroll confusion.")
    exclusion_options = [0, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6]
    if default_extra not in exclusion_options:
        exclusion_options.append(default_extra)
        exclusion_options = sorted(exclusion_options)
    st.markdown("<div class='special-impact-heading'>Special Impact Tools</div>", unsafe_allow_html=True)
    st.info("Regular payroll counts leaves normally. Activate these only when this selected employee needs special uninformed/collaborative impact.")
    st.caption("Collaborative controls are dependent. The value field changes meaning based on the selected method.")

    c_sp1, c_sp2 = st.columns(2)
    apply_uninformed = c_sp1.selectbox(
        "Apply Uninformed Leave penalty?",
        ["No", "Yes"],
        index=0,
        help="Default is No. Turn Yes only when applying this special impact to the selected employee.",
        key=f"apply_uninformed_{selected_emp}_{selected_month}"
    )
    uninformed_penalty = c_sp2.number_input(
        "Penalty amount per uninformed leave (₹)",
        min_value=0.0,
        value=50.0,
        step=10.0,
        key=f"uninformed_penalty_{selected_emp}_{selected_month}"
    )

    c_sp3, c_sp4 = st.columns(2)
    apply_collab = c_sp3.selectbox(
        "Apply Collaborative Leave impact?",
        ["No", "Yes"],
        index=0,
        help="Default is No. Turn Yes only when collaborative leave should have extra impact for this selected employee.",
        key=f"apply_collab_{selected_emp}_{selected_month}"
    )
    collab_mode = c_sp4.selectbox(
        "Collaborative impact method",
        ["Deduct as leave days", "Additional amount per collaborative leave", "Fixed total collaborative deduction"],
        index=0,
        key=f"collab_mode_{selected_emp}_{selected_month}"
    )

    if collab_mode == "Deduct as leave days":
        collab_value = st.number_input(
            "Collaborative leave days to count per leave",
            min_value=0.0,
            max_value=10.0,
            value=1.5,
            step=0.5,
            help="Example: 1 collaborative leave = 1.5 leave days. This is NOT rupees.",
            key=f"collab_days_value_{selected_emp}_{selected_month}"
        )
        st.info("Selected method: day impact. The value affects leave units, not rupee amount.")
    elif collab_mode == "Additional amount per collaborative leave":
        collab_value = st.number_input(
            "Additional rupee deduction per collaborative leave (₹)",
            min_value=0.0,
            value=50.0,
            step=10.0,
            help="Example: value 50 means ₹50 per collaborative leave. It will NOT become 50 leave days.",
            key=f"collab_amount_per_leave_{selected_emp}_{selected_month}"
        )
        st.info("Selected method: amount per leave. Collaborative leave stays as 1 leave day and ₹ value is added separately.")
    else:
        collab_value = st.number_input(
            "Fixed total collaborative deduction for this employee/month (₹)",
            min_value=0.0,
            value=0.0,
            step=100.0,
            help="Example: value 500 means total ₹500 deduction for collaborative leave impact.",
            key=f"collab_fixed_amount_{selected_emp}_{selected_month}"
        )
        st.info("Selected method: fixed rupee amount. Collaborative leave stays as 1 leave day and this fixed amount is added separately.")

    special_config_profile = {
        "apply_uninformed": apply_uninformed == "Yes",
        "uninformed_penalty_per_leave": uninformed_penalty,
        "apply_collaborative": apply_collab == "Yes",
        "collaborative_mode": collab_mode,
        "collaborative_value": collab_value,
    }

    with st.form("recalc_form"):
        st.markdown("<div class='recalc-action-heading'>Final Recalculation Inputs</div>", unsafe_allow_html=True)
        st.caption("These inputs are part of the same employee-level recalculation. Click the button below to apply the selected Special Impact settings and save the updated payroll row.")
        extra_leave_override = st.selectbox(
            "Extra paid leaves / exclusions for this employee",
            exclusion_options,
            index=exclusion_options.index(default_extra),
            help="This is person-wise and applies only to the selected employee/month."
        )
        special_override = None
        advance_override = st.number_input("Advance deduction for this month", min_value=0.0, step=100.0, value=float(default_adv), help="This value is synced back to Advance Schedule and used in payroll calculation.")
        submitted = st.form_submit_button("Recalculate Selected Employee Payroll")
    if submitted:
        item, logs = calculate_employee_payroll(emp, yr, mon, extra_leave_override, special_override, advance_override, special_config=special_config_profile)
        if item is None:
            st.warning("This employee is omitted from this payroll month because the Date of Joining is after the selected salary month.")
            return

        regular_units_note = safe_float(item.get("Regular_Leave_Units_Before_Special", item.get("Leave_Units", 0)))
        special_units_note = safe_float(item.get("Special_Impact_Leave_Units", item.get("Leave_Units", 0)))
        difference_note = safe_float(item.get("Special_Impact_Leave_Difference", special_units_note - regular_units_note))
        st.session_state.last_special_impact_note = (
            f"Before/After Special Impact for {emp['Name']}: "
            f"Regular Payroll Leave Units = {regular_units_note:g}, "
            f"Special Impact Leave Units = {special_units_note:g}, "
            f"Difference Applied = {difference_note:g}."
        )

        payroll = upsert_employee_payroll_row(payroll, item, selected_month, selected_emp)
        write_table("payroll_items", payroll)

        sync_msg = sync_advance_schedule_override(selected_emp, selected_month, advance_override, st.session_state.user["email"])
        add_audit(st.session_state.user["email"], "SYNC_ADVANCE_FROM_EMPLOYEE_PROFILE", f"{selected_month} {selected_emp}: {sync_msg}")

        leave_log = read_table("leave_adjustment_log")
        leave_log = leave_log[~((leave_log["Emp_ID"].astype(str) == selected_emp) & (leave_log["Month"].astype(str) == selected_month))]
        if logs:
            leave_log = pd.concat([leave_log, pd.DataFrame(logs)], ignore_index=True)
        write_table("leave_adjustment_log", leave_log)

        st.session_state.last_recalculated_month = selected_month
        st.session_state.salary_summary_selected_month = selected_month
        add_audit(st.session_state.user["email"], "RECALCULATE_EMPLOYEE_PAYROLL", f"{selected_month} {selected_emp}")
        set_confirmation("Employee payroll recalculated and all relevant elements updated.", celebrate=True)
        st.rerun()

    st.markdown("#### Leave adjustment log")
    leave_log = read_table("leave_adjustment_log")
    st.dataframe(leave_log[(leave_log["Emp_ID"].astype(str) == selected_emp) & (leave_log["Month"].astype(str) == selected_month)], use_container_width=True)

    st.markdown("#### Advance schedule review")
    schedule = read_table("advance_schedule")
    emp_schedule = schedule[(schedule["Emp_ID"].astype(str) == selected_emp) & (schedule["Deduction_Month"].astype(str) == selected_month)] if not schedule.empty else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])
    st.dataframe(emp_schedule, use_container_width=True)

    if emp_schedule.empty:
        st.info("No advance schedule exists for this employee/month. If you enter an advance deduction above and recalculate, a manual adjustment schedule will be created.")
    else:
        st.success("Advance schedule is linked. Any advance deduction override above will update this schedule after recalculation.")

def employees_page():
    st.subheader("Employees")
    df = read_table("employees")

    search = st.text_input("Search employee by name, ID, level or status", placeholder="Type Gudiya, E_Gudiya, L0, L1, Active...")
    display_df = df.copy()
    if search.strip():
        s = search.strip().lower()
        display_df = display_df[
            display_df.astype(str).apply(lambda row: row.str.lower().str.contains(s, na=False).any(), axis=1)
        ]

    st.dataframe(display_df, use_container_width=True)

    if st.session_state.user["role"] != "Admin":
        st.info("Only Admin can add or edit employees.")
        return

    st.caption("Level rule: L0 = contractor paid by defined daily rate with 0 paid leaves and 0 leave encashment; L1 = 2 paid leaves/month; L2 = 4 paid leaves/month. Date of Joining controls first-month pro-rata salary/leave and future-month omission.")

    st.markdown("### Add New Employee")
    with st.form("add_employee_form"):
        name = st.text_input("Name")
        auto_emp_id = generate_emp_id_from_name(name)
        st.text_input("Auto Employee ID", value=auto_emp_id, disabled=True)
        c1, c2, c3 = st.columns(3)
        level = c1.selectbox("Level", LEVEL_OPTIONS, index=1, key="add_level", help="L0 = contractor: paid per day, no paid leave or encashment. L1 = 2 paid leaves. L2 = 4 paid leaves.")
        salary = c2.number_input("Monthly Salary / L0 Daily Rate", min_value=0.0, step=500.0, key="add_salary", help="For L0 contractors, enter the defined per-day rate. For L1/L2, enter monthly salary.")
        extra = c3.number_input("Default Extra Paid Leaves", min_value=0.0, step=0.5, key="add_extra", help="Ignored for L0 contractors because L0 has no paid leaves.")
        c4, c5 = st.columns(2)
        status = c4.selectbox("Status", ["Active", "Inactive"], key="add_status")
        supervisor = c5.text_input("Supervisor Email", value="supervisor@wagewise.local", key="add_supervisor")
        doj = st.date_input("Date of Joining", value=date.today(), key="add_doj", help="Used for first-month pro-rata salary and leave quota. If employee joins after a payroll month, they are omitted from that month.")
        add_submit = st.form_submit_button("Add Employee")
    if add_submit:
        clean_name = name.strip()
        emp_id = generate_emp_id_from_name(clean_name)
        if not clean_name:
            st.error("Employee name is required.")
            return
        if df["Name"].astype(str).str.lower().eq(clean_name.lower()).any():
            st.error("Duplicate blocked: employee with this name already exists.")
            return
        if emp_id in df["Emp_ID"].astype(str).tolist():
            st.error("Duplicate blocked: generated Employee ID already exists.")
            return
        if level == "L0":
            extra = 0.0
        df.loc[len(df)] = {"Emp_ID": emp_id, "Name": clean_name, "Level": level, "Monthly_Salary": salary, "Extra_Paid_Leaves": extra, "Status": status, "Supervisor_Email": supervisor.strip(), "Date_of_Joining": str(doj)}
        write_table("employees", df)
        add_audit(st.session_state.user["email"], "ADD_EMPLOYEE", emp_id)
        st.success(f"Employee added with ID: {emp_id}")
        st.rerun()

    st.divider()
    st.markdown("### Edit Existing Employee")
    if df.empty:
        st.info("No employees available to edit.")
        return

    filtered_choices_df = display_df if not display_df.empty else df
    choices = [f"{r.Emp_ID} - {r.Name}" for r in filtered_choices_df.itertuples()]
    selected = st.selectbox("Select employee to edit", choices)
    selected_emp_id = selected.split(" - ")[0]
    row = df[df["Emp_ID"].astype(str) == selected_emp_id].iloc[0]

    with st.form("edit_employee_form"):
        st.text_input("Employee ID", value=str(row["Emp_ID"]), disabled=True)
        c1, c2, c3 = st.columns(3)
        edit_name = c1.text_input("Name", value=str(row["Name"]))
        current_level = normalize_employee_level(row["Level"])
        edit_level = c2.selectbox("Level", LEVEL_OPTIONS, index=LEVEL_OPTIONS.index(current_level), key="edit_level", help="L0 = contractor: paid per day, no paid leave or encashment.")
        edit_status = c3.selectbox("Status", ["Active", "Inactive"], index=0 if str(row["Status"]) == "Active" else 1, key="edit_status")
        c4, c5 = st.columns(2)
        edit_salary = c4.number_input("Monthly Salary / L0 Daily Rate", min_value=0.0, step=500.0, value=float(row["Monthly_Salary"]), help="For L0 contractors, this value is treated as daily rate.")
        edit_extra = c5.number_input("Default Extra Paid Leaves", min_value=0.0, step=0.5, value=float(row["Extra_Paid_Leaves"]), help="Ignored for L0 contractors.")
        edit_supervisor = st.text_input("Supervisor Email", value=str(row["Supervisor_Email"]))
        edit_doj = st.text_input("Date of Joining (YYYY-MM-DD, optional)", value=str(row.get("Date_of_Joining", "")).strip(), help="Blank means existing employee/full-month eligible. Use YYYY-MM-DD for new employees to activate pro-rata logic.")
        update_submit = st.form_submit_button("Update Employee")
    if update_submit:
        clean_edit_name = edit_name.strip()
        if not clean_edit_name:
            st.error("Employee name is required.")
            return
        duplicate_name = df[
            (df["Name"].astype(str).str.lower() == clean_edit_name.lower()) &
            (df["Emp_ID"].astype(str) != selected_emp_id)
        ]
        if not duplicate_name.empty:
            st.error("Duplicate blocked: another employee already has this name.")
            return
        mask = df["Emp_ID"].astype(str) == selected_emp_id
        df.loc[mask, "Name"] = clean_edit_name
        df.loc[mask, "Level"] = edit_level
        df.loc[mask, "Monthly_Salary"] = edit_salary
        df.loc[mask, "Extra_Paid_Leaves"] = 0.0 if edit_level == "L0" else edit_extra
        df.loc[mask, "Status"] = edit_status
        df.loc[mask, "Supervisor_Email"] = edit_supervisor.strip()
        df.loc[mask, "Date_of_Joining"] = edit_doj.strip()
        write_table("employees", df)
        add_audit(st.session_state.user["email"], "EDIT_EMPLOYEE", selected_emp_id)
        set_confirmation("Employee updated successfully.", celebrate=True)
        st.rerun()

    st.markdown("### Quick Deactivate")
    if st.button("Deactivate Selected Employee", use_container_width=True):
        mask = df["Emp_ID"].astype(str) == selected_emp_id
        df.loc[mask, "Status"] = "Inactive"
        write_table("employees", df)
        add_audit(st.session_state.user["email"], "DEACTIVATE_EMPLOYEE", selected_emp_id)
        set_confirmation("Employee deactivated successfully.", celebrate=True)
        st.rerun()



def show_db_action_result_panel():
    """Large visible result panel for database actions. Balloons trigger once per action."""
    result = st.session_state.get("last_db_action_result")
    if not result:
        return

    status = str(result.get("status", ""))
    action = str(result.get("action", "Database Action"))
    ts = str(result.get("timestamp", ""))
    message = str(result.get("message", ""))
    result_id = f"{action}|{ts}|{status}"

    if status == "success":
        st.success(f"✅ {action} completed successfully")
        if st.session_state.get("last_balloon_result_id") != result_id:
            try:
                st.balloons()
            except Exception:
                pass
            st.session_state.last_balloon_result_id = result_id
    else:
        st.error(f"❌ {action} failed")

    border = "#1F7A4D" if status == "success" else "#B42318"
    bg = "#F2FBF6" if status == "success" else "#FFF5F5"
    st.markdown(
        f"""
        <div style="border:2px solid {border};border-radius:16px;padding:14px 16px;margin:10px 0;background:{bg};color:#172033;">
            <div style="font-weight:900;font-size:18px;margin-bottom:6px;">Last Database Action Result</div>
            <div><b>Action:</b> {action}</div>
            <div><b>Status:</b> {status}</div>
            <div><b>Time:</b> {ts}</div>
            <div><b>Message:</b> {message}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    before = result.get("before_counts")
    after = result.get("after_counts")
    if before is not None or after is not None:
        with st.expander("View row counts before/after", expanded=False):
            if before is not None:
                st.markdown("##### Before")
                st.dataframe(pd.DataFrame(before), use_container_width=True)
            if after is not None:
                st.markdown("##### After")
                st.dataframe(pd.DataFrame(after), use_container_width=True)


def database_health_panel():
    st.markdown("### Storage Health")
    if is_demo_mode():
        st.info("Demo Mode is ON. Database setup details are hidden. Turn Demo Mode OFF from System Admin → Demo Mode Guide to manage database health.")
        return
    status = db_connection_status_text()

    status_class = "db-ok" if "connected" in status.lower() else ("db-warn" if "fallback" in status.lower() else "db-danger")
    st.markdown(
        f"""
        <div class="db-health-shell">
            <div class="db-health-title">Storage Status</div>
            <div class="db-status-pill {status_class}">{status}</div>
            <div class="db-health-help">
                Use this page only when setting up or troubleshooting database storage.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    show_db_action_result_panel()

    st.markdown("#### Database Actions")
    st.caption("For day-to-day use, you should not need Reset or Seed again. Use Refresh to check row counts.")

    c1, c2, c3 = st.columns(3)
    if c1.button("Refresh DB Health", use_container_width=True, key="db_refresh_button", type="secondary"):
        clear_db_setup_cache()
        st.session_state.last_db_action_result = {
            "action": "Refresh DB Health",
            "status": "success",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "message": "Database health refreshed.",
            "before_counts": None,
            "after_counts": get_db_row_counts().to_dict("records"),
        }
        st.rerun()

    if c2.button("Load Cloud Data from Backup", use_container_width=True, key="db_seed_button", type="primary"):
        before_counts = get_db_row_counts().to_dict("records")
        try:
            msg = seed_supabase_from_csv(overwrite=True)
            clear_db_setup_cache()
            after_counts = get_db_row_counts().to_dict("records")
            add_audit(st.session_state.user["email"], "SEED_SUPABASE_FROM_CSV", msg)
            st.session_state.db_health_message = msg
            st.session_state.last_db_action_result = {
                "action": "Load Cloud Data from Backup",
                "status": "success" if "success" in str(msg).lower() else "failed",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "message": msg,
                "before_counts": before_counts,
                "after_counts": after_counts,
            }
            st.rerun()
        except Exception as e:
            after_counts = get_db_row_counts().to_dict("records")
            st.session_state.db_health_message = f"Seed failed: {e}"
            st.session_state.last_db_action_result = {
                "action": "Load Cloud Data from Backup",
                "status": "failed",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "message": str(e),
                "before_counts": before_counts,
                "after_counts": after_counts,
            }
            st.rerun()

    if c3.button("Export Cloud Data Backup", use_container_width=True, key="db_export_button", type="secondary"):
        before_counts = get_db_row_counts().to_dict("records")
        try:
            msg = export_supabase_to_csv()
            after_counts = get_db_row_counts().to_dict("records")
            add_audit(st.session_state.user["email"], "EXPORT_SUPABASE_TO_CSV", msg)
            st.session_state.db_health_message = msg
            st.session_state.last_db_action_result = {
                "action": "Export Cloud Data Backup",
                "status": "success" if "success" in str(msg).lower() else "failed",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "message": msg,
                "before_counts": before_counts,
                "after_counts": after_counts,
            }
            st.rerun()
        except Exception as e:
            after_counts = get_db_row_counts().to_dict("records")
            st.session_state.db_health_message = f"Export failed: {e}"
            st.session_state.last_db_action_result = {
                "action": "Export Cloud Data Backup",
                "status": "failed",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "message": str(e),
                "before_counts": before_counts,
                "after_counts": after_counts,
            }
            st.rerun()

    with st.expander("Danger Zone: Reset App Data Tables", expanded=False):
        st.warning("Use this only if seeding fails due to old Cloud Storage indexes/setup. This drops and recreates only sms_* tables.")
        confirm_reset = st.checkbox("I understand this will reset only SMS Cloud Storage tables", key="confirm_db_reset")
        if st.button("Reset App Data Tables", use_container_width=True, key="db_reset_tables_button", type="secondary", disabled=not confirm_reset):
            before_counts = get_db_row_counts().to_dict("records")
            try:
                msg = reset_supabase_sms_tables()
                clear_db_setup_cache()
                after_counts = get_db_row_counts().to_dict("records")
                add_audit(st.session_state.user["email"], "RESET_SUPABASE_SMS_TABLES", msg)
                st.session_state.db_health_message = msg
                st.session_state.last_db_action_result = {
                    "action": "Reset App Data Tables",
                    "status": "success" if "success" in str(msg).lower() else "failed",
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "message": msg,
                    "before_counts": before_counts,
                    "after_counts": after_counts,
                }
                st.rerun()
            except Exception as e:
                after_counts = get_db_row_counts().to_dict("records")
                st.session_state.db_health_message = f"Reset failed: {e}"
                st.session_state.last_db_action_result = {
                    "action": "Reset App Data Tables",
                    "status": "failed",
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "message": str(e),
                    "before_counts": before_counts,
                    "after_counts": after_counts,
                }
                st.rerun()

    counts = get_csv_row_counts().merge(get_db_row_counts(), on="Table", how="outer")
    with st.expander("Row Count Validation", expanded=True):
        st.dataframe(counts, use_container_width=True)

    try:
        key_tables = ["employees", "leave_entries", "advance_cases", "advance_schedule", "users"]
        db_ok_lines = []
        for t in key_tables:
            row = counts[counts["Table"].astype(str) == t]
            if not row.empty and "DB Rows" in row.columns:
                db_ok_lines.append(f"{t}: {row['DB Rows'].iloc[0]}")
        if db_ok_lines:
            st.info("Current Cloud Storage row counts → " + " | ".join(db_ok_lines))
    except Exception:
        pass

    expected = {"employees": 7, "leave_entries": 62, "advance_cases": 6, "advance_schedule": 6, "users": 1}
    rows = []
    for table, exp in expected.items():
        row = counts[counts["Table"].astype(str) == table]
        csv_rows = row["CSV Rows"].iloc[0] if not row.empty and "CSV Rows" in row.columns else ""
        db_rows = row["DB Rows"].iloc[0] if not row.empty and "DB Rows" in row.columns else ""
        status_text = "OK" if str(db_rows).isdigit() and int(db_rows) >= exp else "Check"
        if status_text == "Check" and str(csv_rows).isdigit() and int(csv_rows) >= exp and not str(db_rows).isdigit():
            status_text = "CSV OK / DB not active"
        rows.append({"Table": table, "Expected Minimum": exp, "CSV Rows": csv_rows, "DB Rows": db_rows, "Status": status_text})
    with st.expander("Functional Parity Minimum Checks", expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with st.expander("Schema Alignment", expanded=False):
        st.dataframe(get_setup_alignment_report(), use_container_width=True)

    st.caption("Performance mode is active: normal pages do not run database health checks.")


def demo_mode_guide_panel():
    st.markdown("### Demo Mode Guide")
    st.write("Use Demo Mode during client walkthroughs when you want the app to look simpler and business-focused.")
    st.markdown("""
    **When Demo Mode is ON**
    - Technical database messages are hidden.
    - Business guidance messages are shown.
    - Payroll Control Centre becomes the recommended starting point.
    - Screens feel cleaner for end-user review.

    **When Demo Mode is OFF**
    - System Admin users can see database health, seed/export/reset actions and troubleshooting details.
    - Use OFF mode only during setup, admin checks or support.
    """)
    if st.button("Turn Demo Mode ON", use_container_width=True, key="demo_on_from_guide"):
        st.session_state.demo_mode = True
        set_confirmation("Demo Mode turned ON.", celebrate=True)
        st.rerun()
    if st.button("Turn Demo Mode OFF", use_container_width=True, key="demo_off_from_guide"):
        st.session_state.demo_mode = False
        set_confirmation("Demo Mode turned OFF.", celebrate=True)
        st.rerun()


def tech_page():
    st.subheader("Setup, Recovery & Technical Checks")
    demo_mode_panel("tech")
    if not is_demo_mode():
        st.info(f"Storage mode: {db_connection_status_text()}")
        if st.session_state.get("last_db_runtime_issue"):
            st.warning(st.session_state.last_db_runtime_issue)
    else:
        st.caption("Demo Mode hides technical database details. Turn OFF Demo Mode for setup/troubleshooting.")
    if st.session_state.user["role"] != "Admin":
        st.warning("Only Admin users can access System Admin utilities.")
        return

    requested_section = st.session_state.get("page", "Advance Master")
    if requested_section not in ["Advance Master", "Access Manager", "Recovery", "Technical Checks", "Demo Mode Guide", "System Notes"]:
        requested_section = "Advance Master"
    st.markdown(f"### {requested_section}")

    def build_case_schedule_from_inputs(advance_id, emp_id, amount, start_month_label, first_deduction, remaining_months, status):
        start_year, start_month = parse_month_label(start_month_label)
        first_deduction = min(float(first_deduction), float(amount))
        balance = max(0, float(amount) - first_deduction)
        rows = []

        if first_deduction > 0:
            rows.append({
                "Advance_ID": advance_id,
                "Emp_ID": emp_id,
                "Deduction_Month": month_label(start_year, start_month),
                "Scheduled_Deduction": round(first_deduction, 2),
                "Admin_Updated_Deduction": "",
                "Final_Deduction": round(first_deduction, 2),
                "Status": status,
                "Updated_By": st.session_state.user["email"],
                "Updated_At": datetime.now().isoformat(timespec="seconds"),
            })

        if int(remaining_months) > 0 and balance > 0:
            per_month = round(balance / int(remaining_months), 2)
            running_total = 0.0
            for i in range(int(remaining_months)):
                y2, m2 = add_months(start_year, start_month, i + 1)
                amt = per_month
                if i == int(remaining_months) - 1:
                    amt = round(balance - running_total, 2)
                running_total += amt
                rows.append({
                    "Advance_ID": advance_id,
                    "Emp_ID": emp_id,
                    "Deduction_Month": month_label(y2, m2),
                    "Scheduled_Deduction": amt,
                    "Admin_Updated_Deduction": "",
                    "Final_Deduction": amt,
                    "Status": status,
                    "Updated_By": st.session_state.user["email"],
                    "Updated_At": datetime.now().isoformat(timespec="seconds"),
                })

        return pd.DataFrame(rows)

    def get_recon_table(cases, schedule):
        rows = []
        for _, c in cases.iterrows():
            adv_id = str(c["Advance_ID"])
            amount = float(pd.to_numeric(c.get("Amount_Given", 0), errors="coerce") or 0)
            srows = schedule[schedule["Advance_ID"].astype(str) == adv_id] if not schedule.empty else pd.DataFrame()
            total = float(pd.to_numeric(srows.get("Final_Deduction", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not srows.empty else 0
            rows.append({
                "Advance_ID": adv_id,
                "Emp_ID": c.get("Emp_ID", ""),
                "Amount_Given": amount,
                "Schedule_Total": round(total, 2),
                "Difference": round(amount - total, 2),
                "Reconciled": "Yes" if round(amount - total, 2) == 0 else "No",
            })
        return pd.DataFrame(rows)

    def employee_display(emp_id):
        employees = read_table("employees")
        match = employees[employees["Emp_ID"].astype(str) == str(emp_id)] if not employees.empty else pd.DataFrame()
        if match.empty:
            return str(emp_id)
        return f"{match.iloc[0]['Name']} ({emp_id})"

    if requested_section == "Advance Master":
        st.markdown("### Unified Advance Editor")
        st.caption("Select one Advance ID. Employee is read-only to protect data integrity. Editing amount/repayment rebuilds the schedule for the same employee.")

        cases = read_table("advance_cases")
        schedule = read_table("advance_schedule")
        if cases.empty:
            st.success("No advance cases found. This is valid — payroll will treat advance deduction as ₹0.")

        if cases.empty:
            st.info("No advance cases found. Use Create New Advance below.")
        else:
            st.markdown("#### 1. Reconciliation Status")
            recon = get_recon_table(cases, schedule)
            st.dataframe(recon, use_container_width=True)

            bad = recon[recon["Reconciled"] == "No"]
            if not bad.empty:
                st.warning("Some advances are not reconciled. Select the Advance ID below and save to rebuild the schedule.")

            st.markdown("#### 2. Select Advance")
            case_ids = cases["Advance_ID"].astype(str).tolist()
            selected_case = st.selectbox("Advance ID", case_ids)
            case_row = cases[cases["Advance_ID"].astype(str) == selected_case].iloc[0]
            emp_id_locked = str(case_row["Emp_ID"])
            case_schedule = schedule[schedule["Advance_ID"].astype(str) == selected_case].copy() if not schedule.empty else pd.DataFrame(columns=read_table("advance_schedule").columns)

            st.markdown("#### 3. Advance Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Employee", employee_display(emp_id_locked))
            c2.metric("Advance ID", selected_case)
            current_schedule_total = float(pd.to_numeric(case_schedule.get("Final_Deduction", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not case_schedule.empty else 0
            c3.metric("Schedule Total", f"₹{current_schedule_total:,.0f}")

            st.markdown("#### 4. Edit Advance Controls")
            with st.form("unified_advance_case_form"):
                st.text_input("Employee", value=employee_display(emp_id_locked), disabled=True, help="Employee is locked to this Advance ID to prevent reconciliation errors.")
                c1, c2, c3 = st.columns(3)
                amount = c1.number_input("Amount Given", min_value=0.0, value=float(case_row["Amount_Given"]), step=100.0)
                first_deduction = c2.number_input("First Month Deduction", min_value=0.0, value=float(case_row["First_Month_Deduction"]), step=100.0)
                remaining_months = c3.number_input("Remaining Months", min_value=0, value=int(float(case_row["Remaining_Months"])), step=1)

                c4, c5 = st.columns(2)
                start_month_value = str(case_row["Refund_Start_Month"])
                refund_start_date = c4.date_input(
                    "Refund Start Month",
                    value=month_label_to_date(start_month_value),
                    help="Pick any date in the refund start month. System stores it as Apr-2026 format."
                )
                start_month = date_to_month_label(refund_start_date)
                c4.caption(f"Selected month: {start_month}")
                status_options = ["Open", "Closed", "Cancelled"]
                current_status = str(case_row["Status"]) if str(case_row["Status"]) in status_options else "Open"
                status = c5.selectbox("Status", status_options, index=status_options.index(current_status))
                remarks = st.text_area("Remarks", value=str(case_row.get("Remarks", "")))

                st.info("Save will rebuild the full schedule for the same employee so case and schedule reconcile.")
                save_case = st.form_submit_button("Save Unified Advance")

            if save_case:
                try:
                    parse_month_label(start_month)
                    if first_deduction > amount:
                        st.error("First Month Deduction cannot be greater than Amount Given.")
                    else:
                        case_mask = cases["Advance_ID"].astype(str) == selected_case
                        cases.loc[case_mask, "Emp_ID"] = emp_id_locked
                        cases.loc[case_mask, "Amount_Given"] = amount
                        cases.loc[case_mask, "Refund_Start_Month"] = start_month
                        cases.loc[case_mask, "First_Month_Deduction"] = first_deduction
                        cases.loc[case_mask, "Remaining_Months"] = remaining_months
                        cases.loc[case_mask, "Status"] = status
                        cases.loc[case_mask, "Remarks"] = remarks
                        rebuilt = build_case_schedule_from_inputs(selected_case, emp_id_locked, amount, start_month, first_deduction, remaining_months, status)
                        schedule = schedule[schedule["Advance_ID"].astype(str) != selected_case].copy()
                        if not rebuilt.empty:
                            schedule = pd.concat([schedule, rebuilt], ignore_index=True)
                        b1, b2 = safe_write_advance_tables(cases, schedule, label="before_unified_advance_save", selected_advance_id=selected_case)

                        add_audit(st.session_state.user["email"], "TECH_SAVE_UNIFIED_ADVANCE", f"{selected_case}; backups: {b1}, {b2}")
                        set_confirmation(f"Unified advance saved and reconciled for {selected_case}.", celebrate=True)
                        st.rerun()
                except Exception as e:
                    st.error(f"Could not save: {e}")

            st.markdown("#### 5. Schedule Preview")
            if case_schedule.empty:
                st.info("No schedule exists. Use Save Unified Advance to generate it.")
            else:
                st.dataframe(case_schedule, use_container_width=True)
                schedule_total = float(pd.to_numeric(case_schedule["Final_Deduction"], errors="coerce").fillna(0).sum())
                difference = round(float(case_row["Amount_Given"]) - schedule_total, 2)
                if difference == 0:
                    st.success("Selected advance is reconciled.")
                else:
                    st.error(f"Selected advance is not reconciled. Difference: ₹{difference:,.2f}")

        st.divider()
        st.markdown("### Create New Advance")
        st.caption("Employee selection is only available while creating a new advance. After creation, Employee is locked for that Advance ID.")
        with st.form("create_unified_advance"):
            employees = read_table("employees")
            active = employees[employees["Status"].astype(str).str.lower() == "active"] if not employees.empty else employees
            choices = [f"{r.Emp_ID} - {r.Name}" for r in active.itertuples()] if not active.empty else []
            if not choices:
                st.info("No active employees available.")
            else:
                emp_pick_new = st.selectbox("Employee", choices, key="new_adv_emp")
                adv_date = st.date_input("Advance Date")
                amount_new = st.number_input("Amount Given", min_value=0.0, step=100.0, key="new_adv_amount")
                refund_start_date_new = st.date_input(
                    "Refund Start Month",
                    value=date.today().replace(day=1),
                    help="Pick any date in the refund start month. System stores it as Apr-2026 format.",
                    key="new_adv_month_date"
                )
                start_month_new = date_to_month_label(refund_start_date_new)
                st.caption(f"Selected refund start month: {start_month_new}")
                first_new = st.number_input("First Month Deduction", min_value=0.0, step=100.0, key="new_adv_first")
                remaining_new = st.number_input("Remaining Months", min_value=0, step=1, key="new_adv_remaining")
                remarks_new = st.text_area("Remarks", key="new_adv_remarks")
                create_new = st.form_submit_button("Create Unified Advance")

        if 'create_new' in locals() and create_new and choices:
            try:
                parse_month_label(start_month_new)
                emp_id_new = extract_emp_id(emp_pick_new)
                if amount_new <= 0:
                    st.error("Amount must be greater than 0.")
                elif first_new > amount_new:
                    st.error("First Month Deduction cannot be greater than Amount Given.")
                else:
                    new_id = f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    cases = read_table("advance_cases")
                    schedule = read_table("advance_schedule")
                    cases.loc[len(cases)] = [new_id, emp_id_new, str(adv_date), amount_new, start_month_new, first_new, remaining_new, "Open", remarks_new, st.session_state.user["email"], datetime.now().isoformat(timespec="seconds")]
                    new_sched = build_case_schedule_from_inputs(new_id, emp_id_new, amount_new, start_month_new, first_new, remaining_new, "Open")
                    if not new_sched.empty:
                        schedule = pd.concat([schedule, new_sched], ignore_index=True)
                    b1, b2 = safe_write_advance_tables(cases, schedule, label="before_unified_advance_create", selected_advance_id=new_id)
                    add_audit(st.session_state.user["email"], "TECH_CREATE_UNIFIED_ADVANCE", f"{new_id}; backups: {b1}, {b2}")
                    set_confirmation(f"New unified advance created and reconciled: {new_id}.", celebrate=True)
                    st.rerun()
            except Exception as e:
                st.error(f"Could not create advance: {e}")

    if requested_section == "Access Manager":
        st.markdown("### Access Manager")
        st.caption("Manage login users, role-card permissions, activation status and fallback password access.")

        if st.button("Repair Users Storage Columns", use_container_width=True, key="repair_users_storage_columns"):
            ok, msg = ensure_users_table_storage_columns()
            if ok:
                set_confirmation("Users storage columns verified/repaired.", celebrate=True)
                st.session_state.page = "Access Manager"
                st.session_state.scroll_target_note = "Users storage repaired. You are still in Access Manager."
                st.rerun()
            else:
                st.error(f"Users storage repair failed: {msg}")

        users = ensure_user_access_columns(read_table("users"))
        users, recovered = ensure_recovery_admin_exists(users)
        if recovered:
            write_table("users", users)
            st.warning("User access recovery was applied because no active Admin login was found.")
        if "active" not in users.columns:
            users["active"] = True

        display_users = users.copy()
        display_users["password_hash"] = "••••••••"
        display_cols = ["email", "name", "role", "active", "allow_admin", "allow_supervisor", "password_hash"]
        st.dataframe(display_users[[c for c in display_cols if c in display_users.columns]], use_container_width=True)

        st.info("Role access controls which role cards appear after login. For Google/OIDC users, add the exact Gmail ID and leave fallback password blank. Never enter a Gmail password in WageWise.")

        st.markdown("#### Create New Login")
        with st.form("create_user_form"):
            c1, c2 = st.columns(2)
            new_email = c1.text_input("Login Email ID")
            new_name = c2.text_input("Display Name")
            c3, c4 = st.columns(2)
            new_role = c3.selectbox("Role Label", ["All Access", "Admin", "Supervisor"], index=0)
            new_active = c4.selectbox("Status", ["Active", "Inactive"], index=0)
            st.markdown("##### Role-card access")
            a1, a2 = st.columns(2)
            new_allow_admin = a1.checkbox("Allow Admin card", value=True)
            new_allow_supervisor = a2.checkbox("Allow Supervisor card", value=True)
            st.caption("For Google/OIDC users, do not enter Gmail password. Leave fallback password blank unless you want backup password login.")
            c5, c6 = st.columns(2)
            new_password = c5.text_input("Optional fallback password", type="password", placeholder="Leave blank for OIDC-only user")
            new_confirm = c6.text_input("Confirm fallback password", type="password", placeholder="Leave blank for OIDC-only user")
            create_user = st.form_submit_button("Create Login / Access")

        if create_user:
            clean_email = new_email.strip().lower()
            clean_name = new_name.strip() or clean_email
            if not clean_email:
                st.error("Login Email ID is required.")
            elif clean_email in users["email"].astype(str).str.lower().tolist():
                st.error("This login email already exists.")
            elif not any([new_allow_admin, new_allow_supervisor]):
                st.error("At least one role-card access must be enabled.")
            elif new_password and len(new_password) < 6:
                st.error("Fallback password must be at least 6 characters, or leave it blank for OIDC-only access.")
            elif new_password != new_confirm:
                st.error("Fallback passwords do not match.")
            else:
                password_hash_value = hash_password(new_password) if new_password else oidc_access_user_password_hash(clean_email)
                new_row = {
                    "email": clean_email,
                    "name": clean_name,
                    "role": new_role,
                    "password_hash": password_hash_value,
                    "active": True if new_active == "Active" else False,
                    "allow_admin": new_allow_admin,
                    "allow_supervisor": new_allow_supervisor,
                }
                for col in new_row:
                    if col not in users.columns:
                        users[col] = ""
                users.loc[len(users), list(new_row.keys())] = list(new_row.values())
                ok, fresh_or_msg = force_write_users_to_active_storage(users)
                if not ok or not verify_user_write(clean_email):
                    st.error(f"User save verification failed. Details: {fresh_or_msg}. Please open Storage Health or run the recovery SQL.")
                    return
                add_audit(st.session_state.user["email"], "CREATE_USER", clean_email)
                set_confirmation(f"Login created and verified for {clean_email}.", celebrate=True)
                st.session_state.page = "Access Manager"
                st.session_state.scroll_target_note = "User created. You are still in Access Manager."
                st.rerun()

        st.divider()
        st.markdown("#### Edit Existing Login")
        if users.empty:
            st.info("No users available.")
        else:
            user_options = users["email"].astype(str).tolist()
            selected_email = st.selectbox("Select login to edit", user_options)
            row = users[users["email"].astype(str) == selected_email].iloc[0]

            with st.form("edit_user_form"):
                edited_email = st.text_input("Login Email ID", value=str(row["email"]))
                edited_name = st.text_input("Display Name", value=str(row["name"]))
                role_options = ["All Access", "Admin", "Supervisor"]
                current_role_raw = str(row["role"])
                current_role = "Admin" if current_role_raw in ["Tech", "System Admin"] else (current_role_raw if current_role_raw in role_options else "All Access")
                edited_role = st.selectbox("Legacy Role Label", role_options, index=role_options.index(current_role))
                current_active = str(row["active"]).lower() in ["true", "1", "yes", "active"]
                edited_active = st.selectbox("Status", ["Active", "Inactive"], index=0 if current_active else 1)

                st.markdown("##### Role-card access")
                b1, b2 = st.columns(2)
                edited_allow_admin = b1.checkbox("Allow Admin card", value=boolish(row.get("allow_admin", True)), key=f"edit_allow_admin_{selected_email}")
                edited_allow_supervisor = b2.checkbox("Allow Supervisor card", value=boolish(row.get("allow_supervisor", True)), key=f"edit_allow_supervisor_{selected_email}")

                st.caption("Optional: set/change fallback password only. Do not enter Gmail password.")
                edited_password = st.text_input("New fallback password (leave blank to keep old)", type="password")
                edited_confirm = st.text_input("Confirm new fallback password", type="password")
                update_user = st.form_submit_button("Update Login")

            if update_user:
                old_email = selected_email
                clean_email = edited_email.strip().lower()
                duplicate = users[
                    (users["email"].astype(str).str.lower() == clean_email) &
                    (users["email"].astype(str) != old_email)
                ]
                if not clean_email:
                    st.error("Login Email ID is required.")
                elif not duplicate.empty:
                    st.error("Another login already uses this email ID.")
                elif not any([edited_allow_admin, edited_allow_supervisor]):
                    st.error("At least one role-card access must be enabled.")
                elif edited_password and len(edited_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif edited_password and edited_password != edited_confirm:
                    st.error("Passwords do not match.")
                else:
                    mask = users["email"].astype(str) == old_email
                    users.loc[mask, "email"] = clean_email
                    users.loc[mask, "name"] = edited_name.strip() or clean_email
                    users.loc[mask, "role"] = edited_role
                    users.loc[mask, "active"] = True if edited_active == "Active" else False
                    users.loc[mask, "allow_admin"] = edited_allow_admin
                    users.loc[mask, "allow_supervisor"] = edited_allow_supervisor
                    if edited_password:
                        users.loc[mask, "password_hash"] = hash_password(edited_password)
                    ok, fresh_or_msg = force_write_users_to_active_storage(users)
                    if not ok or not verify_user_write(clean_email):
                        st.error(f"User update verification failed. Details: {fresh_or_msg}. Please open Storage Health or run the recovery SQL.")
                        return
                    add_audit(st.session_state.user["email"], "EDIT_USER", f"{old_email} -> {clean_email}")
                    set_confirmation(f"Login updated and verified for {clean_email}.", celebrate=True)
                    st.session_state.page = "Access Manager"
                    st.session_state.scroll_target_note = "User updated. You are still in Access Manager."
                    st.rerun()

            st.markdown("#### Delete Login")
            st.warning("Deleting a login removes access immediately. Keep at least one login in the system.")
            confirm_delete = st.checkbox(f"I confirm I want to delete {selected_email}")
            if st.button("Delete Selected Login", use_container_width=True):
                if not confirm_delete:
                    st.error("Please tick the confirmation checkbox before deleting.")
                elif len(users) <= 1:
                    st.error("At least one login must remain in the system.")
                else:
                    users = users[users["email"].astype(str) != selected_email].copy()
                    ok, fresh_or_msg = force_write_users_to_active_storage(users)
                    if not ok:
                        st.error(f"User delete verification failed. Details: {fresh_or_msg}.")
                        return
                    clear_db_table_cache("users")
                    if db_enabled():
                        fresh_users = ensure_user_access_columns(pd.read_sql_query('SELECT * FROM "sms_users"', get_db_engine()))
                    else:
                        fresh_users = ensure_user_access_columns(read_table_csv("users"))
                    if selected_email in fresh_users["email"].astype(str).tolist():
                        st.error("User delete verification failed. The login is still present in storage.")
                        return
                    add_audit(st.session_state.user["email"], "DELETE_USER", selected_email)
                    set_confirmation(f"Login deleted and verified: {selected_email}.", celebrate=True)
                    st.rerun()

    if requested_section == "Recovery":
        section_rollback_panel()

    if requested_section == "Technical Checks":
        database_health_panel()

    if requested_section == "Demo Mode Guide":
        demo_mode_guide_panel()

    if requested_section == "System Notes":
        st.markdown("### Utility definitions")
        st.info("Advance ID is the single control point. Employee is locked after advance creation to protect data integrity.")
        st.info("Unified Advance Editor writes both advance_cases and advance_schedule together.")
        st.info("Amount controls use ₹100 increments.")



def system_health_page():
    st.subheader("System Health Check")
    st.caption("Pre-client readiness checks for empty data, missing columns and basic table health.")

    checks = []
    for table_name, required_cols in REQUIRED_FILES.items():
        try:
            df = read_table(table_name)
            missing = [c for c in required_cols if c not in df.columns]
            status = "OK" if not missing else "Missing columns"
            detail = f"Rows: {len(df)}" if not missing else f"Missing: {', '.join(missing)}"
            checks.append({"Area": table_name, "Status": status, "Detail": detail})
        except Exception as e:
            checks.append({"Area": table_name, "Status": "Error", "Detail": str(e)})

    health_df = pd.DataFrame(checks)
    st.dataframe(health_df, use_container_width=True)

    errors = health_df[health_df["Status"] != "OK"]
    if errors.empty:
        st.success("All core data files are readable and structurally safe.")
    else:
        st.error("Some checks need attention before client demo.")

    st.markdown("### Important empty-data scenarios")
    st.info("No leaves: valid. Payroll treats employees as present.")
    st.info("No advance cases: valid. Payroll treats advance deduction as ₹0.")
    st.info("No advance schedule: valid. Payroll treats advance deduction as ₹0.")
    st.info("No advance schedule: valid. Advance deduction is ₹0.")
    st.info("No payroll generated: Salary Summary shows a message instead of error.")


def logs_page():
    st.subheader("Logs and Cleansing")
    c1, c2 = st.columns(2)
    if c1.button("Run Data Cleansing"):
        cleanse_data()
        add_audit(st.session_state.user["email"], "RUN_CLEANSING", "Manual cleansing")
        st.success("Cleansing completed.")
    if c2.button("Refresh Logs"):
        st.rerun()
    st.markdown("#### Audit log")
    st.dataframe(read_table("audit_log").tail(150), use_container_width=True)
    st.markdown("#### Cleansing log")
    st.dataframe(read_table("cleansing_log").tail(150), use_container_width=True)

def render_to_top_button():
    """Small bottom utility to jump back to the top of the app without manual scrolling."""
    st.markdown("---")
    if st.button("⬆ To the Top", use_container_width=True, key="ww_to_top_button"):
        components.html(
            """
            <script>
            (function() {
                function scrollTopNow() {
                    try { window.parent.scrollTo({top: 0, behavior: 'smooth'}); } catch(e) {}
                    try { window.parent.document.querySelector('[data-testid="stAppViewContainer"]').scrollTo({top: 0, behavior: 'smooth'}); } catch(e) {}
                    try { window.parent.document.documentElement.scrollTop = 0; } catch(e) {}
                    try { window.parent.document.body.scrollTop = 0; } catch(e) {}
                }
                scrollTopNow();
                setTimeout(scrollTopNow, 150);
                setTimeout(scrollTopNow, 500);
            })();
            </script>
            """,
            height=0,
            scrolling=False,
        )


def main():
    st.set_page_config(page_title="WageWise", page_icon="💼", layout="wide")
    apply_theme()

    # Speed: do not run data/table checks before showing the login screen.
    if "auth_user" not in st.session_state:
        if oidc_enabled() and handle_oidc_authenticated_user():
            ensure_data_files()
        else:
            login_screen()
            return
    else:
        ensure_data_files()

    if not st.session_state.get("user"):
        role_selection_page()
        return

    apply_v116_1_backend_requested_actions()

    render_wagewise_header()
    show_confirmation_area()
    page = page_navigation()
    render_page_heading(page)
    render_selected_content_anchor()
    if page == "Dashboard":
        dashboard_page()
    elif page == "Payroll Control Centre":
        payroll_control_centre_page()
    elif page == "Salary Summary":
        salary_summary_page()
    elif page == "Leave":
        leave_page()
    elif page in ["Access Manager", "Advance Master", "Recovery", "Technical Checks", "Demo Mode Guide", "System Notes", "System Admin", "Tech"]:
        tech_page()
    elif page == "Bulk Leave Upload":
        bulk_leave_upload_page()
    elif page == "System Health":
        system_health_page()
    elif page == "Holiday":
        holiday_page()
    elif page == "Advance":
        advance_page()
    elif page in ["Payroll", "Payroll Calculation"]:
        payroll_page()
    elif page == "Payroll Approval":
        payroll_approval_page()
    elif page == "Employee Profile":
        employee_profile_page()
    elif page == "Employees":
        employees_page()
    elif page == "Logs":
        logs_page()

    render_to_top_button()
    trigger_auto_scroll_to_content()

    if st.session_state.get("scroll_target_note"):
        st.session_state.pop("scroll_target_note", None)

if __name__ == "__main__":
    main()


