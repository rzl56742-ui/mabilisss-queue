-- ═══════════════════════════════════════════════════════════
--  MabiliSSS Queue V2.2.0 — Complete Database Schema
--  Run in Supabase SQL Editor for FRESH INSTALL
--  For UPGRADES from V2.1.0, use migrate_v220.sql instead
-- ═══════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ═══════════════════════════════════════════════════
--  TABLES
-- ═══════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS branch_config (
    id TEXT PRIMARY KEY DEFAULT 'main',
    name TEXT NOT NULL DEFAULT 'SSS Gingoog Branch',
    address TEXT DEFAULT 'National Highway, Gingoog City',
    hours TEXT DEFAULT 'Mon-Fri, 8:00 AM - 5:00 PM',
    phone TEXT DEFAULT '',
    open_time TEXT DEFAULT '06:00',
    close_time TEXT DEFAULT '16:00',
    announcement TEXT DEFAULT '',
    o_stat TEXT DEFAULT 'online' CHECK (o_stat IN ('online','intermittent','offline')),
    updated_at TIMESTAMPTZ DEFAULT now()
);
INSERT INTO branch_config (id) VALUES ('main') ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    icon TEXT DEFAULT '📋',
    short_label TEXT NOT NULL,
    avg_time INT DEFAULT 10,
    cap INT DEFAULT 50,
    sort_order INT DEFAULT 0,
    bqms_prefix TEXT DEFAULT '',
    bqms_range_start INTEGER DEFAULT NULL,
    bqms_range_end INTEGER DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS services (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    sort_order INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS queue_entries (
    id TEXT PRIMARY KEY,
    queue_date DATE NOT NULL DEFAULT CURRENT_DATE,
    slot INT NOT NULL,
    res_num TEXT NOT NULL,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    mi TEXT DEFAULT '',
    mobile TEXT DEFAULT '',
    service TEXT NOT NULL,
    service_id TEXT,
    category TEXT NOT NULL,
    category_id TEXT,
    cat_icon TEXT DEFAULT '📋',
    priority TEXT DEFAULT 'regular' CHECK (priority IN ('regular','priority')),
    status TEXT DEFAULT 'RESERVED'
        CHECK (status IN ('RESERVED','ARRIVED','SERVING','COMPLETED','CANCELLED','VOID','EXPIRED')),
    bqms_number TEXT,
    bqms_prev TEXT DEFAULT NULL,
    source TEXT DEFAULT 'ONLINE' CHECK (source IN ('ONLINE','KIOSK')),
    issued_at TIMESTAMPTZ DEFAULT now(),
    arrived_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ DEFAULT NULL,
    void_reason TEXT DEFAULT NULL,
    voided_by TEXT DEFAULT NULL,
    voided_at TIMESTAMPTZ DEFAULT NULL,
    expired_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_queue_date ON queue_entries(queue_date);
CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_entries(status);
CREATE INDEX IF NOT EXISTS idx_queue_date_cat ON queue_entries(queue_date, category_id);

CREATE TABLE IF NOT EXISTS bqms_state (
    category_id TEXT PRIMARY KEY,
    now_serving TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staff_users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('kiosk','staff','th','bh','dh')),
    password_hash TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════
--  SEED DATA
-- ═══════════════════════════════════════════════════

INSERT INTO categories (id, label, icon, short_label, avg_time, cap, sort_order,
                        bqms_prefix, bqms_range_start, bqms_range_end) VALUES
    ('ret_death',   'Retirement / Death / Funeral',       '🏖️', 'Ret/Death',  16, 50, 1, '', 1,    999),
    ('smd',         'Sickness / Maternity / Disability',  '🏥', 'Sick/Mat',   14, 50, 2, '', 1001, 1999),
    ('loans',       'Loans',                              '💰', 'Loans',      10, 60, 3, '', 2001, 2999),
    ('membership',  'Membership / ID / Inquiries',        '🪪', 'Members',     8, 60, 4, '', 3001, 3999),
    ('acop',        'ACOP',                               '📋', 'ACOP',       10, 30, 5, '', 4001, 4999),
    ('payments',    'Payments',                            '💳', 'Payments',    7, 70, 6, '', 5001, 5999),
    ('employers',   'Employers',                          '🏢', 'Employers',  12, 30, 7, '', 6001, 6999)
ON CONFLICT (id) DO NOTHING;

INSERT INTO services (id, category_id, label, sort_order) VALUES
    ('retirement',      'ret_death',   'Retirement Claim',           1),
    ('death_claim',     'ret_death',   'Death Claim',                2),
    ('funeral',         'ret_death',   'Funeral Benefit',            3),
    ('sickness',        'smd',         'Sickness Benefit',           1),
    ('maternity',       'smd',         'Maternity / Paternity',      2),
    ('disability',      'smd',         'Disability Benefit',         3),
    ('salary_loan',     'loans',       'Salary Loan',                1),
    ('calamity_loan',   'loans',       'Calamity Loan',              2),
    ('emergency_loan',  'loans',       'Emergency Loan',             3),
    ('consoloan',       'loans',       'Consoloan',                  4),
    ('new_member',      'membership',  'New Registration',           1),
    ('umid',            'membership',  'UMID Enrollment / Release',  2),
    ('e1_update',       'membership',  'E-1 / E-4 Update',          3),
    ('inquiry',         'membership',  'General Inquiry',            4),
    ('member_record',   'membership',  'Member Records',             5),
    ('acop_filing',     'acop',        'ACOP Filing',                1),
    ('acop_followup',   'acop',        'ACOP Follow-up',             2),
    ('pay_contribution','payments',    'Contribution Payment',       1),
    ('pay_loan',        'payments',    'Loan Amortization',          2),
    ('pay_others',      'payments',    'Other Payments / PRN',       3),
    ('er_registration', 'employers',   'Employer Registration',      1),
    ('er_reporting',    'employers',   'Collection / Reporting',     2),
    ('er_inquiry',      'employers',   'Employer Inquiry',           3),
    ('er_certificate',  'employers',   'Employer Certification',     4)
ON CONFLICT (id) DO NOTHING;

INSERT INTO bqms_state (category_id) VALUES
    ('ret_death'),('smd'),('loans'),('membership'),('acop'),('payments'),('employers')
ON CONFLICT (category_id) DO NOTHING;

-- SHA-256 hashed passwords. Default: mnd2026
INSERT INTO staff_users (id, username, display_name, role, password_hash) VALUES
    ('kiosk',  'kiosk',  'Guard / Kiosk',   'kiosk', encode(digest('mnd2026', 'sha256'), 'hex')),
    ('staff1', 'staff1', 'Staff 1',         'staff', encode(digest('mnd2026', 'sha256'), 'hex')),
    ('staff2', 'staff2', 'Staff 2',         'staff', encode(digest('mnd2026', 'sha256'), 'hex')),
    ('th',     'th',     'Team Head',       'th',    encode(digest('mnd2026', 'sha256'), 'hex')),
    ('bh',     'bh',     'Branch Head',     'bh',    encode(digest('mnd2026', 'sha256'), 'hex')),
    ('dh',     'dh',     'Division Head',   'dh',    encode(digest('mnd2026', 'sha256'), 'hex'))
ON CONFLICT (id) DO NOTHING;

-- ═══════════════════════════════════════════════════
--  ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════

ALTER TABLE branch_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE queue_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE bqms_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read"   ON branch_config FOR SELECT USING (true);
CREATE POLICY "anon_update" ON branch_config FOR UPDATE USING (true);

CREATE POLICY "anon_all" ON categories FOR ALL USING (true);
CREATE POLICY "anon_all" ON services   FOR ALL USING (true);

CREATE POLICY "anon_read"   ON queue_entries FOR SELECT              USING (true);
CREATE POLICY "anon_insert" ON queue_entries FOR INSERT WITH CHECK   (true);
CREATE POLICY "anon_update" ON queue_entries FOR UPDATE              USING (true);

CREATE POLICY "anon_read"   ON bqms_state FOR SELECT              USING (true);
CREATE POLICY "anon_insert" ON bqms_state FOR INSERT WITH CHECK   (true);
CREATE POLICY "anon_update" ON bqms_state FOR UPDATE              USING (true);

CREATE POLICY "anon_all" ON staff_users FOR ALL USING (true);

-- ═══════════════════════════════════════════════════
--  VERIFY:
--  SELECT id, bqms_range_start, bqms_range_end FROM categories;
--  SELECT id, username, length(password_hash) as hash_len FROM staff_users;
--  (hash_len should be 64 for all rows)
-- ═══════════════════════════════════════════════════
