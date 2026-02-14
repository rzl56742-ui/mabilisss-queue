"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Database Layer (Supabase)
 Shared by member_app.py and staff_app.py
═══════════════════════════════════════════════════════════
"""

import streamlit as st
from supabase import create_client
from datetime import date, datetime
import time, uuid, hashlib

VER = "V2.0.0"

# ── Supabase Connection ──
# Reads from Streamlit secrets (deployed) or falls back to env vars
def get_supabase():
    """Get or create cached Supabase client."""
    if "sb_client" not in st.session_state:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except Exception:
            import os
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            st.error("❌ Missing Supabase credentials. Check secrets or environment.")
            st.stop()
        st.session_state.sb_client = create_client(url, key)
    return st.session_state.sb_client

# ── Helpers ──
def today_iso():
    return date.today().isoformat()

def today_mmdd():
    return date.today().strftime("%m%d")

def gen_id():
    return f"{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ═══════════════════════════════════════════════════
#  BRANCH CONFIG
# ═══════════════════════════════════════════════════
def get_branch():
    sb = get_supabase()
    r = sb.table("branch_config").select("*").eq("id", "main").execute()
    if r.data:
        return r.data[0]
    return {"id":"main","name":"SSS Gingoog Branch","address":"","hours":"","announcement":"","o_stat":"online"}

def update_branch(**kwargs):
    sb = get_supabase()
    kwargs["updated_at"] = datetime.now().isoformat()
    sb.table("branch_config").update(kwargs).eq("id", "main").execute()

# ═══════════════════════════════════════════════════
#  CATEGORIES & SERVICES
# ═══════════════════════════════════════════════════
def get_categories():
    sb = get_supabase()
    r = sb.table("categories").select("*").order("sort_order").execute()
    return r.data or []

def get_services(category_id=None):
    sb = get_supabase()
    q = sb.table("services").select("*")
    if category_id:
        q = q.eq("category_id", category_id)
    r = q.order("sort_order").execute()
    return r.data or []

def get_categories_with_services():
    """Returns categories with nested services list — used by both portals."""
    cats = get_categories()
    svcs = get_services()
    svc_map = {}
    for s in svcs:
        cid = s["category_id"]
        if cid not in svc_map:
            svc_map[cid] = []
        svc_map[cid].append(s)
    for c in cats:
        c["services"] = svc_map.get(c["id"], [])
    return cats

def update_category_cap(cat_id, new_cap):
    sb = get_supabase()
    sb.table("categories").update({"cap": new_cap}).eq("id", cat_id).execute()

# ═══════════════════════════════════════════════════
#  QUEUE ENTRIES
# ═══════════════════════════════════════════════════
def get_queue_today():
    sb = get_supabase()
    r = sb.table("queue_entries").select("*").eq("queue_date", today_iso()).order("slot").execute()
    return r.data or []

def insert_queue_entry(entry):
    sb = get_supabase()
    sb.table("queue_entries").insert(entry).execute()

def update_queue_entry(entry_id, **kwargs):
    sb = get_supabase()
    sb.table("queue_entries").update(kwargs).eq("id", entry_id).execute()

def count_active_by_category(queue_list, cat_id):
    return len([r for r in queue_list if r.get("category_id") == cat_id and r.get("status") not in ("NO_SHOW","COMPLETED")])

def slot_counts(cats, queue_list):
    m = {}
    for c in cats:
        used = count_active_by_category(queue_list, c["id"])
        cap = c.get("cap", 50)
        m[c["id"]] = {"used": used, "cap": cap, "remaining": max(0, cap - used)}
    return m

def next_slot_num(queue_list):
    return len(queue_list) + 1

def is_bqms_taken(queue_list, bqms_number):
    """Check if a BQMS number is already assigned to an active entry today."""
    if not bqms_number:
        return False
    bn = bqms_number.strip().upper()
    for r in queue_list:
        if r.get("status") in ("NO_SHOW", "COMPLETED"):
            continue
        if (r.get("bqms_number") or "").strip().upper() == bn:
            return True
    return False

def count_ahead(queue_list, entry):
    """Count active entries in same category with BQMS# ahead of this entry."""
    my_bqms = entry.get("bqms_number", "")
    my_cat = entry.get("category_id", "")
    if not my_bqms:
        return 0
    try:
        my_num = int("".join(filter(str.isdigit, str(my_bqms))))
    except:
        return 0
    count = 0
    for r in queue_list:
        if r.get("id") == entry.get("id"):
            continue
        if r.get("category_id") != my_cat:
            continue
        if r.get("status") in ("NO_SHOW", "COMPLETED", "SERVING"):
            continue
        rb = r.get("bqms_number", "")
        if not rb:
            continue
        try:
            rn = int("".join(filter(str.isdigit, str(rb))))
            if rn < my_num:
                count += 1
        except:
            continue
    return count

def is_duplicate(queue_list, last, first, mobile):
    nk = f"{last}|{first}"
    for r in queue_list:
        if r.get("status") in ("NO_SHOW","COMPLETED"):
            continue
        if f"{r.get('last_name','')}|{r.get('first_name','')}" == nk:
            return True
        if mobile and r.get("mobile") and r["mobile"] == mobile:
            return True
    return False

# ═══════════════════════════════════════════════════
#  BQMS STATE
# ═══════════════════════════════════════════════════
def get_bqms_state():
    sb = get_supabase()
    r = sb.table("bqms_state").select("*").execute()
    m = {}
    for row in (r.data or []):
        m[row["category_id"]] = row.get("now_serving", "")
    return m

def update_bqms_state(category_id, now_serving):
    sb = get_supabase()
    sb.table("bqms_state").update({
        "now_serving": now_serving,
        "updated_at": datetime.now().isoformat()
    }).eq("category_id", category_id).execute()

# ═══════════════════════════════════════════════════
#  STAFF USERS
# ═══════════════════════════════════════════════════
def get_users():
    sb = get_supabase()
    r = sb.table("staff_users").select("*").execute()
    return r.data or []

def authenticate(username, password):
    """Returns user dict or None."""
    users = get_users()
    u = next((x for x in users if x["username"].lower() == username.strip().lower() and x.get("active", True)), None)
    if not u:
        return None
    # Support both plain text (initial) and hashed passwords
    pw_hash = hash_pw(password)
    if u["password_hash"] == password or u["password_hash"] == pw_hash:
        return u
    return None

def update_password(user_id, new_password):
    sb = get_supabase()
    sb.table("staff_users").update({"password_hash": hash_pw(new_password)}).eq("id", user_id).execute()

# ═══════════════════════════════════════════════════
#  STATUS HELPERS
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
    "NO_SHOW":   "❌ No-Show",
}
