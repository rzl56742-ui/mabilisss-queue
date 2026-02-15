-- ═══════════════════════════════════════════════════════════
--  MabiliSSS Queue V2.2.0 — Migration from V2.1.0
--  Run in Supabase SQL Editor BEFORE deploying V2.2.0 code
-- ═══════════════════════════════════════════════════════════

-- Enable pgcrypto for password hashing
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── 1. Performance indexes ──
CREATE INDEX IF NOT EXISTS idx_queue_date ON queue_entries(queue_date);
CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_entries(status);
CREATE INDEX IF NOT EXISTS idx_queue_date_cat ON queue_entries(queue_date, category_id);

-- ── 2. Categories: BQMS series columns ──
ALTER TABLE categories ADD COLUMN IF NOT EXISTS bqms_prefix TEXT DEFAULT '';
ALTER TABLE categories ADD COLUMN IF NOT EXISTS bqms_range_start INTEGER DEFAULT NULL;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS bqms_range_end INTEGER DEFAULT NULL;

-- ── 3. Queue entries: new status values + audit fields ──
-- Update CHECK constraint to support CANCELLED, VOID, EXPIRED
ALTER TABLE queue_entries DROP CONSTRAINT IF EXISTS queue_entries_status_check;
ALTER TABLE queue_entries ADD CONSTRAINT queue_entries_status_check
    CHECK (status IN ('RESERVED','ARRIVED','SERVING','COMPLETED','CANCELLED','VOID','EXPIRED'));

-- New audit columns
ALTER TABLE queue_entries ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE queue_entries ADD COLUMN IF NOT EXISTS void_reason TEXT DEFAULT NULL;
ALTER TABLE queue_entries ADD COLUMN IF NOT EXISTS voided_by TEXT DEFAULT NULL;
ALTER TABLE queue_entries ADD COLUMN IF NOT EXISTS voided_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE queue_entries ADD COLUMN IF NOT EXISTS expired_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE queue_entries ADD COLUMN IF NOT EXISTS bqms_prev TEXT DEFAULT NULL;

-- ── 4. Staff users: audit timestamps ──
ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE staff_users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ── 5. Hash existing PLAIN-TEXT passwords ──
-- Only converts passwords shorter than 64 chars (not already hashed)
UPDATE staff_users
SET password_hash = encode(digest(password_hash, 'sha256'), 'hex')
WHERE length(password_hash) < 64;

-- ── 6. BQMS series for default categories ──
-- ⚠️ CRITICAL: IDs must match YOUR categories table exactly
-- Verify with: SELECT id FROM categories;
UPDATE categories SET bqms_prefix = '', bqms_range_start = 1,    bqms_range_end = 999   WHERE id = 'ret_death';
UPDATE categories SET bqms_prefix = '', bqms_range_start = 1001, bqms_range_end = 1999  WHERE id = 'smd';
UPDATE categories SET bqms_prefix = '', bqms_range_start = 2001, bqms_range_end = 2999  WHERE id = 'loans';
UPDATE categories SET bqms_prefix = '', bqms_range_start = 3001, bqms_range_end = 3999  WHERE id = 'membership';
UPDATE categories SET bqms_prefix = '', bqms_range_start = 4001, bqms_range_end = 4999  WHERE id = 'acop';
UPDATE categories SET bqms_prefix = '', bqms_range_start = 5001, bqms_range_end = 5999  WHERE id = 'payments';
UPDATE categories SET bqms_prefix = '', bqms_range_start = 6001, bqms_range_end = 6999  WHERE id = 'employers';

-- ── 7. Convert legacy NO_SHOW to EXPIRED ──
UPDATE queue_entries SET status = 'EXPIRED' WHERE status = 'NO_SHOW';

-- ── 8. Fix RLS: add missing INSERT/DELETE policies for staff_users + bqms_state ──
-- Drop old restrictive policies if they exist, replace with full CRUD
DO $$
BEGIN
    -- staff_users: ensure INSERT and DELETE exist
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='staff_users' AND policyname='anon_insert') THEN
        CREATE POLICY "anon_insert" ON staff_users FOR INSERT WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='staff_users' AND policyname='anon_delete') THEN
        CREATE POLICY "anon_delete" ON staff_users FOR DELETE USING (true);
    END IF;
    -- bqms_state: ensure INSERT exists
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='bqms_state' AND policyname='anon_insert')
       AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='bqms_state' AND policyname='Allow all insert') THEN
        CREATE POLICY "anon_insert" ON bqms_state FOR INSERT WITH CHECK (true);
    END IF;
END$$;

-- ═══════════════════════════════════════════════════════════
--  VERIFY:
--  SELECT id, bqms_range_start, bqms_range_end FROM categories;
--  SELECT id, username, length(password_hash) as hash_len FROM staff_users;
--  SELECT * FROM queue_entries WHERE status = 'NO_SHOW';  -- should be 0 rows
-- ═══════════════════════════════════════════════════════════
