"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Database Layer V2.2.0 (Supabase)
 Shared by member_app.py and staff_app.py
 All times in PHT (UTC+8)
═══════════════════════════════════════════════════════════
"""

import streamlit as st
from supabase import create_client
from datetime import date, datetime, timezone, timedelta
import time, uuid, hashlib, re

VER = "V2.2.0"

# ── Philippine Standard Time ──
PHT = timezone(timedelta(hours=8))

def now_pht():
    return datetime.now(PHT)

def today_pht():
    return now_pht().date()

def today_iso():
    return today_pht().isoformat()

def today_mmdd():
    return today_pht().strftime("%m%d")

# ── SSS Official Logo ──
SSS_LOGO = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Social_Security_System_%28Philippines%29_logo.svg/1200px-Social_Security_System_%28Philippines%29_logo.svg.png"

# ── Supabase Connection ──
def get_supabase():
    if "sb_client" not in st.session_state:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except Exception:
            import os
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            st.error("❌ Missing Supabase credentials.")
            st.stop()
        st.session_state.sb_client = create_client(url, key)
    return st.session_state.sb_client

# ── ID / Password Helpers ──
def gen_id():
    """Unique ID: microsecond timestamp + 8-char UUID to prevent collision."""
    return f"{int(time.time()*1_000_000)}-{uuid.uuid4().hex[:8]}"

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def validate_mobile_ph(mobile):
    """Validate Philippine mobile: 09XX XXXX XXX (11 digits starting with 09)."""
    digits = re.sub(r'\D', '', mobile)
    if len(digits) == 11 and digits.startswith("09"):
        return digits
    if len(digits) == 12 and digits.startswith("639"):
        return "0" + digits[2:]
    return None

# ═══════════════════════════════════════════════════
#  CACHED LOOKUPS (branch + categories change rarely)
# ═══════════════════════════════════════════════════
@st.cache_data(ttl=60)
def get_branch_cached():
    sb = get_supabase()
    r = sb.table("branch_config").select("*").eq("id", "main").execute()
    if r.data:
        return r.data[0]
    return {"id": "main", "name": "SSS Gingoog Branch", "address": "", "hours": "",
            "announcement": "", "o_stat": "online"}

def get_branch():
    return get_branch_cached()

def invalidate_branch():
    get_branch_cached.clear()

@st.cache_data(ttl=60)
def get_categories_cached():
    sb = get_supabase()
    r = sb.table("categories").select("*").order("sort_order").execute()
    return r.data or []

@st.cache_data(ttl=60)
def get_services_cached():
    sb = get_supabase()
    r = sb.table("services").select("*").order("sort_order").execute()
    return r.data or []

def get_categories():
    return get_categories_cached()

def get_services(category_id=None):
    svcs = get_services_cached()
    if category_id:
        return [s for s in svcs if s["category_id"] == category_id]
    return svcs

def get_categories_with_services():
    cats = [dict(c) for c in get_categories()]  # copy to avoid mutating cache
    svcs = get_services()
    svc_map = {}
    for s in svcs:
        svc_map.setdefault(s["category_id"], []).append(s)
    for c in cats:
        c["services"] = svc_map.get(c["id"], [])
    return cats

def invalidate_categories():
    get_categories_cached.clear()
    get_services_cached.clear()

# ═══════════════════════════════════════════════════
#  BRANCH CONFIG — WRITES
# ═══════════════════════════════════════════════════
def update_branch(**kwargs):
    sb = get_supabase()
    kwargs["updated_at"] = now_pht().isoformat()
    sb.table("branch_config").update(kwargs).eq("id", "main").execute()
    invalidate_branch()

# ═══════════════════════════════════════════════════
#  CATEGORIES — FULL CRUD
# ═══════════════════════════════════════════════════
def add_category(cat_id, label, icon, short_label, avg_time, cap, sort_order,
                 bqms_prefix="", bqms_range_start=None, bqms_range_end=None):
    sb = get_supabase()
    sb.table("categories").insert({
        "id": cat_id, "label": label, "icon": icon,
        "short_label": short_label, "avg_time": avg_time,
        "cap": cap, "sort_order": sort_order,
        "bqms_prefix": bqms_prefix or "",
        "bqms_range_start": bqms_range_start,
        "bqms_range_end": bqms_range_end,
    }).execute()
    try:
        sb.table("bqms_state").insert({"category_id": cat_id}).execute()
    except:
        pass
    invalidate_categories()

def update_category(cat_id, **kwargs):
    sb = get_supabase()
    sb.table("categories").update(kwargs).eq("id", cat_id).execute()
    invalidate_categories()

def delete_category(cat_id):
    """Delete category + its services + bqms_state. Checks for active entries first."""
    sb = get_supabase()
    sb.table("services").delete().eq("category_id", cat_id).execute()
    try:
        sb.table("bqms_state").delete().eq("category_id", cat_id).execute()
    except:
        pass
    sb.table("categories").delete().eq("id", cat_id).execute()
    invalidate_categories()

def has_active_entries(cat_id):
    """Check if category has active (non-terminal) queue entries today."""
    q = get_queue_today()
    return any(r.get("category_id") == cat_id and r.get("status") in ("RESERVED", "ARRIVED", "SERVING")
               for r in q)

# ═══════════════════════════════════════════════════
#  SERVICES (Sub-Categories) — FULL CRUD
# ═══════════════════════════════════════════════════
def add_service(svc_id, category_id, label, sort_order=0):
    sb = get_supabase()
    sb.table("services").insert({
        "id": svc_id, "category_id": category_id,
        "label": label, "sort_order": sort_order
    }).execute()
    invalidate_categories()

def update_service(svc_id, **kwargs):
    sb = get_supabase()
    sb.table("services").update(kwargs).eq("id", svc_id).execute()
    invalidate_categories()

def delete_service(svc_id):
    sb = get_supabase()
    sb.table("services").delete().eq("id", svc_id).execute()
    invalidate_categories()

# ═══════════════════════════════════════════════════
#  QUEUE ENTRIES — READS
# ═══════════════════════════════════════════════════
# Terminal statuses: entry is "done" — no more actions
TERMINAL = ("COMPLETED", "CANCELLED", "VOID", "EXPIRED")
# Freed statuses: slot goes back to daily cap pool
FREED = ("CANCELLED", "VOID")

def get_queue_today():
    sb = get_supabase()
    r = sb.table("queue_entries").select("*").eq("queue_date", today_iso()).order("slot").execute()
    return r.data or []

def get_queue_by_date(target_date):
    sb = get_supabase()
    r = sb.table("queue_entries").select("*").eq("queue_date", target_date).order("slot").execute()
    return r.data or []

def get_queue_date_range(start_date, end_date):
    sb = get_supabase()
    r = (sb.table("queue_entries").select("*")
         .gte("queue_date", start_date)
         .lte("queue_date", end_date)
         .order("queue_date").order("slot")
         .execute())
    return r.data or []

# ═══════════════════════════════════════════════════
#  QUEUE ENTRIES — WRITES
# ═══════════════════════════════════════════════════
def insert_queue_entry(entry):
    sb = get_supabase()
    sb.table("queue_entries").insert(entry).execute()

def update_queue_entry(entry_id, **kwargs):
    sb = get_supabase()
    sb.table("queue_entries").update(kwargs).eq("id", entry_id).execute()

def cancel_entry(entry_id):
    """Member self-cancellation. Frees the slot."""
    update_queue_entry(entry_id, status="CANCELLED", cancelled_at=now_pht().isoformat())

def void_entry(entry_id, reason, voided_by):
    """TH admin void. Frees the slot. Requires reason for audit."""
    update_queue_entry(entry_id,
                       status="VOID",
                       void_reason=reason,
                       voided_by=voided_by,
                       voided_at=now_pht().isoformat())

def expire_old_reserved():
    """Auto-expire: set all RESERVED entries from past dates to EXPIRED.
    Called on app load. Handles entries from any previous day still in RESERVED."""
    sb = get_supabase()
    today = today_iso()
    sb.table("queue_entries").update({
        "status": "EXPIRED",
        "expired_at": now_pht().isoformat()
    }).eq("status", "RESERVED").lt("queue_date", today).execute()

# ═══════════════════════════════════════════════════
#  SLOT / CAP LOGIC
# ═══════════════════════════════════════════════════
def count_daily_by_category(queue_list, cat_id):
    """Count entries consuming a daily cap slot.
    ALL entries count EXCEPT: CANCELLED, VOID (these free slots).
    COMPLETED still counts — cap is for the WHOLE DAY.
    EXPIRED still counts — they occupied a slot during the day."""
    return len([r for r in queue_list
                if r.get("category_id") == cat_id
                and r.get("status") not in FREED])

def slot_counts(cats, queue_list):
    m = {}
    for c in cats:
        used = count_daily_by_category(queue_list, c["id"])
        cap = c.get("cap", 50)
        m[c["id"]] = {"used": used, "cap": cap, "remaining": max(0, cap - used)}
    return m

def next_slot_num(queue_list):
    """Next slot number. Uses max existing slot + 1 to handle gaps from deletes."""
    if not queue_list:
        return 1
    max_slot = max(r.get("slot", 0) for r in queue_list)
    return max_slot + 1

# ═══════════════════════════════════════════════════
#  BQMS VALIDATION & SERIES
# ═══════════════════════════════════════════════════
def is_bqms_taken(queue_list, bqms_number, exclude_id=None):
    """Check if BQMS# is already assigned today. Excludes terminal entries.
    exclude_id: skip this entry (for edit scenarios)."""
    if not bqms_number:
        return False
    bn = bqms_number.strip().upper()
    for r in queue_list:
        if exclude_id and r.get("id") == exclude_id:
            continue
        if r.get("status") in TERMINAL:
            continue
        if (r.get("bqms_number") or "").strip().upper() == bn:
            return True
    return False

def extract_bqms_num(bqms_str):
    """Extract numeric portion from a BQMS string. '2005' → 2005, 'L-023' → 23."""
    digits = re.sub(r'\D', '', str(bqms_str))
    return int(digits) if digits else None

def validate_bqms_range(bqms_str, category):
    """Check if BQMS# falls within the category's configured range.
    Returns (ok, message)."""
    rs = category.get("bqms_range_start")
    re_ = category.get("bqms_range_end")
    if rs is None or re_ is None:
        return True, ""  # No range configured — skip validation
    num = extract_bqms_num(bqms_str)
    if num is None:
        return False, "Could not parse number from BQMS input."
    if rs <= num <= re_:
        return True, ""
    return False, f"Number {num} is outside {category.get('short_label','')} series ({rs}–{re_})."

def suggest_next_bqms(queue_list, category):
    """Auto-suggest the next BQMS# for a category based on assigned numbers today."""
    cat_id = category["id"]
    prefix = category.get("bqms_prefix", "") or ""
    rs = category.get("bqms_range_start")

    # Find highest BQMS number assigned in this category today
    max_num = 0
    for r in queue_list:
        if r.get("category_id") != cat_id:
            continue
        if r.get("status") in TERMINAL:
            continue
        bn = r.get("bqms_number", "")
        if not bn:
            continue
        n = extract_bqms_num(bn)
        if n and n > max_num:
            max_num = n

    if max_num > 0:
        suggested = max_num + 1
    elif rs:
        suggested = rs  # Start of range
    else:
        return ""  # No range, no history — can't suggest

    return f"{prefix}{suggested}"

