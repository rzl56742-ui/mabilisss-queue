# MabiliSSS Queue V2.2.0 — Audit Fix Map

## Every bug from the pre-implementation audit → exact fix location

### PHASE 1 FIXES (Foundation)

| Bug ID | Issue | Fix Location | Status |
|--------|-------|-------------|--------|
| BUG-01/02/07/12 | Timezone: datetime.now() returns UTC | db.py L17-29: PHT timezone + now_pht()/today_pht()/today_iso() | ✅ FIXED |
| BUG-04/10 | Slot race condition | db.py L272-277: next_slot_num uses max(slot)+1 + gen_id uses microsecond+UUID | ✅ MITIGATED |
| BUG-03 | Cap logic incomplete for new statuses | db.py L255-262: FREED tuple excludes CANCELLED,VOID from cap count | ✅ FIXED |
| BUG-05 | Duplicate check: mobile spaces | db.py L58-65: validate_mobile_ph strips non-digits; L409-421: is_duplicate uses cleaned mobile | ✅ FIXED |
| BUG-06 | Plain text passwords | db.py L431-441: authenticate hash-only; schema.sql seeds with pgcrypto hash; migrate_v220.sql L30-32: converts existing plain text | ✅ FIXED |
| BUG-08 | Unconditional data loading | member_app.py L71-97: conditional loading per screen | ✅ FIXED |
| BUG-09 | Stale session data | member_app.py L196,246: stores ID only, fetches fresh on each screen | ✅ FIXED |
| BUG-13 | Session timeout bypassed by auto-refresh | staff_app.py L105-118: max 8h session duration (not inactivity-based) | ✅ FIXED |
| BUG-14 | Status radio flash writes | staff_app.py L206-210: compares new_stat != o_stat before writing | ✅ FIXED |
| BUG-15 | No-Show buttons still exist | Removed entirely — replaced by CANCELLED/VOID/EXPIRED | ✅ FIXED |
| BUG-16 | Serving click doesn't update Now Serving | staff_app.py L511,517,530: auto_update_now_serving() on Serving/Complete | ✅ FIXED |
| LOGIC-03 | delete_category doesn't check active entries | db.py L165-169: has_active_entries() check; staff_app.py L683-684: blocks delete | ✅ FIXED |
| LOGIC-04/06 | Dual submit buttons in forms | staff_app.py L220-228: announcement buttons outside form; L686: delete outside form | ✅ FIXED |
| LOGIC-07 | Service ID collision | staff_app.py L769: UUID suffix in service ID | ✅ FIXED |
| SEC-01 | Staff has full admin access | staff_app.py L122: is_admin_role = ("th",) only | ✅ FIXED |
| SEC-02 | Users tab display-only | staff_app.py L802-894: full CRUD + password reset | ✅ FIXED |
| DB-01 | Missing cancelled_at, void_reason, voided_by | schema.sql + migrate_v220.sql: all columns added | ✅ FIXED |
| DB-02 | Missing BQMS series columns | schema.sql + migrate_v220.sql: bqms_prefix, range_start, range_end | ✅ FIXED |
| DB-03 | Missing bqms_prev column | schema.sql + migrate_v220.sql: bqms_prev added | ✅ FIXED |
| DB-04 | Missing queue_date index | schema.sql + migrate_v220.sql: idx_queue_date, idx_queue_status, idx_queue_date_cat | ✅ FIXED |
| DB-05 | Missing created_at on staff_users | schema.sql + migrate_v220.sql: created_at, updated_at added | ✅ FIXED |
| PERF-01/04 | Excessive DB calls | db.py L70-118: @st.cache_data(ttl=60) on branch/categories/services | ✅ FIXED |
| PERF-02 | get_available_dates fetches all | Removed — replaced by date range picker in dashboard | ✅ FIXED |
| PERF-03 | gen_id collision risk | db.py L52-53: microsecond + 8-char UUID | ✅ MITIGATED |
| UX-02 | Active Queue inflated | member_app.py L145-147: split into Waiting/Being Served/Completed | ✅ FIXED |
| UX-03 | Mobile validation too loose | db.py L58-65: validate_mobile_ph enforces 09XX 11-digit or +63 format | ✅ FIXED |

### PHASE 2 FEATURES (V2.2.0)

| Feature | Location | Linked To |
|---------|----------|-----------|
| Member self-cancel | member_app.py L539-568, db.py L230-232 | BUG-03 (cap), DB-01 (cancelled_at) |
| Void with reason | staff_app.py L542-562, db.py L234-240 | DB-01 (void_reason, voided_by, voided_at) |
| Auto-expire | db.py L242-250, member/staff apps expire_old_reserved() | BUG-01 (timezone), DB-01 (expired_at) |
| BQMS auto-update | db.py L374-379, staff_app.py L511,517,530 | BUG-16 |
| BQMS series config | staff_app.py L647-680, db.py L302-357 | DB-02 (bqms_prefix, range columns) |
| BQMS auto-suggest | db.py L316-343, staff_app.py L465,299 | DB-02, BQMS series |
| BQMS range validation | db.py L302-314, staff_app.py L492-494 | DB-02 |
| BQMS edit | staff_app.py L564-602, db.py update_queue_entry | DB-03 (bqms_prev) |
| Now Serving inline | staff_app.py L234-245 | BUG-16, auto-update |
| User CRUD | staff_app.py L802-894, db.py L426-471 | SEC-02, DB-05 |
| Walk-in registration | staff_app.py L268-369 | BQMS series, cap logic |
| CSV export (complete) | staff_app.py L976-1009 | All audit fields |

### SCHEMA FIXES FOUND IN THIS SESSION

| Issue | Fix |
|-------|-----|
| migrate_v220.sql had wrong category IDs (sick_mat, members) | Corrected to smd, membership |
| schema.sql status CHECK still had NO_SHOW | Updated to include CANCELLED, VOID, EXPIRED |
| schema.sql seed passwords plain text | Changed to pgcrypto digest() hashed |
| schema.sql missing BQMS/audit columns | Added all V2.2.0 columns |
| RLS missing INSERT/DELETE on staff_users | Added full CRUD policies |
| RLS missing INSERT on bqms_state | Added insert policy |
| migrate_v220.sql missing pgcrypto extension | Added CREATE EXTENSION pgcrypto |
| migrate_v220.sql missing status CHECK update | Added DROP + ADD constraint |
