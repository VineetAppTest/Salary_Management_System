# Bulk Leave Upload Guide

This feature is for one-time bulk upload of leave/status data.

## Page

Admin Navigation → Bulk Leave Upload

## Required CSV columns

- Date
- Emp_ID
- Leave_Type
- Status
- Remarks

## Allowed Leave_Type values

- Leave - Full Day
- Leave - Half Day
- Leave - Uninformed
- Leave - Collaborative

## Duplicate rule

If same Date + Emp_ID already exists, Admin can choose:
- Skip duplicates
- Replace duplicates

## Status

Status is stored for review. Recommended values:
- Approved
- Pending
- Rejected
- Migrated

Only uploaded rows that pass validation are saved.