def find_bqms_conflict_category(bqms_str, cats, current_cat_id):
    """Check if a BQMS# belongs to a different category's range."""
    num = extract_bqms_num(bqms_str)
    if num is None:
        return None
    for c in cats:
        if c["id"] == current_cat_id:
            continue
        rs = c.get("bqms_range_start")
        re_ = c.get("bqms_range_end")
        if rs and re_ and rs <= num <= re_:
            return c
    return None

# ═══════════════════════════════════════════════════
#  BQMS STATE (Now Serving)
# ═══════════════════════════════════════════════════
def get_bqms_state():
    sb = get_supabase()
    r = sb.table("bqms_state").select("*").execute()
    return {row["category_id"]: row.get("now_serving", "") for row in (r.data or [])}

def update_bqms_state(category_id, now_serving):
    sb = get_supabase()
    sb.table("bqms_state").update({
        "now_serving": now_serving,
        "updated_at": now_pht().isoformat()
    }).eq("category_id", category_id).execute()

def auto_update_now_serving(entry):
    """Auto-update 'Now Serving' when entry status changes to SERVING or COMPLETED."""
    bqms = entry.get("bqms_number")
    cat_id = entry.get("category_id")
    if bqms and cat_id:
        update_bqms_state(cat_id, bqms)

# ═══════════════════════════════════════════════════
#  QUEUE AHEAD / WAIT ESTIMATION
# ═══════════════════════════════════════════════════
def count_ahead(queue_list, entry):
    """Count active entries in same category with lower BQMS# (ahead in line)."""
    my_bqms = entry.get("bqms_number", "")
    my_cat = entry.get("category_id", "")
    if not my_bqms:
        return 0
    my_num = extract_bqms_num(my_bqms)
    if my_num is None:
        return 0
    count = 0
    for r in queue_list:
        if r.get("id") == entry.get("id"):
            continue
        if r.get("category_id") != my_cat:
            continue
        if r.get("status") in TERMINAL or r.get("status") == "SERVING":
            continue
        rn = extract_bqms_num(r.get("bqms_number", ""))
        if rn is not None and rn < my_num:
            count += 1
    return count

