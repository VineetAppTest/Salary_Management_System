import calendar
import hashlib
import os
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from io import BytesIO
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy import text

def test_database_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user;"))
            row = result.fetchone()

        st.success("Supabase database connected successfully.")
        st.write({
            "database": row[0],
            "user": row[1],
        })
        return True

    except Exception as e:
        st.error("Database connection failed.")
        st.exception(e)
        return False

from urllib.parse import urlparse
import streamlit as st

from sqlalchemy import text

def test_database_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user;"))
            row = result.fetchone()

        st.success("✅ Supabase connected successfully.")
        st.write({
            "database": row[0],
            "user": row[1],
        })
        return True

    except Exception as e:
        st.error("❌ Supabase connection failed.")
        st.exception(e)
        return False

db_ok = test_database_connection()


def show_db_debug():
    try:
        raw_url = str(st.secrets.get("DATABASE_URL", "")).replace("\x00", "").strip()
        parsed = urlparse(raw_url)

        st.info("Database debug details")

        st.write({
            "scheme": parsed.scheme,
            "username": parsed.username,
            "host": parsed.hostname,
            "port": parsed.port,
            "database": parsed.path.replace("/", ""),
            "has_password": bool(parsed.password),
            "contains_null_character": "\x00" in raw_url,
        })

    except Exception as e:
        st.error(f"Could not parse DATABASE_URL safely: {e}")

show_db_debug()

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

