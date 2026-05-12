-- WageWise V92 Users Direct Save Repair
-- Run in Supabase SQL Editor if Users & Access save verification fails.

ALTER TABLE public."sms_users"
ADD COLUMN IF NOT EXISTS "allow_admin" TEXT DEFAULT 'True';

ALTER TABLE public."sms_users"
ADD COLUMN IF NOT EXISTS "allow_supervisor" TEXT DEFAULT 'True';

UPDATE public."sms_users"
SET "allow_admin" = 'True'
WHERE "allow_admin" IS NULL OR "allow_admin" = '';

UPDATE public."sms_users"
SET "allow_supervisor" = 'True'
WHERE "allow_supervisor" IS NULL OR "allow_supervisor" = '';

-- Optional check:
SELECT "email", "name", "role", "active", "allow_admin", "allow_supervisor"
FROM public."sms_users"
ORDER BY "email";