# ═══════════════════════════════════════════════════
#  DUPLICATE DETECTION
# ═══════════════════════════════════════════════════
def is_duplicate(queue_list, last, first, mobile_clean):
    """Check for duplicate active entry. Uses cleaned mobile (digits only)."""
    nk = f"{last}|{first}"
    for r in queue_list:
        if r.get("status") in TERMINAL:
            continue
        if f"{r.get('last_name', '')}|{r.get('first_name', '')}" == nk:
            return True
        if mobile_clean and r.get("mobile"):
            r_clean = re.sub(r'\D', '', r["mobile"])
            if r_clean == mobile_clean:
                return True
    return False

# ═══════════════════════════════════════════════════
#  STAFF USERS — FULL CRUD
# ═══════════════════════════════════════════════════
def get_users():
    sb = get_supabase()
    r = sb.table("staff_users").select("*").execute()
    return r.data or []

def authenticate(username, password):
    """Authenticate using HASHED password only. No plain-text fallback."""
    users = get_users()
    u = next((x for x in users
              if x["username"].lower() == username.strip().lower()
              and x.get("active", True)), None)
    if not u:
        return None
    if u["password_hash"] == hash_pw(password):
        return u
    return None

def add_user(user_id, username, display_name, role, password):
    sb = get_supabase()
    sb.table("staff_users").insert({
        "id": user_id, "username": username.strip().lower(),
        "display_name": display_name.strip(),
        "role": role, "password_hash": hash_pw(password),
        "active": True,
        "created_at": now_pht().isoformat(),
        "updated_at": now_pht().isoformat(),
    }).execute()