REQUIRED_FILES = {
    "users": ["email", "name", "role", "password_hash", "active"],
    "employees": ["Emp_ID", "Name", "Level", "Monthly_Salary", "Extra_Paid_Leaves", "Status", "Supervisor_Email"],
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
    users = pd.read_csv(users_path) if users_path.exists() else pd.DataFrame(columns=REQUIRED_FILES["users"])
    if users.empty:
        users = pd.DataFrame([
            {"email": "demo@sms.local", "name": "Demo User", "role": "All Access", "password_hash": hash_password("demo123"), "active": True},
        ])
        users.to_csv(users_path, index=False)

    employees_path = file_path("employees")
    employees = pd.read_csv(employees_path) if employees_path.exists() else pd.DataFrame(columns=REQUIRED_FILES["employees"])
    if employees.empty:
        employees = pd.DataFrame([
            {"Emp_ID": "E_Gudiya", "Name": "Gudiya", "Level": "L1", "Monthly_Salary": 9200, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
            {"Emp_ID": "E_Asha", "Name": "Asha", "Level": "L1", "Monthly_Salary": 10000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
            {"Emp_ID": "E_Pooja", "Name": "Pooja", "Level": "L1", "Monthly_Salary": 8000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
            {"Emp_ID": "E_Kiran", "Name": "Kiran", "Level": "L1", "Monthly_Salary": 8000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
            {"Emp_ID": "E_Riya", "Name": "Riya", "Level": "L1", "Monthly_Salary": 4500, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
            {"Emp_ID": "E_Sunita", "Name": "Sunita", "Level": "L1", "Monthly_Salary": 8000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
            {"Emp_ID": "E_Faizan", "Name": "Faizan", "Level": "L2", "Monthly_Salary": 16000, "Extra_Paid_Leaves": 0, "Status": "Active", "Supervisor_Email": "supervisor@sms.local"},
        ])
        employees.to_csv(employees_path, index=False)

def read_table_csv(name):
    ensure_data_files_csv_only()
    path = file_path(name)
    try:
        df = pd.read_csv(path)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        df = pd.DataFrame(columns=REQUIRED_FILES.get(name, []))
    return normalize_required_columns(name, df)

def write_table_csv(name, df):
    df = normalize_required_columns(name, df)
    df.to_csv(file_path(name), index=False)

def ensure_database_tables():
    engine = get_db_engine()
    if engine is None:
        ensure_data_files_csv_only()
        return
    ensure_data_files_csv_only()
    try:
        with engine.begin() as conn:
            for name, columns in REQUIRED_FILES.items():
                table = db_table_name(name)
                col_sql = ", ".join([f'"{c}" TEXT' for c in columns])
                conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{table}" ({col_sql})'))
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                if int(count or 0) == 0:
                    seed_df = read_table_csv(name)
                    if not seed_df.empty:
                        seed_df = normalize_required_columns(name, seed_df)
                        seed_df.to_sql(table, engine, if_exists="append", index=False)
    except Exception as e:
        st.warning(f"Database connection issue. Falling back to local CSV for this session. Details: {e}")

def read_table_db(name):
    engine = get_db_engine()
    if engine is None:
        return read_table_csv(name)
    try:
        ensure_database_tables()
        df = pd.read_sql_table(db_table_name(name), engine)
        return normalize_required_columns(name, df)
    except Exception as e:
        st.warning(f"Could not read {name} from Supabase. Using CSV fallback. Details: {e}")
        return read_table_csv(name)

def write_table_db(name, df):
    engine = get_db_engine()
    if engine is None:
        write_table_csv(name, df)
        return
    try:
        ensure_database_tables()
        df = normalize_required_columns(name, df)
        df.to_sql(db_table_name(name), engine, if_exists="replace", index=False)
    except Exception as e:
        st.error(f"Could not write {name} to Supabase. Data was saved to local CSV fallback only. Details: {e}")
        write_table_csv(name, df)


def file_path(name):
    return DATA_DIR / f"{name}.csv"

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def ensure_data_files():
    if db_enabled():
        ensure_database_tables()
    else:
        ensure_data_files_csv_only()

def read_table(name):
    if db_enabled():
        return read_table_db(name)
    return read_table_csv(name)

def write_table(name, df):
    if db_enabled():
        write_table_db(name, df)
    else:
        write_table_csv(name, df)

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
    """Display persistent confirmation after button actions."""
    msg = st.session_state.pop("confirmation_message", None)
    celebrate = st.session_state.pop("celebrate_success", False)
    if msg:
        st.success(msg)
        if celebrate:
            st.balloons()
            try:
                st.toast("Action completed successfully.", icon="✅")
            except Exception:
                pass

def set_confirmation(message, celebrate=False):
    st.session_state.confirmation_message = message
    if celebrate:
        st.session_state.celebrate_success = True

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
        level = str(emp.get("Level", "L1"))
        monthly_salary = safe_float(emp.get("Monthly_Salary", 0))
        days_in_month = calendar.monthrange(yr, mon)[1]
        daily_wage = monthly_salary / days_in_month if days_in_month else 0
        allowed = 2 if level == "L1" else 4
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


def build_mobile_salary_summary(month_value):
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
        advances["Advance_Date_dt"] = parse_app_date_series(advances["Advance_Date"])

    rows = []
    for _, p in month_df.iterrows():
        emp_id = str(p["Emp_ID"])
        name = p.get("Name", "")
        level = str(p.get("Level", "L1"))
        total_pay = safe_float(p.get("Monthly_Salary", 0))
        daily_wage = safe_float(p.get("Daily_Wage", 0))

        emp_adv = advances[advances["Emp_ID"].astype(str) == emp_id].copy() if (not advances.empty and "Emp_ID" in advances.columns) else pd.DataFrame(columns=REQUIRED_FILES["advance_cases"])
        emp_sched = schedule[schedule["Emp_ID"].astype(str) == emp_id].copy() if (not schedule.empty and "Emp_ID" in schedule.columns) else pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])

        current_month_adv_ids = set()
        prior_month_adv_ids = set()
        total_adv_ids = set()

        if not emp_adv.empty:
            prior_cases = emp_adv[emp_adv["Advance_Date_dt"] < month_start]
            current_cases = emp_adv[(emp_adv["Advance_Date_dt"] >= month_start) & (emp_adv["Advance_Date_dt"] <= month_end)]
            prior_month_adv_ids = set(prior_cases["Advance_ID"].astype(str))
            current_month_adv_ids = set(current_cases["Advance_ID"].astype(str))
            total_adv_ids = set(emp_adv["Advance_ID"].astype(str))
        else:
            prior_cases = pd.DataFrame()
            current_cases = pd.DataFrame()

        # Operational summary rule:
        # - Prior Month Advance = current-month deduction lines for advance IDs created before this month.
        # - Current Month Advance = current-month deduction lines for advance IDs created in this month.
        # This matches the business expectation where Pooja can show 2k prior + 2k current = 4k total.
        advance_prior_month = 0.0
        advance_current_month = 0.0
        deduction_for_month = 0.0
        total_deducted_upto_current = 0.0
        total_advance_given_until_month = 0.0

        if not emp_adv.empty:
            total_advance_given_until_month = safe_numeric_series(emp_adv["Amount_Given"]).sum() if "Amount_Given" in emp_adv.columns else 0

        if not emp_sched.empty:
            for _, srow in emp_sched.iterrows():
                try:
                    sy, sm = parse_month_label(str(srow["Deduction_Month"]))
                except Exception:
                    continue

                adv_id = str(srow.get("Advance_ID", ""))
                amt = safe_float(srow.get("Final_Deduction", 0))

                if (sy, sm) == (yr, mon):
                    deduction_for_month += amt
                    if adv_id in current_month_adv_ids:
                        advance_current_month += amt
                    else:
                        # If schedule exists but case date is missing/old/unknown, treat as prior month bucket.
                        advance_prior_month += amt

                if (sy, sm) <= (yr, mon):
                    total_deducted_upto_current += amt

        # Fallbacks from payroll row if schedule/case split is absent.
        if advance_prior_month == 0:
            advance_prior_month = safe_float(p.get("Advance_Prior_Month", 0))
        if advance_current_month == 0:
            advance_current_month = safe_float(p.get("Advance_Given_This_Month", 0))

        # If deduction exists in payroll but not in schedule, keep payroll deduction.
        if deduction_for_month == 0:
            deduction_for_month = safe_float(p.get("Advance_Deduction", 0))

        total_advance = advance_prior_month + advance_current_month
        advance_left = safe_float(p.get("Advance_Balance_Close", 0))
        if advance_left == 0 and total_advance_given_until_month > 0:
            advance_left = max(0.0, total_advance_given_until_month - total_deducted_upto_current)

        leaves_taken = safe_float(p.get("Leave_Units", 0))
        base_leave_allowed = 2 if level == "L1" else 4
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
            "Leaves Taken": leaves_taken,
            "Deduction for the Month": round(deduction_for_month, 2),
            "Leave Deduction Cost": leave_deduction_cost,
            "Net Salary to be Paid": round(net_salary, 2),
            "Advance Left": round(advance_left, 2),
        })

    return pd.DataFrame(rows)
def add_audit(user, action, details):
    df = read_table("audit_log")
    df.loc[len(df)] = [datetime.now().isoformat(timespec="seconds"), user, action, details]
    write_table("audit_log", df)

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

    </style>
    """, unsafe_allow_html=True)

def authenticate(email, password):
    users = read_table("users")
    match = users[
        (users["email"].astype(str).str.lower() == email.lower()) &
        (users["password_hash"] == hash_password(password)) &
        (users["active"].astype(str).str.lower().isin(["true", "1", "yes"]))
    ]
    if match.empty:
        return None
    return match.iloc[0].to_dict()

def login_screen():
    st.markdown("""
    <div class='login-shell'>
        <div class='login-logo'>₹</div>
        <div class='login-title'>Salary Management System</div>
        <div class='login-subtitle'>One secure login. Choose Admin or Supervisor access after login.</div>
    </div>
    """, unsafe_allow_html=True)

    left, center, right = st.columns([0.8, 2.4, 0.8])
    with center:
        with st.form("single_login_form"):
            email = st.text_input("Email", value="demo@sms.local")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login securely", use_container_width=True)

    if submitted:
        user = authenticate(email, password)
        if user:
            st.session_state.auth_user = user
            st.session_state.user = None
            st.session_state.access_role = None
            st.session_state.page = "Role Selection"
            add_audit(email, "SINGLE_LOGIN", "Successful login")
            st.rerun()
        else:
            st.error("Invalid credentials or inactive user.")

def role_selection_page():
    auth_user = st.session_state.get("auth_user")
    if not auth_user:
        st.session_state.clear()
        st.rerun()

    st.markdown("""
    <div class='login-shell'>
        <div class='login-logo'>✓</div>
        <div class='login-title'>Choose Role</div>
        <div class='login-subtitle'>One login gives access to Admin, Supervisor, and Tech areas.</div>
    </div>
    """, unsafe_allow_html=True)

    roles = [
        ("Admin", "Admin", "Payroll operations: employees, leave, holidays, advances, payroll review and approval."),
        ("Supervisor", "Supervisor", "Simple daily flow with only two actions: Mark Leave and Add Advance."),
        ("Tech", "Tech", "Technical utilities: bulk upload, advance master edit, schedule edit and password reset."),
    ]

    cols = st.columns(3)
    for col, (role_key, title, desc) in zip(cols, roles):
        with col:
            st.markdown(f"""
            <div class='role-card'>
                <div class='role-title'>{title}</div>
                <div class='role-help'>{desc}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Open {title}", use_container_width=True):
                st.session_state.user = {
                    "email": auth_user["email"] if role_key != "Supervisor" else "supervisor@sms.local",
                    "name": auth_user.get("name", "Demo User") if role_key != "Supervisor" else "Supervisor",
                    "role": role_key,
                    "active": True,
                }
                st.session_state.access_role = role_key
                st.session_state.page = "Tech" if role_key == "Tech" else "Dashboard"
                add_audit(auth_user["email"], "ROLE_SELECTED", f"{role_key} role selected")
                st.rerun()

    st.divider()
    if st.button("Logout", use_container_width=True):
        add_audit(auth_user["email"], "LOGOUT_FROM_ROLE_SELECTION", "Logged out before choosing role")
        st.session_state.clear()
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
        employees = employees[employees["Supervisor_Email"].astype(str).str.lower() == st.session_state.user["email"].lower()]
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
        if row.get("Level") not in ["L1", "L2"]:
            employees.at[idx, "Level"] = "L1"
            add_clean_log("Employees", "Invalid Level", "Defaulted to L1", str(row.get("Emp_ID")))
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
    level = str(emp["Level"])
    monthly_salary = float(emp["Monthly_Salary"])
    daily_wage = monthly_salary / total_days
    base_extra = float(emp.get("Extra_Paid_Leaves", 0) or 0)
    extra = base_extra if extra_leave_override is None else float(extra_leave_override)

    emp_holidays = employee_holidays[employee_holidays["Emp_ID"].astype(str) == emp_id].copy() if not employee_holidays.empty else employee_holidays.copy()
    if not emp_holidays.empty:
        emp_holidays["Date_dt"] = parse_app_date_series(emp_holidays["Date"])
        emp_holidays = emp_holidays[(emp_holidays["Date_dt"] >= month_start) & (emp_holidays["Date_dt"] <= month_end)]
    holiday_exclusions = float(len(emp_holidays))

    paid_leave_allowed = (2 if level == "L1" else 4) + extra + holiday_exclusions

    if leave_entries.empty:
        emp_leaves = pd.DataFrame(columns=list(leave_entries.columns) + ["Date_dt"])
    else:
        valid_emp_ids = {emp_id, normalize_emp_id_value(emp_id), normalize_emp_id_value(emp.get("Name", ""))}
        emp_leaves = leave_entries[leave_entries["Emp_ID"].astype(str).apply(lambda x: normalize_emp_id_value(x) in valid_emp_ids)].copy()
        if not emp_leaves.empty:
            emp_leaves["Date_dt"] = parse_app_date_series(emp_leaves["Date"])
            emp_leaves = emp_leaves[(emp_leaves["Date_dt"] >= month_start) & (emp_leaves["Date_dt"] <= month_end)]

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

    for _, leave in emp_leaves.sort_values("Date_dt").iterrows():
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
    present_days = total_days - lop_days
    unused_leaves = max(0, paid_leave_allowed - paid_leave_used)
    encashment = unused_leaves * daily_wage

    uninformed_special_amount, collaborative_special_amount, default_special_deduction, final_impact_cfg = calculate_special_impact(
        uninformed_count, collaborative_count, impact_cfg
    )
    special_applied = default_special_deduction if special_override is None else float(special_override)

    if schedule.empty:
        emp_schedule = pd.DataFrame(columns=REQUIRED_FILES["advance_schedule"])
    else:
        emp_schedule = schedule[
            (schedule["Emp_ID"].astype(str) == emp_id) &
            (schedule["Deduction_Month"].astype(str) == current_month) &
            (schedule["Status"].astype(str).str.lower() == "open")
        ].copy()
    default_advance = pd.to_numeric(emp_schedule["Final_Deduction"], errors="coerce").fillna(0).sum() if not emp_schedule.empty else 0
    advance_deduction = default_advance if advance_override is None else safe_float(advance_override)

    if not advance_cases.empty:
        advance_cases["Advance_Date_dt"] = pd.to_datetime(advance_cases["Advance_Date"], errors="coerce", dayfirst=True)
        emp_cases_all = advance_cases[advance_cases["Emp_ID"].astype(str) == emp_id].copy()
        emp_cases_month = emp_cases_all[(emp_cases_all["Advance_Date_dt"] >= month_start) & (emp_cases_all["Advance_Date_dt"] <= month_end)] if not emp_cases_all.empty else emp_cases_all.head(0)
        emp_cases_prior = emp_cases_all[emp_cases_all["Advance_Date_dt"] < month_start] if not emp_cases_all.empty else emp_cases_all.head(0)
        advance_given_this_month = pd.to_numeric(emp_cases_month["Amount_Given"], errors="coerce").fillna(0).sum() if not emp_cases_month.empty else 0
        prior_advance_given = pd.to_numeric(emp_cases_prior["Amount_Given"], errors="coerce").fillna(0).sum() if not emp_cases_prior.empty else 0
        total_advance_given_until_month = prior_advance_given + advance_given_this_month
        prior_advance_ids = set(emp_cases_prior["Advance_ID"].astype(str)) if not emp_cases_prior.empty else set()
    else:
        advance_given_this_month = 0
        prior_advance_given = 0
        total_advance_given_until_month = 0
        prior_advance_ids = set()

    if not schedule.empty:
        schedule_emp = schedule[schedule["Emp_ID"].astype(str) == emp_id].copy()

        def sched_month_tuple(row):
            try:
                sy, sm = parse_month_label(str(row["Deduction_Month"]))
                return (sy, sm)
            except Exception:
                return None

        current_month_deductions = 0.0
        prior_deducted_upto_current = 0.0
        total_deducted_upto_current = 0.0
        for _, srow in schedule_emp.iterrows():
            mt = sched_month_tuple(srow)
            if mt is None:
                continue
            amt = float(pd.to_numeric(srow.get("Final_Deduction", 0), errors="coerce") or 0)
            if mt == (year, month):
                current_month_deductions += amt
            if mt <= (year, month):
                total_deducted_upto_current += amt
                if str(srow.get("Advance_ID", "")) in prior_advance_ids:
                    prior_deducted_upto_current += amt
    else:
        current_month_deductions = advance_deduction
        prior_deducted_upto_current = 0
        total_deducted_upto_current = advance_deduction

    # Advance Prior Month = carry forward from prior advances after current month scheduled deductions.
    advance_prior_month = max(0, prior_advance_given - prior_deducted_upto_current)
    advance_balance_open = advance_prior_month
    advance_balance_close = max(0, total_advance_given_until_month - total_deducted_upto_current)

    final_without_special = (present_days * daily_wage) + encashment - advance_deduction
    final_with_special = final_without_special - special_applied

    item = {
        "Month": current_month,
        "Emp_ID": emp_id,
        "Name": emp["Name"],
        "Level": level,
        "Monthly_Salary": monthly_salary,
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
        if emp_id not in existing_emp_ids:
            item, _ = calculate_employee_payroll(emp, yr, mon)
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
        item, leave_logs = calculate_employee_payroll(emp, year, month, special_config=special_config)
        rows.append(item)
        logs.extend(leave_logs)
    payroll_df = pd.DataFrame(rows)
    payroll_df = reconcile_payroll_month(month_label(year, month), payroll_df)
    return payroll_df, pd.DataFrame(logs)

def page_navigation():
    user = st.session_state.user
    auth_user = st.session_state.get("auth_user", user)
    st.markdown(
        f"<div class='top-nav'><b>Logged in:</b> {auth_user.get('name', user['name'])} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Current Role:</b> {user['role']}</div>",
        unsafe_allow_html=True
    )

    if user["role"] == "Supervisor":
        pages = ["Dashboard"]
    elif user["role"] == "Admin":
        pages = ["Dashboard", "Salary Summary", "Leave", "Holiday", "Advance", "Payroll", "Payroll Approval", "Employee Profile", "Employees", "Logs"]
    else:
        pages = ["Tech", "Bulk Leave Upload", "System Health"]

    if "page" not in st.session_state or st.session_state.page not in pages:
        st.session_state.page = pages[0]

    if user["role"] in ["Admin", "Tech"]:
        st.markdown("<div class='nav-label'>Navigation</div>", unsafe_allow_html=True)
        st.caption("Use the buttons below to move between sections. On phone, buttons stack vertically.")
        rows = [pages[i:i+3] for i in range(0, len(pages), 3)]
        for row in rows:
            cols = st.columns(len(row))
            for col, page_name in zip(cols, row):
                active = " ✅" if st.session_state.page == page_name else ""
                if col.button(page_name + active, use_container_width=True):
                    st.session_state.page = page_name
                    st.rerun()

    c1, c2, c3 = st.columns([3, 1, 1])
    with c2:
        if st.button("Switch Role", use_container_width=True):
            st.session_state.user = None
            st.session_state.access_role = None
            st.session_state.page = "Role Selection"
            st.rerun()
    with c3:
        if st.button("Logout", use_container_width=True):
            add_audit(auth_user.get("email", user["email"]), "LOGOUT", "User logged out")
            st.session_state.clear()
            st.rerun()

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
            st.rerun()

    st.divider()
    action = st.session_state.get("quick_action", "")

    if action == "leave":
        st.markdown("### Mark Leave")
        quick_leave_form()
    elif action == "advance":
        st.markdown("### Add Advance")
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
        cases = read_table("advance_cases")
        advance_id = f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cases.loc[len(cases)] = [advance_id, emp_id, str(adv_date), amount, month_label(int(start_year), int(start_month)), first_deduction, remaining_months, "Open", remarks, st.session_state.user["email"], datetime.now().isoformat(timespec="seconds")]
        write_table("advance_cases", cases)
        create_advance_schedule(advance_id, emp_id, amount, int(start_year), int(start_month), first_deduction, remaining_months)
        add_audit(st.session_state.user["email"], "SUPERVISOR_QUICK_CREATE_ADVANCE", f"{advance_id} {emp_id} ₹{amount}")
        set_confirmation("Advance and schedule created successfully.", celebrate=True)
        st.session_state.quick_action = ""
        st.rerun()


def dashboard_page():
    if st.session_state.user["role"] == "Supervisor":
        supervisor_dashboard_page()
        return
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
        if st.session_state.get("last_bulk_upload_summary"):
            st.markdown("#### Last saved upload summary")
            st.dataframe(pd.DataFrame(st.session_state.last_bulk_upload_summary), use_container_width=True, height=min(260, 80 + len(st.session_state.last_bulk_upload_summary) * 35))

    if st.session_state.user["role"] != "Tech":
        st.warning("Open the Tech role to use bulk upload.")
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

    employees = read_table("employees")
    active_emp_ids = set(employees[employees["Status"].astype(str).str.lower() == "active"]["Emp_ID"].astype(str))
    valid_leave_types = set(LEAVE_UNITS.keys())

    clean_rows = []
    error_rows = []

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
        if is_month_locked(lock_month):
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
    st.markdown("#### Preview of all valid rows")
    same_day_dupes = clean_df[clean_df.duplicated(["Date", "Emp_ID"], keep=False)]
    if not same_day_dupes.empty:
        st.warning(f"{len(same_day_dupes)} rows have the same Date + Emp_ID. They will still be saved in replace-month mode and not collapsed.")
    st.dataframe(clean_df[["Date", "Emp_ID", "Leave_Type", "Status", "Remarks"]], use_container_width=True, height=360)

    upload_mode = st.radio(
        "Upload mode",
        ["Replace entire leave data for uploaded month", "Append / replace matching rows"],
        horizontal=False,
        index=0,
        help="For demo and one-time migration, keep 'Replace entire leave data for uploaded month'. It ensures saved rows match the uploaded file for that month."
    )
    duplicate_policy = "Replace duplicates"

    if st.button("Confirm Bulk Upload", use_container_width=True):
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
        st.success(msg)
        st.markdown("#### Saved employee summary after upload")
        st.dataframe(saved_summary, use_container_width=True, height=min(260, 80 + len(saved_summary) * 35))
        st.balloons()
        try:
            st.toast("Bulk upload completed and verified.", icon="✅")
        except Exception:
            pass


def leave_page():
    st.subheader("Leave Updation")
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
    st.dataframe(display_leaves, use_container_width=True, height=420)
    st.download_button(
        "Download All Leave Entries",
        all_leaves.to_csv(index=False).encode("utf-8"),
        file_name="all_leave_entries.csv",
        mime="text/csv",
        on_click=download_ack,
        args=("All leave entries",)
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
    st.caption("Advance entered here creates the repayment schedule. Employee Profile can later override the current month deduction and sync it back to this schedule.")
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
        cases = read_table("advance_cases")
        advance_id = f"ADV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cases.loc[len(cases)] = [advance_id, emp_id, str(adv_date), amount, month_label(int(start_year), int(start_month)), first_deduction, remaining_months, "Open", remarks, st.session_state.user["email"], datetime.now().isoformat(timespec="seconds")]
        write_table("advance_cases", cases)
        create_advance_schedule(advance_id, emp_id, amount, int(start_year), int(start_month), first_deduction, remaining_months)
        add_audit(st.session_state.user["email"], "CREATE_ADVANCE", f"{advance_id} {emp_id} ₹{amount}")
        set_confirmation("Advance and repayment schedule created.", celebrate=True)
        st.rerun()

    st.markdown("#### Advance cases")
    st.dataframe(read_table("advance_cases").tail(20), use_container_width=True)

    st.markdown("#### Repayment schedule")
    st.dataframe(read_table("advance_schedule").tail(50), use_container_width=True)


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
    total_leave_cost = summary["Leave Deduction Cost"].sum() if "Leave Deduction Cost" in summary else 0
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
        "Total Advance", "Deduction for the Month", "Leave Deduction Cost",
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

    months = payroll["Month"].dropna().astype(str).unique().tolist()
    selected_month = st.selectbox("Select month", months, index=len(months)-1)

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

    render_salary_summary_cards(summary)
    render_sticky_salary_table(summary)

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

    search = st.text_input("Search employee by name, ID, level or status", placeholder="Type Gudiya, E_Gudiya, L1, Active...")
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

    st.markdown("### Add New Employee")
    with st.form("add_employee_form"):
        name = st.text_input("Name")
        auto_emp_id = generate_emp_id_from_name(name)
        st.text_input("Auto Employee ID", value=auto_emp_id, disabled=True)
        c1, c2, c3 = st.columns(3)
        level = c1.selectbox("Level", ["L1", "L2"], key="add_level")
        salary = c2.number_input("Monthly Salary", min_value=0.0, step=500.0, key="add_salary")
        extra = c3.number_input("Default Extra Paid Leaves", min_value=0.0, step=0.5, key="add_extra")
        c4, c5 = st.columns(2)
        status = c4.selectbox("Status", ["Active", "Inactive"], key="add_status")
        supervisor = c5.text_input("Supervisor Email", value="supervisor@sms.local", key="add_supervisor")
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
        df.loc[len(df)] = [emp_id, clean_name, level, salary, extra, status, supervisor.strip()]
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
        edit_level = c2.selectbox("Level", ["L1", "L2"], index=0 if row["Level"] == "L1" else 1, key="edit_level")
        edit_status = c3.selectbox("Status", ["Active", "Inactive"], index=0 if str(row["Status"]) == "Active" else 1, key="edit_status")
        c4, c5 = st.columns(2)
        edit_salary = c4.number_input("Monthly Salary", min_value=0.0, step=500.0, value=float(row["Monthly_Salary"]))
        edit_extra = c5.number_input("Default Extra Paid Leaves", min_value=0.0, step=0.5, value=float(row["Extra_Paid_Leaves"]))
        edit_supervisor = st.text_input("Supervisor Email", value=str(row["Supervisor_Email"]))
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
        df.loc[mask, "Extra_Paid_Leaves"] = edit_extra
        df.loc[mask, "Status"] = edit_status
        df.loc[mask, "Supervisor_Email"] = edit_supervisor.strip()
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

def tech_page():
    st.subheader("Tech Utilities")
    st.info(f"Storage mode: {'Supabase PostgreSQL persistent database' if db_enabled() else 'Local CSV fallback. Add DATABASE_URL in Streamlit secrets to enable Supabase.'}")
    if st.session_state.user["role"] != "Tech":
        st.warning("Open the Tech role to access this page.")
        return

    tab1, tab2, tab3 = st.tabs(["Unified Advance Editor", "Users & Password", "System Notes"])

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

    with tab1:
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
                        write_table("advance_cases", cases)

                        rebuilt = build_case_schedule_from_inputs(selected_case, emp_id_locked, amount, start_month, first_deduction, remaining_months, status)
                        schedule = schedule[schedule["Advance_ID"].astype(str) != selected_case].copy()
                        if not rebuilt.empty:
                            schedule = pd.concat([schedule, rebuilt], ignore_index=True)
                        write_table("advance_schedule", schedule)

                        add_audit(st.session_state.user["email"], "TECH_SAVE_UNIFIED_ADVANCE", selected_case)
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
                    write_table("advance_cases", cases)
                    new_sched = build_case_schedule_from_inputs(new_id, emp_id_new, amount_new, start_month_new, first_new, remaining_new, "Open")
                    if not new_sched.empty:
                        schedule = pd.concat([schedule, new_sched], ignore_index=True)
                    write_table("advance_schedule", schedule)
                    add_audit(st.session_state.user["email"], "TECH_CREATE_UNIFIED_ADVANCE", new_id)
                    set_confirmation(f"New unified advance created and reconciled: {new_id}.", celebrate=True)
                    st.rerun()
            except Exception as e:
                st.error(f"Could not create advance: {e}")

    with tab2:
        st.markdown("### User / Member Manager")
        st.caption("Create users, edit login email IDs, reset passwords, activate/deactivate users, or delete users.")

        users = read_table("users")
        if "active" not in users.columns:
            users["active"] = True

        display_users = users.copy()
        display_users["password_hash"] = "••••••••"
        st.dataframe(display_users[["email", "name", "role", "active", "password_hash"]], use_container_width=True)

        st.markdown("#### Create New Login")
        with st.form("create_user_form"):
            c1, c2 = st.columns(2)
            new_email = c1.text_input("Login Email ID")
            new_name = c2.text_input("Display Name")
            c3, c4 = st.columns(2)
            new_role = c3.selectbox("Role", ["All Access", "Admin", "Supervisor", "Tech"], index=0)
            new_active = c4.selectbox("Status", ["Active", "Inactive"], index=0)
            c5, c6 = st.columns(2)
            new_password = c5.text_input("Password", type="password")
            new_confirm = c6.text_input("Confirm Password", type="password")
            create_user = st.form_submit_button("Create Login")

        if create_user:
            clean_email = new_email.strip().lower()
            clean_name = new_name.strip() or clean_email
            if not clean_email:
                st.error("Login Email ID is required.")
            elif clean_email in users["email"].astype(str).str.lower().tolist():
                st.error("This login email already exists.")
            elif not new_password or len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_password != new_confirm:
                st.error("Passwords do not match.")
            else:
                users.loc[len(users)] = [clean_email, clean_name, new_role, hash_password(new_password), True if new_active == "Active" else False]
                write_table("users", users)
                add_audit(st.session_state.user["email"], "CREATE_USER", clean_email)
                set_confirmation(f"Login created for {clean_email}.", celebrate=True)
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
                role_options = ["All Access", "Admin", "Supervisor", "Tech"]
                current_role = str(row["role"]) if str(row["role"]) in role_options else "All Access"
                edited_role = st.selectbox("Role", role_options, index=role_options.index(current_role))
                current_active = str(row["active"]).lower() in ["true", "1", "yes", "active"]
                edited_active = st.selectbox("Status", ["Active", "Inactive"], index=0 if current_active else 1)
                edited_password = st.text_input("New Password (leave blank to keep old)", type="password")
                edited_confirm = st.text_input("Confirm New Password", type="password")
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
                    if edited_password:
                        users.loc[mask, "password_hash"] = hash_password(edited_password)
                    write_table("users", users)
                    add_audit(st.session_state.user["email"], "EDIT_USER", f"{old_email} -> {clean_email}")
                    set_confirmation(f"Login updated for {clean_email}.", celebrate=True)
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
                    write_table("users", users)
                    add_audit(st.session_state.user["email"], "DELETE_USER", selected_email)
                    set_confirmation(f"Login deleted: {selected_email}.", celebrate=True)
                    st.rerun()

    with tab3:
        st.markdown("### Utility definitions")
        st.info("Advance ID is the single control point. Employee is locked after advance creation to protect data integrity.")
        st.info("Unified Advance Editor writes both advance_cases and advance_schedule together.")
        st.info("Amount controls use ₹100 increments.")



def system_health_page():
    st.subheader("System Health Check")
    st.caption(f"Database Mode: {'Supabase PostgreSQL' if db_enabled() else 'Local CSV fallback'}")
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

def main():
    st.set_page_config(page_title="Salary Management System", page_icon="💼", layout="wide")
    ensure_data_files()
    apply_theme()

    if "auth_user" not in st.session_state:
        login_screen()
        return

    if not st.session_state.get("user"):
        role_selection_page()
        return

    st.markdown("<div class='sms-title'>Salary Management System</div>", unsafe_allow_html=True)
    st.markdown("<div class='sms-subtitle'>Mobile-first leave, advance schedule, deduction review and payroll calculation</div>", unsafe_allow_html=True)
    show_confirmation_area()
    page = page_navigation()
    if page == "Dashboard":
        dashboard_page()
    elif page == "Salary Summary":
        salary_summary_page()
    elif page == "Leave":
        leave_page()
    elif page == "Tech":
        tech_page()
    elif page == "Bulk Leave Upload":
        bulk_leave_upload_page()
    elif page == "System Health":
        system_health_page()
    elif page == "Holiday":
        holiday_page()
    elif page == "Advance":
        advance_page()
    elif page == "Payroll":
        payroll_page()
    elif page == "Payroll Approval":
        payroll_approval_page()
    elif page == "Employee Profile":
        employee_profile_page()
    elif page == "Employees":
        employees_page()
    elif page == "Logs":
        logs_page()

if __name__ == "__main__":
    main()


