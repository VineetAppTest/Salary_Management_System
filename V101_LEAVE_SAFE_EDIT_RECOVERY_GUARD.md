# WageWise V101 Leave Safe Edit + Recovery Guard

Built on V100.

Critical safety fix:
- Leave correction now follows enterprise-safe pattern.
- Physical delete is removed from the Admin leave correction flow.
- Admin can edit selected leave row safely.
- Admin can cancel selected leave row safely by setting Status = Cancelled.
- Cancelled leave rows remain in the table for audit and are ignored by payroll.
- Backup of leave_entries is created before every admin edit/cancel.
- Mandatory admin correction remark remains.
- Audit log captures the correction and backup path.

Retained from V100:
- Advance safe edit/recovery guard.
- Advance cancellation instead of physical delete.
- V98 advance calculation guardrails.
- V96 OIDC-ready capability.

No salary/leave calculation rule changes.