def update_user(user_id, **kwargs):
    sb = get_supabase()
    kwargs["updated_at"] = now_pht().isoformat()
    sb.table("staff_users").update(kwargs).eq("id", user_id).execute()

def delete_user(user_id):
    sb = get_supabase()
    sb.table("staff_users").delete().eq("id", user_id).execute()

def reset_password(user_id, new_password):
    sb = get_supabase()
    sb.table("staff_users").update({
        "password_hash": hash_pw(new_password),
        "updated_at": now_pht().isoformat()
    }).eq("id", user_id).execute()

def update_password(user_id, new_password):
    reset_password(user_id, new_password)

# ═══════════════════════════════════════════════════
#  STATUS CONSTANTS
# ═══════════════════════════════════════════════════
OSTATUS = {
    "online":       {"label": "Reservation Open",             "emoji": "🟢", "color": "green"},
    "intermittent": {"label": "Intermittent — Expect Delays", "emoji": "🟡", "color": "yellow"},
    "offline":      {"label": "Reservation Closed",           "emoji": "🔴", "color": "red"},
}

STATUS_LABELS = {
    "RESERVED":  "📋 Reserved",
    "ARRIVED":   "✅ Arrived",
    "SERVING":   "🔵 Serving",
    "COMPLETED": "✅ Completed",
    "CANCELLED": "🚫 Cancelled",
    "VOID":      "⚙️ Voided",
    "EXPIRED":   "⏰ Expired",
}

ROLES = ["kiosk", "staff", "th", "bh", "dh"]
ROLE_LABELS = {"kiosk": "Kiosk Operator", "staff": "Staff In-Charge",
               "th": "Team Head / Section Head", "bh": "Branch Head", "dh": "Division Head"}
ROLE_ICONS = {"kiosk": "🏢", "staff": "🛡️", "th": "👔", "bh": "🏛️", "dh": "⭐"}
