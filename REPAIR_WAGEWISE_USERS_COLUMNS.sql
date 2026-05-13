-- WageWise V91 Users & Access storage repair
-- Run in Supabase SQL Editor if user creation/update verification fails.

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
