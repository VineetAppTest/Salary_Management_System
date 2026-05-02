-- Salary Management System Supabase schema
-- Run this ONCE in Supabase SQL Editor before enabling DATABASE_URL in Streamlit.
-- It creates SMS tables without the app needing to create schema at runtime.

CREATE TABLE IF NOT EXISTS public."sms_users" (
    "email" TEXT,
    "name" TEXT,
    "role" TEXT,
    "password_hash" TEXT,
    "active" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_employees" (
    "Emp_ID" TEXT,
    "Name" TEXT,
    "Level" TEXT,
    "Monthly_Salary" TEXT,
    "Extra_Paid_Leaves" TEXT,
    "Status" TEXT,
    "Supervisor_Email" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_leave_entries" (
    "Date" TEXT,
    "Emp_ID" TEXT,
    "Leave_Type" TEXT,
    "Remarks" TEXT,
    "Supervisor" TEXT,
    "Timestamp" TEXT,
    "Status" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_employee_holidays" (
    "Holiday_ID" TEXT,
    "Date" TEXT,
    "Emp_ID" TEXT,
    "Festival_Name" TEXT,
    "Remarks" TEXT,
    "Created_By" TEXT,
    "Timestamp" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_advance_cases" (
    "Advance_ID" TEXT,
    "Emp_ID" TEXT,
    "Advance_Date" TEXT,
    "Amount_Given" TEXT,
    "Refund_Start_Month" TEXT,
    "First_Month_Deduction" TEXT,
    "Remaining_Months" TEXT,
    "Status" TEXT,
    "Remarks" TEXT,
    "Created_By" TEXT,
    "Timestamp" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_advance_schedule" (
    "Advance_ID" TEXT,
    "Emp_ID" TEXT,
    "Deduction_Month" TEXT,
    "Scheduled_Deduction" TEXT,
    "Admin_Updated_Deduction" TEXT,
    "Final_Deduction" TEXT,
    "Status" TEXT,
    "Updated_By" TEXT,
    "Updated_At" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_payroll_items" (
    "Month" TEXT,
    "Emp_ID" TEXT,
    "Name" TEXT,
    "Level" TEXT,
    "Monthly_Salary" TEXT,
    "Total_Days" TEXT,
    "Daily_Wage" TEXT,
    "Leave_Units" TEXT,
    "Holiday_Exclusions" TEXT,
    "Extra_Paid_Leaves" TEXT,
    "Paid_Leave_Allowed" TEXT,
    "Paid_Leave_Used" TEXT,
    "Leaves_After_Allowed_And_Exclusions" TEXT,
    "LOP_Days" TEXT,
    "Leave_Deduction_Cost" TEXT,
    "Present_Days" TEXT,
    "Unused_Leaves" TEXT,
    "Encashment" TEXT,
    "Uninformed_Count" TEXT,
    "Collaborative_Count" TEXT,
    "Special_Deductions" TEXT,
    "Special_Deductions_Applied" TEXT,
    "Advance_Prior_Month" TEXT,
    "Advance_Given_This_Month" TEXT,
    "Advance_Deduction" TEXT,
    "Advance_Balance_Open" TEXT,
    "Advance_Balance_Close" TEXT,
    "Final_Salary_Without_Special" TEXT,
    "Final_Salary_With_Special" TEXT,
    "Admin_Override_Extra_Leaves" TEXT,
    "Admin_Override_Special_Deduction" TEXT,
    "Admin_Override_Advance_Deduction" TEXT,
    "Payroll_Status" TEXT,
    "Approved_By" TEXT,
    "Approved_At" TEXT,
    "Locked" TEXT,
    "Last_Recalculated_By" TEXT,
    "Last_Recalculated_At" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_leave_adjustment_log" (
    "Month" TEXT,
    "Date" TEXT,
    "Emp_ID" TEXT,
    "Original_Leave_Type" TEXT,
    "Leave_Units" TEXT,
    "Paid_Leave_Before" TEXT,
    "Paid_Leave_Used" TEXT,
    "LOP_Created" TEXT,
    "Special_Deduction" TEXT,
    "Remarks" TEXT,
    "Supervisor" TEXT,
    "Timestamp" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_cleansing_log" (
    "Timestamp" TEXT,
    "Area" TEXT,
    "Issue" TEXT,
    "Action" TEXT,
    "Record_Key" TEXT
);

CREATE TABLE IF NOT EXISTS public."sms_audit_log" (
    "Timestamp" TEXT,
    "User" TEXT,
    "Action" TEXT,
    "Details" TEXT
);
