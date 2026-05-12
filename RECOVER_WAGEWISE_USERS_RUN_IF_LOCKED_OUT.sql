-- WageWise V88 user access recovery
-- Use this in Supabase SQL Editor if you are locked out.
-- This resets ONLY the login table.

DELETE FROM public."sms_users";

INSERT INTO public."sms_users"
("email", "name", "role", "password_hash", "active", "allow_admin", "allow_supervisor")
VALUES
('admin@wagewise.local', 'WageWise Admin', 'Admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'True', 'True', 'True'),
('supervisor@wagewise.local', 'WageWise Supervisor', 'Supervisor', '02423ab2e61297b8262449c93e19be42fb5bbb275860a7d93b1ebdc7b6535ed7', 'True', 'False', 'True');
