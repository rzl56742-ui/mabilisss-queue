# MabiliSSS Queue V2.2.0 — Deployment Guide

## ⚡ Pre-Deployment Checklist

### What Changed (V2.1.0 → V2.2.0)
| Area | Change |
|---|---|
| **Statuses** | Removed NO_SHOW → Added CANCELLED, VOID, EXPIRED |
| **Member Cancel** | Members can cancel their own reservation |
| **Void + Reason** | TH can void entries with audit reason |
| **Auto-Expire** | Past RESERVED entries auto-expire on load |
| **BQMS Series** | Per-category prefix + number range |
| **BQMS Auto-Suggest** | Pre-fills next number in series |
| **BQMS Range Check** | Warns if number outside category series |
| **BQMS Edit** | Staff can change assigned BQMS# with audit |
| **BQMS Auto-Update** | "Serving" click auto-updates Now Serving |
| **Now Serving Inline** | Badges per category always visible |
| **User CRUD** | TH can add/edit/delete/reset staff accounts |
| **Security** | Only TH gets admin (staff = queue ops only) |
| **Passwords** | SHA-256 hashed only (no plain text) |
| **Timezone** | All timestamps PHT (UTC+8) |
| **Performance** | Cached lookups, conditional loading, indexes |

---

## 🔧 Step 1: Database Migration

### For EXISTING Supabase (upgrading from V2.1.0):
1. Open Supabase Dashboard → SQL Editor
2. Copy-paste entire `migrate_v220.sql`
3. Click **RUN**
4. Verify:
```sql
SELECT id, bqms_range_start, bqms_range_end FROM categories;
-- Should show 7 rows with ranges set

SELECT id, username, length(password_hash) as hash_len FROM staff_users;
-- hash_len should be 64 for ALL rows (hashed)

SELECT * FROM queue_entries WHERE status = 'NO_SHOW';
-- Should return 0 rows (all converted to EXPIRED)
```

### For FRESH Supabase (new install):
1. Open Supabase Dashboard → SQL Editor
2. Copy-paste entire `schema.sql`
3. Click **RUN**
4. Same verification queries above

---

## 🔧 Step 2: Update GitHub Repository

### Files to update:
```
db.py            → Root of repo (shared database layer)
member_app.py    → Root or pages/ (member portal)
staff_app.py     → Root or pages/ (staff console)
requirements.txt → Root (no changes but verify)
```

### Git commands:
```bash
git add db.py member_app.py staff_app.py requirements.txt
git commit -m "V2.2.0: Cancel/Void/Expire, BQMS series, User CRUD, security fixes"
git push origin main
```

---

## 🔧 Step 3: Streamlit Cloud

Streamlit Cloud auto-deploys from GitHub. After push:
1. Check deploy log for errors
2. Both apps should restart automatically
3. If not, click "Reboot app" in Streamlit Cloud dashboard

---

## 🔧 Step 4: Post-Deployment Verification

### Login Test
- Go to Staff Portal
- Login with `th` / `mnd2026`
- If login fails → migration Step 5 (password hashing) didn't run

### BQMS Series Test
1. Admin → Categories → Check each category shows series range
2. Queue → Add Walk-in → Select category → BQMS field auto-suggests number

### Cancel Test (Member Side)
1. Member Portal → Reserve a slot
2. Track My Queue → Tap Cancel → Confirm
3. Status should show "Cancelled", slot freed

### Void Test (Staff Side)
1. Staff Portal → Find an ARRIVED entry → Tap Void
2. Enter reason → Confirm
3. Status shows "Voided" with reason visible

### User Management Test
1. Admin → Users → Add a test user
2. Login with test user → verify role restrictions
3. Delete test user

---

## ⚠️ Rollback Plan

If critical issues found:
1. **Database**: New columns are additive (won't break V2.1.0 code)
2. **Code**: Revert git commit: `git revert HEAD && git push`
3. **Status constraint**: Only issue — V2.1.0 can't write CANCELLED/VOID/EXPIRED
4. **Passwords**: If hashing breaks login, run in SQL Editor:
```sql
UPDATE staff_users SET password_hash = encode(digest('mnd2026', 'sha256'), 'hex');
```

---

## 📊 BQMS Series Reference (Gingoog Branch Default)

| Category | ID | Range |
|---|---|---|
| Retirement/Death/Funeral | ret_death | 1 – 999 |
| Sickness/Maternity/Disability | smd | 1001 – 1999 |
| Loans | loans | 2001 – 2999 |
| Membership/ID/Inquiries | membership | 3001 – 3999 |
| ACOP | acop | 4001 – 4999 |
| Payments | payments | 5001 – 5999 |
| Employers | employers | 6001 – 6999 |

*Customize via Admin → Categories → BQMS Number Series*

---

## 👤 Default Accounts

| Username | Role | Default Password |
|---|---|---|
| kiosk | Kiosk Operator | mnd2026 |
| staff1 | Staff In-Charge | mnd2026 |
| staff2 | Staff In-Charge | mnd2026 |
| th | Team Head | mnd2026 |
| bh | Branch Head | mnd2026 |
| dh | Division Head | mnd2026 |

**⚠️ Change all passwords immediately after deployment via Admin → Users**
