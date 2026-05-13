-- WageWise V116.1 backend actions
-- Purpose:
-- 1) Create missing advance master records from advance schedules for Apr-2026 onwards.
-- 2) Mark employee-specific holidays for E_Vivek from 2026-05-01 to 2026-05-12 with remark "started on 13th May".
-- Safe/idempotent: only inserts missing rows. It does not delete or overwrite existing data.

BEGIN;

WITH schedule_base AS (
    SELECT
        s."Advance_ID",
        s."Emp_ID",
        s."Deduction_Month",
        COALESCE(
            NULLIF(s."Final_Deduction", '')::numeric,
            NULLIF(s."Admin_Updated_Deduction", '')::numeric,
            NULLIF(s."Scheduled_Deduction", '')::numeric,
            0
        ) AS deduction_amount,
        to_date('01-' || s."Deduction_Month", 'DD-Mon-YYYY') AS deduction_date
    FROM "sms_advance_schedule" s
    WHERE COALESCE(s."Advance_ID", '') <> ''
      AND COALESCE(s."Emp_ID", '') <> ''
      AND COALESCE(s."Deduction_Month", '') <> ''
), schedule_from_april AS (
    SELECT *
    FROM schedule_base
    WHERE deduction_date >= DATE '2026-04-01'
), grouped AS (
    SELECT
        "Advance_ID",
        MIN("Emp_ID") AS "Emp_ID",
        MIN(deduction_date) AS first_deduction_date,
        SUM(deduction_amount) AS total_amount,
        COUNT(DISTINCT "Deduction_Month") AS month_count
    FROM schedule_from_april
    GROUP BY "Advance_ID"
), first_month AS (
    SELECT
        g."Advance_ID",
        g."Emp_ID",
        g.first_deduction_date,
        to_char(g.first_deduction_date, 'Mon-YYYY') AS first_month_label,
        g.total_amount,
        GREATEST(g.month_count - 1, 0) AS remaining_months,
        SUM(s.deduction_amount) AS first_month_deduction
    FROM grouped g
    JOIN schedule_from_april s
      ON s."Advance_ID" = g."Advance_ID"
     AND s.deduction_date = g.first_deduction_date
    GROUP BY g."Advance_ID", g."Emp_ID", g.first_deduction_date, g.total_amount, g.month_count
)
INSERT INTO "sms_advance_cases" (
    "Advance_ID", "Emp_ID", "Advance_Date", "Amount_Given", "Refund_Start_Month",
    "First_Month_Deduction", "Remaining_Months", "Status", "Remarks", "Created_By", "Timestamp"
)
SELECT
    f."Advance_ID",
    f."Emp_ID",
    f.first_deduction_date::text,
    f.total_amount::text,
    f.first_month_label,
    f.first_month_deduction::text,
    f.remaining_months::text,
    'Open',
    'V116.1 backend reconciliation: advance case created from advance schedule.',
    'backend@wagewise.local',
    now()::text
FROM first_month f
WHERE f.total_amount > 0
  AND NOT EXISTS (
      SELECT 1 FROM "sms_advance_cases" c
      WHERE c."Advance_ID" = f."Advance_ID"
  );

INSERT INTO "sms_employee_holidays" (
    "Holiday_ID", "Date", "Emp_ID", "Festival_Name", "Remarks", "Created_By", "Timestamp"
)
SELECT
    'HOL-E-VIVEK-' || to_char(d::date, 'YYYYMMDD'),
    d::date::text,
    'E_Vivek',
    'Employee-specific holiday',
    'started on 13th May',
    'backend@wagewise.local',
    now()::text
FROM generate_series(DATE '2026-05-01', DATE '2026-05-12', INTERVAL '1 day') AS d
WHERE NOT EXISTS (
    SELECT 1 FROM "sms_employee_holidays" h
    WHERE h."Date" = d::date::text
      AND h."Emp_ID" = 'E_Vivek'
);

INSERT INTO "sms_audit_log" ("Timestamp", "User", "Action", "Details")
VALUES (
    now()::text,
    'backend@wagewise.local',
    'V116_1_BACKEND_ACTIONS_SQL',
    'Created missing advance cases from schedules for Apr-2026 onwards and added E_Vivek holiday exclusions from 2026-05-01 to 2026-05-12.'
);

COMMIT;
