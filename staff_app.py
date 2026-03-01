"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Staff Console V2.3.0-P3 (Protected)
 © RPTayo / SSS-MND 2026
═══════════════════════════════════════════════════════════
"""

import streamlit as st
import time, csv, io, re, uuid
from datetime import datetime, date, timedelta
from db import (
    VER, SSS_LOGO, PHT, now_pht, today_pht, today_iso, today_mmdd,
    get_branch, invalidate_branch, update_branch,
    get_categories, get_categories_with_services, get_services,
    invalidate_categories,
    get_queue_today, get_queue_by_date, get_queue_date_range,
    insert_queue_entry, update_queue_entry,
    cancel_entry, void_entry, expire_old_reserved,
    get_bqms_state, update_bqms_state, auto_update_now_serving,
    get_users, authenticate, add_user, update_user, delete_user,
    reset_password, update_password,
    add_category, update_category, delete_category, has_active_entries,
    add_service, update_service, delete_service,
    slot_counts, next_slot_num, is_duplicate, is_bqms_taken,
    validate_bqms_range, suggest_next_bqms, find_bqms_conflict_category,
    validate_mobile_ph, extract_bqms_num,
    gen_id, hash_pw,
    batch_assign_category, batch_assign_all, quick_checkin,
    get_batch_log_today,
    swap_category_order, swap_service_order,
    is_reservation_open, format_time_12h, get_logo, ICON_LIBRARY,
    OSTATUS, STATUS_LABELS, TERMINAL, FREED,
    ROLES, ROLE_LABELS, ROLE_ICONS
)

st.set_page_config(page_title="MabiliSSS Staff", page_icon="🔐", layout="centered")

st.markdown("""<style>
.sss-header{background:linear-gradient(135deg,#002E52,#0066A1);color:#fff!important;padding:18px 22px;border-radius:12px;margin-bottom:16px}
.sss-header h2{margin:0;font-size:22px;color:#fff!important}
.sss-header p{margin:4px 0 0;opacity:.75;font-size:13px;color:#fff!important}
.sss-card{background:var(--secondary-background-color,#fff);color:var(--text-color,#1a1a2e);border-radius:10px;padding:16px;margin-bottom:12px;border:1px solid rgba(128,128,128,.15)}
.sss-card strong,.sss-card b{color:var(--text-color,#1a1a2e)}
.sss-alert{border-radius:8px;padding:12px 16px;margin-bottom:12px;font-weight:600;text-align:center}
.sss-alert-red{background:rgba(220,53,69,.15);color:#ef4444;border:1px solid rgba(220,53,69,.3)}
.sss-alert-green{background:rgba(15,157,88,.12);color:#22c55e;border:1px solid rgba(15,157,88,.25)}
.sss-alert-blue{background:rgba(59,130,246,.12);color:#60a5fa;border:1px solid rgba(59,130,246,.25)}
.sss-alert-yellow{background:rgba(217,119,6,.12);color:#f59e0b;border:1px solid rgba(217,119,6,.25)}
.sss-alert strong,.sss-alert b{color:inherit}
.sss-ns-badge{display:inline-block;padding:4px 10px;border-radius:6px;font-size:13px;font-weight:800;font-family:monospace;background:rgba(34,184,207,.12);color:#22B8CF;border:1px solid rgba(34,184,207,.25)}
.stButton>button{border-radius:8px;font-weight:700}
</style>""", unsafe_allow_html=True)

# ── Auto-refresh ──
_ar_ok = False
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=15_000, limit=None, key="staff_ar")
    _ar_ok = True
except ImportError:
    pass

# ── Session state ──
for k, v in {"auth_user": None, "fail_count": 0, "lock_until": 0,
             "staff_tab": "queue"}.items():
    if k not in st.session_state:
        st.session_state[k] = v

now = now_pht()

# ═══════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════
if not st.session_state.auth_user:
    st.markdown(f"""<div class="sss-header" style="text-align:center;">
        <img src="{SSS_LOGO}" width="48"
             style="border-radius:8px;background:#fff;padding:3px;margin-bottom:8px;"
             onerror="this.style.display='none'"/>
        <h2>Staff Portal</h2>
        <p>MabiliSSS Queue · Authorized Personnel Only</p>
    </div>""", unsafe_allow_html=True)

    locked = time.time() < st.session_state.lock_until
    if locked:
        remaining = int(st.session_state.lock_until - time.time())
        st.error(f"🔒 Locked. Wait {remaining}s.")

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login", type="primary", use_container_width=True, disabled=locked):
            u = authenticate(username, password)
            if u:
                st.session_state.auth_user = u
                st.session_state.fail_count = 0
                st.session_state.session_start = time.time()
                st.rerun()
            else:
                st.session_state.fail_count += 1
                left = 3 - st.session_state.fail_count
                if left <= 0:
                    st.session_state.lock_until = time.time() + 300
                    st.session_state.fail_count = 0
                    st.error("❌ Locked for 5 minutes.")
                else:
                    st.error(f"❌ Invalid credentials. {left} attempts left.")
    st.stop()

# ═══════════════════════════════════════════════════
#  SESSION TIMEOUT (max 8h session — BUG-13 fix)
# ═══════════════════════════════════════════════════
# Auto-refresh (15s) resets inactivity timers, making them useless.
# Instead: enforce maximum session duration from login time.
if "session_start" not in st.session_state:
    st.session_state.session_start = time.time()

session_age_hrs = (time.time() - st.session_state.session_start) / 3600
if session_age_hrs > 8:
    st.session_state.auth_user = None
    st.session_state.pop("session_start", None)
    st.warning("Session expired (8-hour limit). Please login again.")
    st.rerun()
user = st.session_state.auth_user
role = user["role"]
is_th = role == "th"
is_admin_role = role in ("th",)  # Only TH gets admin — SEC-01 fix
is_ro = role in ("bh", "dh")  # Read-only observers
can_edit_queue = role in ("kiosk", "staff", "th")  # Can operate queue

# ── Auto-expire old entries on load ──
if "staff_expired_run" not in st.session_state:
    expire_old_reserved()
    st.session_state.staff_expired_run = True

# ── Load data ──
branch = get_branch()
logo_url = get_logo(branch)
cats = get_categories_with_services()
queue = get_queue_today()
bqms_state = get_bqms_state()
o_stat = branch.get("o_stat", "online")
sc = slot_counts(cats, queue)

# ═══════════════════════════════════════════════════
#  HEADER + NAV
# ═══════════════════════════════════════════════════
st.markdown(f"""<div class="sss-header">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="display:flex;align-items:center;gap:12px;">
            <img src="{SSS_LOGO}" width="38"
                 style="border-radius:8px;background:#fff;padding:2px;"
                 onerror="this.style.display='none'"/>
            <div><h2>Staff Console</h2>
                <p>{user['display_name']} · {ROLE_LABELS.get(role, role)}</p></div>
        </div>
        <div style="text-align:right;font-size:12px;opacity:.8;">
            {now.strftime('%I:%M %p')} PHT<br/>{today_pht().isoformat()}</div>
    </div></div>""", unsafe_allow_html=True)

st.caption(f"🔄 {'Auto 15s' if _ar_ok else 'Manual'} · {len(queue)} entries · oStat: {o_stat}")

# ── Navigation ──
nav = [("📋 Queue", "queue")]
if is_admin_role:
    nav.append(("👔 Admin", "admin"))
if role in ("th", "staff", "bh", "dh"):
    nav.append(("📊 Dashboard", "dash"))
nav += [("🔑 Password", "pw"), ("🚪 Logout", "logout")]

cols = st.columns(len(nav))
for i, (lbl, key) in enumerate(nav):
    with cols[i]:
        if key == "logout":
            if st.button(lbl, use_container_width=True):
                st.session_state.auth_user = None
                st.rerun()
        else:
            bt = "primary" if st.session_state.staff_tab == key else "secondary"
            if st.button(lbl, use_container_width=True, type=bt):
                st.session_state.staff_tab = key
                st.rerun()

tab = st.session_state.staff_tab

# ═══════════════════════════════════════════════════
#  PASSWORD TAB
# ═══════════════════════════════════════════════════
if tab == "pw":
    st.subheader("🔑 Change Password")
    with st.form("pw_form"):
        np1 = st.text_input("New Password", type="password")
        np2 = st.text_input("Confirm", type="password")
        if st.form_submit_button("Save", type="primary"):
            if len(np1) < 4:
                st.error("Min 4 characters.")
            elif np1 != np2:
                st.error("Passwords don't match.")
            else:
                update_password(user["id"], np1)
                st.success("✅ Password changed!")

# ═══════════════════════════════════════════════════
#  QUEUE CONSOLE
# ═══════════════════════════════════════════════════
elif tab == "queue":
    unassigned = [r for r in queue if not r.get("bqms_number")
                  and r.get("status") not in TERMINAL]

    # ── System Status (only for staff/TH) ──
    if can_edit_queue and role != "kiosk":
        st.markdown("**System Status**")
        _sopts = ["🟢 Online", "🟡 Intermittent", "🔴 Offline"]
        _smap = {"🟢 Online": "online", "🟡 Intermittent": "intermittent", "🔴 Offline": "offline"}
        _srev = {v: k for k, v in _smap.items()}
        cur_idx = _sopts.index(_srev.get(o_stat, "🟢 Online"))
        new_s = st.radio("Status:", _sopts, horizontal=True, index=cur_idx, key="sys_stat")
        new_stat = _smap[new_s]
        if new_stat != o_stat:
            update_branch(o_stat=new_stat)
            st.rerun()

    # ── Announcement (separate buttons — LOGIC-04 fix) ──
    if can_edit_queue and role != "kiosk":
        with st.expander(f"📢 Announcement {'(ACTIVE)' if branch.get('announcement', '').strip() else '(none)'}"):
            ann_text = st.text_area("Scrolling banner on member app",
                                   value=branch.get("announcement", ""), height=80,
                                   key="ann_txt")
            ac1, ac2 = st.columns([3, 1])
            with ac1:
                if st.button("📢 Post", type="primary", key="ann_post"):
                    update_branch(announcement=ann_text.strip())
                    st.success("✅ Posted!")
                    st.rerun()
            with ac2:
                if st.button("🗑️ Clear", key="ann_clear"):
                    update_branch(announcement="")
                    st.success("✅ Cleared!")
                    st.rerun()

    # ── BQMS Alert + Now Serving Inline Badges ──
    if unassigned:
        st.markdown(f'<div class="sss-alert sss-alert-red" style="font-size:16px;">🔴 <strong>{len(unassigned)} NEED BQMS#</strong></div>', unsafe_allow_html=True)

    # Now Serving per category — inline, always visible
    ns_parts = []
    for c in cats:
        ns_val = bqms_state.get(c["id"], "")
        disp = ns_val if ns_val else "—"
        ns_parts.append(f"{c['icon']} {c.get('short_label', c['label'][:8])}: <span class='sss-ns-badge'>{disp}</span>")
    if ns_parts:
        st.markdown(f"""<div class="sss-card" style="padding:10px 14px;">
            <div style="font-size:11px;opacity:.5;margin-bottom:6px;">📺 NOW SERVING</div>
            <div style="display:flex;flex-wrap:wrap;gap:10px;font-size:13px;">
                {'&nbsp;&nbsp;'.join(ns_parts)}
            </div></div>""", unsafe_allow_html=True)

    # Manual override for Now Serving (edge cases — e.g., walk-ins not in digital queue)
    if can_edit_queue and role != "kiosk":
        with st.expander("✏️ Manual Override — Now Serving"):
            st.caption("Use this only for walk-ins served outside the digital queue.")
            override_cat = st.selectbox("Category",
                                        [f"{c['icon']} {c['label']}" for c in cats],
                                        key="ns_override_cat")
            override_idx = [f"{c['icon']} {c['label']}" for c in cats].index(override_cat)
            override_c = cats[override_idx]
            cur_ns = bqms_state.get(override_c["id"], "")

            oc1, oc2 = st.columns([3, 1])
            with oc1:
                ns_new = st.text_input("BQMS #", value=cur_ns, key="ns_override_val")
            with oc2:
                st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
                if st.button("Update", key="ns_override_btn", use_container_width=True):
                    update_bqms_state(override_c["id"], ns_new.strip().upper())
                    st.rerun()

    # ═══════════════════════════════════════════════════
    #  V2.3.0 — QUICK CHECK-IN (Guard + Staff)
    # ═══════════════════════════════════════════════════
    if can_edit_queue:
        with st.expander("🔍 Quick Check-in (Online Reservations)"):
            st.caption("Search by Reservation # or mobile → one-tap arrival confirmation.")
            qc_val = st.text_input("Search Res# or Mobile", key="qc_search",
                                   placeholder="R-0228-003 or 09171234567")
            if qc_val.strip():
                qc_v = qc_val.strip()
                qc_results = []
                for r in queue:
                    if r.get("status") in TERMINAL:
                        continue
                    if r.get("source") != "ONLINE":
                        continue
                    rn = (r.get("res_num") or "").upper()
                    mob = r.get("mobile") or ""
                    mob_input = validate_mobile_ph(qc_v) or qc_v.upper()
                    if qc_v.upper() in rn or mob_input == mob or qc_v.strip() in mob:
                        qc_results.append(r)

                if not qc_results:
                    st.warning("No matching online reservations found.")
                else:
                    for qr in qc_results:
                        qr_status = qr.get("status", "")
                        qr_bqms = qr.get("bqms_number", "")
                        is_arrived = qr_status == "ARRIVED"
                        pri_icon = "⭐" if qr.get("priority") == "priority" else ""

                        # Card
                        arr_badge = ""
                        if is_arrived:
                            arr_time = qr.get("arrived_at", "")
                            if arr_time:
                                try:
                                    at = datetime.fromisoformat(arr_time)
                                    arr_badge = f' · Arrived {at.strftime("%I:%M %p")}'
                                except:
                                    arr_badge = " · Arrived"
                            else:
                                arr_badge = " · Arrived"

                        st.markdown(f"""<div class="sss-card" style="border-left:4px solid {'#22c55e' if is_arrived else '#f59e0b'};">
                            <span style="font-family:monospace;font-size:15px;font-weight:800;color:#3399CC;">{qr.get('res_num','')}</span>
                            {pri_icon}<br/>
                            <strong>{qr.get('cat_icon','')} {qr['last_name']}, {qr['first_name']} {qr.get('mi','')}</strong><br/>
                            <span style="font-size:12px;opacity:.6;">{qr.get('category','')} → {qr.get('service','')}</span>
                            {f'<br/><span style="font-size:11px;opacity:.5;">📱 {qr["mobile"]}</span>' if qr.get('mobile') else ''}
                            <br/><span style="font-size:11px;font-weight:700;color:{'#22c55e' if is_arrived else '#f59e0b'};">
                            {STATUS_LABELS.get(qr_status, qr_status)}{arr_badge}</span>
                            {f'<br/><span style="font-size:13px;font-weight:900;color:#22B8CF;">BQMS: {qr_bqms}</span>' if qr_bqms else ''}
                        </div>""", unsafe_allow_html=True)

                        if qr_status == "RESERVED" and not qr_bqms:
                            if st.button(f"✅ Confirm Arrival — {qr.get('res_num','')}",
                                         key=f"qc_{qr['id']}", type="primary",
                                         use_container_width=True):
                                quick_checkin(qr["id"])
                                st.success(f"✅ {qr.get('res_num','')} checked in!")
                                st.rerun()
                        elif is_arrived and not qr_bqms:
                            st.info(f"Already checked in. Waiting for BQMS# assignment.")
                        elif qr_bqms:
                            st.info(f"Already has BQMS# {qr_bqms}.")

    # ═══════════════════════════════════════════════════
    #  V2.3.0 — BATCH ASSIGN (Staff + TH)
    # ═══════════════════════════════════════════════════
    if can_edit_queue and role != "kiosk":
        batch_time_str = branch.get("batch_assign_time", "08:00")
        batch_logs = get_batch_log_today()
        assigned_cats = {bl["category_id"] for bl in batch_logs}

        # Count unassigned per category
        unassigned_by_cat = {}
        for cat in cats:
            cid = cat["id"]
            cnt = len([e for e in queue
                       if e.get("category_id") == cid
                       and not e.get("bqms_number")
                       and e.get("status") not in TERMINAL])
            if cnt > 0:
                unassigned_by_cat[cid] = cnt

        total_unassigned = sum(unassigned_by_cat.values())

        with st.expander(f"🎫 Batch Assign BQMS ({total_unassigned} pending · cutoff {batch_time_str})"):
            st.caption("Assign BQMS# to all checked-in and reserved members at once. "
                       "Priority: ⭐ Arrived → Regular Arrived → ⭐ Reserved → Regular Reserved.")

            # Guard cap display per category
            st.markdown("**📊 Queue Status per Category**")
            for cat in cats:
                cid = cat["id"]
                arrived_cnt = len([e for e in queue if e.get("category_id") == cid and e.get("status") == "ARRIVED" and not e.get("bqms_number")])
                reserved_cnt = len([e for e in queue if e.get("category_id") == cid and e.get("status") == "RESERVED" and not e.get("bqms_number")])
                s = sc.get(cid, {"remaining": 0, "cap": 0, "used": 0})
                was_assigned = cid in assigned_cats
                log_entry = next((bl for bl in batch_logs if bl["category_id"] == cid), None)

                badge = ""
                if was_assigned and log_entry:
                    try:
                        at = datetime.fromisoformat(log_entry["assigned_at"])
                        badge = f' · ✅ Batch done at {at.strftime("%I:%M %p")} by {log_entry["assigned_by"]} ({log_entry["assigned_count"]})'
                    except:
                        badge = f' · ✅ Batch done ({log_entry["assigned_count"]})'

                st.markdown(f"""{cat['icon']} **{cat.get('short_label', cat['label'])}** — """
                            f"""🏢 {arrived_cnt} arrived · 📱 {reserved_cnt} reserved · """
                            f"""🎫 {s['remaining']}/{s['cap']} slots left{badge}""")

            st.markdown("---")

            # Per-category batch assign buttons
            st.markdown("**Per Category**")
            for cat in cats:
                cid = cat["id"]
                was_assigned = cid in assigned_cats
                cnt = unassigned_by_cat.get(cid, 0)
                key_base = f"batch_{cid}"

                if was_assigned:
                    st.button(f"✅ {cat['icon']} {cat.get('short_label','')} — Done",
                              key=key_base, disabled=True, use_container_width=True)
                elif cnt == 0:
                    st.button(f"{cat['icon']} {cat.get('short_label','')} — 0 pending",
                              key=key_base, disabled=True, use_container_width=True)
                else:
                    # Confirmation flow
                    if st.session_state.get(f"confirm_{key_base}"):
                        st.warning(f"⚠️ Assign BQMS# to **{cnt} members** in {cat['label']}?")
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            if st.button(f"✅ Yes, Assign", key=f"y_{key_base}",
                                         type="primary", use_container_width=True):
                                fresh_q = get_queue_today()
                                n, first, last = batch_assign_category(fresh_q, cat, user["display_name"])
                                st.session_state[f"confirm_{key_base}"] = False
                                if n > 0:
                                    st.success(f"✅ Assigned {n} BQMS# ({first}–{last}) for {cat['label']}!")
                                st.rerun()
                        with bc2:
                            if st.button("← Cancel", key=f"n_{key_base}",
                                         use_container_width=True):
                                st.session_state[f"confirm_{key_base}"] = False
                                st.rerun()
                    else:
                        if st.button(f"🎫 {cat['icon']} {cat.get('short_label','')} — {cnt} pending",
                                     key=key_base, use_container_width=True):
                            st.session_state[f"confirm_{key_base}"] = True
                            st.rerun()

            # Batch Assign ALL button
            if total_unassigned > 0 and len(assigned_cats) < len(cats):
                st.markdown("---")
                all_key = "batch_all"
                if st.session_state.get(f"confirm_{all_key}"):
                    st.warning(f"⚠️ Assign BQMS# to **ALL {total_unassigned} pending members** across all categories?")
                    ba1, ba2 = st.columns(2)
                    with ba1:
                        if st.button("✅ Yes, Assign All", key=f"y_{all_key}",
                                     type="primary", use_container_width=True):
                            results = batch_assign_all(queue, cats, user["display_name"])
                            st.session_state[f"confirm_{all_key}"] = False
                            total_done = sum(r[0] for r in results.values())
                            st.success(f"✅ Batch assigned {total_done} BQMS# across {len(results)} categories!")
                            st.rerun()
                    with ba2:
                        if st.button("← Cancel", key=f"n_{all_key}",
                                     use_container_width=True):
                            st.session_state[f"confirm_{all_key}"] = False
                            st.rerun()
                else:
                    if st.button(f"🎫 Batch Assign ALL Categories ({total_unassigned} pending)",
                                 key=all_key, type="primary", use_container_width=True):
                        st.session_state[f"confirm_{all_key}"] = True
                        st.rerun()

    # ── Walk-in Registration ──
    if can_edit_queue:
        with st.expander("➕ Add Walk-in"):
            with st.form("walkin"):
                cat_labels = ["-- Select --"] + [
                    f"{c['icon']} {c['label']} ({sc.get(c['id'], {}).get('remaining', 0)} left)"
                    for c in cats]
                w_cat_i = st.selectbox("Category *", range(len(cat_labels)),
                                       format_func=lambda i: cat_labels[i])
                w_cat = cats[w_cat_i - 1] if w_cat_i > 0 else None

                # Show category description if available
                if w_cat and w_cat.get("description"):
                    st.caption(f"ℹ️ {w_cat['description']}")

                w_svc = None
                if w_cat:
                    svcs_for_cat = [s for s in get_services() if s.get("category_id") == w_cat["id"]]
                    svc_labels = ["-- None --"] + [
                        f"{s['label']}" + (f" — {s['description']}" if s.get("description") else "")
                        for s in svcs_for_cat]
                    w_svc_i = st.selectbox("Sub-service", range(len(svc_labels)),
                                           format_func=lambda i: svc_labels[i])
                    w_svc = svcs_for_cat[w_svc_i - 1] if w_svc_i > 0 else None

                wc1, wc2 = st.columns(2)
                with wc1:
                    wl = st.text_input("Last Name *", key="wl")
                with wc2:
                    wf = st.text_input("First Name *", key="wf")
                wc1, wc2 = st.columns([1, 3])
                with wc1:
                    wmi = st.text_input("M.I.", max_chars=2, key="wmi")
                with wc2:
                    wmob = st.text_input("Mobile (optional)", key="wmob")
                wpri = st.radio("Lane:", ["👤 Regular", "⭐ Priority (Senior/PWD/Pregnant)"], horizontal=True, key="wpri")
                st.caption("⭐ Priority = Senior Citizen, PWD, or Pregnant. Ask for valid ID/proof before selecting.")

                wbqms = ""
                if role != "kiosk" and w_cat:
                    suggested = suggest_next_bqms(queue, w_cat) if w_cat else ""
                    rs = w_cat.get("bqms_range_start")
                    re_ = w_cat.get("bqms_range_end")
                    hint = f"Series: {rs}–{re_}" if rs and re_ else "Enter BQMS #"
                    wbqms = st.text_input(f"BQMS # ({hint})",
                                          value=suggested,
                                          key="wbqms")

                if st.form_submit_button("Register Walk-in", type="primary",
                                          use_container_width=True):
                    wlu = wl.strip().upper()
                    wfu = wf.strip().upper()
                    wmu_raw = wmob.strip()
                    wmu_clean = validate_mobile_ph(wmu_raw) if wmu_raw else ""
                    errs = []
                    if not w_cat:
                        errs.append("Select category.")
                    if not wlu:
                        errs.append("Last Name required.")
                    if not wfu:
                        errs.append("First Name required.")
                    if wmu_raw and not wmu_clean:
                        errs.append("Invalid mobile format (09XX, 11 digits).")

                    if not errs:
                        fresh_q = get_queue_today()
                        fsc = slot_counts(cats, fresh_q)
                        bv_check = wbqms.strip().upper() if wbqms else ""

                        if is_duplicate(fresh_q, wlu, wfu, wmu_clean):
                            errs.append("Duplicate entry for this person today.")
                        if fsc.get(w_cat["id"], {}).get("remaining", 0) <= 0:
                            errs.append(f"Daily cap reached for {w_cat['label']}.")
                        if bv_check:
                            if is_bqms_taken(fresh_q, bv_check):
                                errs.append(f"BQMS {bv_check} already assigned!")
                            ok, msg = validate_bqms_range(bv_check, w_cat)
                            if not ok:
                                errs.append(f"BQMS range warning: {msg}")
                            conflict = find_bqms_conflict_category(bv_check, cats, w_cat["id"])
                            if conflict:
                                errs.append(f"⚠️ {bv_check} falls in {conflict['label']} series. Assign anyway via override.")

                    if errs:
                        for e in errs:
                            st.error(f"❌ {e}")
                    else:
                        slot = next_slot_num(fresh_q)
                        rn = f"K-{today_mmdd()}-{slot:03d}"
                        svc_lbl = w_svc["label"] if w_svc else "Walk-in"
                        svc_id = w_svc["id"] if w_svc else "walkin"
                        ts = now_pht().isoformat()
                        entry = {
                            "id": gen_id(), "queue_date": today_iso(),
                            "slot": slot, "res_num": rn,
                            "last_name": wlu, "first_name": wfu,
                            "mi": wmi.strip().upper(),
                            "mobile": wmu_clean or None,
                            "service": svc_lbl, "service_id": svc_id,
                            "category": w_cat["label"], "category_id": w_cat["id"],
                            "cat_icon": w_cat["icon"],
                            "priority": "priority" if "Priority" in wpri else "regular",
                            "status": "ARRIVED" if bv_check else "RESERVED",
                            "bqms_number": bv_check or None,
                            "source": "KIOSK",
                            "issued_at": ts,
                            "arrived_at": ts if bv_check else None,
                        }
                        insert_queue_entry(entry)
                        st.success(f"✅ **{rn}** registered! Share this with the member.")
                        st.rerun()

    # ═══════════════════════════════════════════════════
    #  QUEUE LIST
    # ═══════════════════════════════════════════════════
    st.markdown("---")
    _fm = {
        "🔴 Need BQMS": "UNASSIGNED",
        "All": "all",
        "🏢 Kiosk": "KIOSK",
        "📱 Online": "ONLINE",
        "✅ Arrived": "ARRIVED",
        "🔵 Serving": "SERVING",
        "✔ Done": "COMPLETED",
        "🚫 Cancelled": "CANCELLED",
    }
    sel_f = st.radio("Filter:", list(_fm.keys()), horizontal=True, index=0)
    qf = _fm[sel_f]
    search = st.text_input("🔍 Search", key="qsearch")

    # Sort: unassigned first, then by issued_at
    sorted_q = sorted(queue, key=lambda r: (
        0 if (not r.get("bqms_number") and r.get("status") not in TERMINAL) else 1,
        r.get("issued_at", "")
    ))
    filt = sorted_q

    if qf == "UNASSIGNED":
        filt = [r for r in filt if not r.get("bqms_number") and r.get("status") not in TERMINAL]
    elif qf == "KIOSK":
        filt = [r for r in filt if r.get("source") == "KIOSK"]
    elif qf == "ONLINE":
        filt = [r for r in filt if r.get("source") == "ONLINE"]
    elif qf != "all":
        filt = [r for r in filt if r.get("status") == qf]

    if search:
        sl = search.strip().lower()
        filt = [r for r in filt
                if sl in r.get("last_name", "").lower()
                or sl in r.get("first_name", "").lower()
                or sl in (r.get("bqms_number", "") or "").lower()
                or sl in (r.get("res_num", "") or "").lower()]

    st.caption(f"Showing {len(filt)} of {len(queue)} entries")

    if not filt:
        if qf == "UNASSIGNED":
            st.success("✅ All entries have BQMS#!")
        else:
            st.info("No entries match this filter.")
    else:
        for r in filt:
            status = r.get("status", "")
            needs_b = not r.get("bqms_number") and status not in TERMINAL
            bdr = "#ef4444" if needs_b else "rgba(128,128,128,.15)"
            src = "🏢" if r.get("source") == "KIOSK" else "📱"
            pri = "⭐" if r.get("priority") == "priority" else ""
            bqms_h = ""
            if r.get("bqms_number"):
                # Range check indicator
                cat_obj = next((c for c in cats if c["id"] == r.get("category_id")), None)
                range_ok = True
                if cat_obj:
                    ok, _ = validate_bqms_range(r["bqms_number"], cat_obj)
                    range_ok = ok
                range_icon = "✓" if range_ok else "⚠️"
                bqms_h = f'<div style="font-family:monospace;font-size:20px;font-weight:900;color:#22B8CF;margin-top:4px;">BQMS: {r["bqms_number"]} <span style="font-size:12px;">{range_icon}</span></div>'

            # Show void reason if voided
            void_note = ""
            if status == "VOID" and r.get("void_reason"):
                void_note = f'<br/><span style="font-size:11px;color:#f59e0b;">Void: {r["void_reason"]}</span>'

            st.markdown(f"""<div class="sss-card" style="border-left:4px solid {bdr};">
                <span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;
                    background:rgba(51,153,204,.15);color:#3399CC;float:right;">
                    {STATUS_LABELS.get(status, status)}</span>
                <span style="font-family:monospace;font-size:15px;font-weight:800;color:#3399CC;">{r.get('res_num','')}</span>
                <span style="font-size:11px;opacity:.5;margin-left:6px;">{src}</span>{pri}<br/>
                <strong>{r.get('cat_icon','')} {r['last_name']}, {r['first_name']} {r.get('mi','')}</strong><br/>
                <span style="font-size:12px;opacity:.6;">{r.get('category','')} → {r.get('service','')}</span>
                {f'<br/><span style="font-size:11px;opacity:.5;">📱 {r["mobile"]}</span>' if r.get('mobile') else ''}{void_note}
                {bqms_h}
            </div>""", unsafe_allow_html=True)

            # ── ACTION BUTTONS (only for queue operators) ──
            if can_edit_queue:
                rid = r["id"]
                cat_obj = next((c for c in cats if c["id"] == r.get("category_id")), None)

                # ── NEEDS BQMS ASSIGNMENT ──
                if needs_b:
                    suggested = suggest_next_bqms(queue, cat_obj) if cat_obj else ""
                    rs = cat_obj.get("bqms_range_start") if cat_obj else None
                    re_ = cat_obj.get("bqms_range_end") if cat_obj else None
                    hint = f"Series: {rs}–{re_}" if rs and re_ else "e.g., 2005"

                    st.markdown(f"""<div style="background:rgba(220,53,69,.08);border:1px solid rgba(220,53,69,.25);
                        border-radius:8px;padding:10px 14px;margin-bottom:8px;">
                        <span style="font-size:12px;font-weight:700;color:#ef4444;">
                        🎫 Assign BQMS for {r.get('res_num','')} — {hint}</span></div>""", unsafe_allow_html=True)

                    ac1, ac2 = st.columns([3, 1])
                    with ac1:
                        bv = st.text_input("BQMS#", value=suggested,
                                           key=f"a_{rid}", placeholder=hint)
                    with ac2:
                        st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
                        if st.button("🎫 Assign", key=f"ba_{rid}", type="primary",
                                     use_container_width=True):
                            bv_clean = bv.strip().upper() if bv else ""
                            if not bv_clean:
                                st.warning("Enter BQMS# first.")
                            else:
                                fresh_q = get_queue_today()
                                assign_err = None
                                if is_bqms_taken(fresh_q, bv_clean):
                                    assign_err = f"BQMS {bv_clean} is already assigned!"
                                if cat_obj and not assign_err:
                                    ok, msg = validate_bqms_range(bv_clean, cat_obj)
                                    if not ok:
                                        assign_err = f"Range warning: {msg}"
                                if assign_err:
                                    st.error(f"❌ {assign_err}")
                                else:
                                    ts = now_pht().isoformat()
                                    update_queue_entry(rid,
                                                       bqms_number=bv_clean,
                                                       status="ARRIVED",
                                                       arrived_at=ts)
                                    st.rerun()

                # ── ARRIVED → Serving / Complete / Void ──
                elif status == "ARRIVED":
                    # V2.3.0: Priority verification reminder
                    if r.get("priority") == "priority":
                        st.markdown(f"""<div style="background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
                            border-radius:6px;padding:6px 10px;margin-bottom:6px;font-size:11px;">
                            ⭐ <b>Priority Lane</b> — Please verify: Senior Citizen ID, PWD ID, or proof of pregnancy.</div>""",
                            unsafe_allow_html=True)
                    ac1, ac2, ac3 = st.columns(3)
                    with ac1:
                        if st.button("🔵 Serving", key=f"srv_{rid}", use_container_width=True):
                            ts = now_pht().isoformat()
                            update_queue_entry(rid, status="SERVING", serving_at=ts)
                            auto_update_now_serving(r)  # AUTO-UPDATE Now Serving
                            st.rerun()
                    with ac2:
                        if st.button("✅ Complete", key=f"dn_{rid}", use_container_width=True):
                            ts = now_pht().isoformat()
                            update_queue_entry(rid, status="COMPLETED", completed_at=ts)
                            auto_update_now_serving(r)  # AUTO-UPDATE Now Serving
                            st.rerun()
                    with ac3:
                        if is_th and st.button("⚙️ Void", key=f"vo_{rid}", use_container_width=True):
                            st.session_state[f"void_{rid}"] = True
                            st.rerun()

                # ── SERVING → Complete ──
                elif status == "SERVING":
                    if st.button("✅ Complete", key=f"dn2_{rid}", type="primary",
                                 use_container_width=True):
                        ts = now_pht().isoformat()
                        update_queue_entry(rid, status="COMPLETED", completed_at=ts)
                        auto_update_now_serving(r)
                        st.rerun()

                # ── RESERVED (no BQMS yet, not arrived) → Void (TH only) ──
                elif status == "RESERVED" and not needs_b:
                    # This case shouldn't normally happen (RESERVED = needs BQMS)
                    # But just in case, allow void
                    if is_th:
                        if st.button("⚙️ Void", key=f"vo2_{rid}", use_container_width=True):
                            st.session_state[f"void_{rid}"] = True
                            st.rerun()

                # ── VOID REASON DIALOG ──
                if st.session_state.get(f"void_{rid}"):
                    st.warning(f"⚠️ Void {r.get('res_num', '')}? This frees the slot.")
                    vr = st.text_input("Reason (required for audit) *",
                                       key=f"vr_{rid}",
                                       placeholder="e.g., Test entry, Duplicate, Member requested by phone")
                    vc1, vc2 = st.columns(2)
                    with vc1:
                        if st.button("✅ Confirm Void", key=f"vconf_{rid}",
                                     type="primary", use_container_width=True):
                            if not vr.strip():
                                st.error("Reason required.")
                            else:
                                void_entry(rid, vr.strip(), user["display_name"])
                                st.session_state[f"void_{rid}"] = False
                                st.rerun()
                    with vc2:
                        if st.button("← Cancel", key=f"vcanc_{rid}",
                                     use_container_width=True):
                            st.session_state[f"void_{rid}"] = False
                            st.rerun()

                # ── BQMS EDIT (for assigned entries that aren't terminal) ──
                if r.get("bqms_number") and status not in TERMINAL and role != "kiosk":
                    if st.session_state.get(f"edit_bqms_{rid}"):
                        ec1, ec2, ec3 = st.columns([3, 1, 1])
                        with ec1:
                            new_bqms = st.text_input("New BQMS#",
                                                     value=r["bqms_number"],
                                                     key=f"eb_{rid}")
                        with ec2:
                            if st.button("💾", key=f"ebs_{rid}", use_container_width=True):
                                nb = new_bqms.strip().upper()
                                if not nb:
                                    st.error("Cannot be empty.")
                                else:
                                    fresh_q = get_queue_today()
                                    if is_bqms_taken(fresh_q, nb, exclude_id=rid):
                                        st.error(f"BQMS {nb} already taken!")
                                    else:
                                        if cat_obj:
                                            ok, msg = validate_bqms_range(nb, cat_obj)
                                            if not ok:
                                                st.warning(f"⚠️ {msg}")
                                        update_queue_entry(rid,
                                                           bqms_number=nb,
                                                           bqms_prev=r["bqms_number"])
                                        # Update Now Serving if this entry is being served
                                        if status == "SERVING":
                                            update_bqms_state(r.get("category_id", ""), nb)
                                        st.session_state[f"edit_bqms_{rid}"] = False
                                        st.rerun()
                        with ec3:
                            if st.button("✖", key=f"ebc_{rid}", use_container_width=True):
                                st.session_state[f"edit_bqms_{rid}"] = False
                                st.rerun()
                    else:
                        if st.button("✏️ Edit BQMS#", key=f"ebe_{rid}",
                                     use_container_width=True):
                            st.session_state[f"edit_bqms_{rid}"] = True
                            st.rerun()

            st.markdown("")  # Spacer

    st.markdown("---")
    if st.button("🔄 Refresh Queue", use_container_width=True):
        st.rerun()

# ═══════════════════════════════════════════════════
#  ADMIN TAB (TH ONLY — SEC-01 fix)
# ═══════════════════════════════════════════════════
elif tab == "admin" and is_admin_role:
    st.subheader("👔 Admin Panel")
    atabs = st.tabs(["📋 Categories", "🔧 Sub-Categories", "📊 Daily Caps",
                     "👥 Users", "🏢 Branch"])

    # ══════════ CATEGORIES (Full CRUD + BQMS Series + Grouping) ══════════
    with atabs[0]:
        st.markdown("**Manage BQMS Categories**")
        st.caption("Main transaction categories shown to members. Configure BQMS series, lane grouping, and descriptions.")

        for i, cat in enumerate(cats):
            rs = cat.get("bqms_range_start", "")
            re_ = cat.get("bqms_range_end", "")
            pfx = cat.get("bqms_prefix", "")
            range_txt = f" · Series: {pfx}{rs}–{pfx}{re_}" if rs and re_ else " · No series set"
            with st.expander(f"{cat['icon']} {cat['label']} — Cap: {cat['cap']}{range_txt}"):
                # ── Reorder buttons (outside form) ──
                mc1, mc2, mc3 = st.columns([1, 1, 6])
                with mc1:
                    if i > 0:
                        if st.button("⬆️ Up", key=f"cup_{cat['id']}", use_container_width=True):
                            swap_category_order(cat["id"], cats[i - 1]["id"])
                            st.success("✅ Moved up!")
                            st.rerun()
                with mc2:
                    if i < len(cats) - 1:
                        if st.button("⬇️ Down", key=f"cdn_{cat['id']}", use_container_width=True):
                            swap_category_order(cat["id"], cats[i + 1]["id"])
                            st.success("✅ Moved down!")
                            st.rerun()

                # ── Edit form ──
                with st.form(f"edit_cat_{cat['id']}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        new_label = st.text_input("Label", value=cat["label"], key=f"cl_{cat['id']}")
                        # Icon picker from library
                        icon_vals = [ic[0] for ic in ICON_LIBRARY]
                        icon_labels = [f"{ic[0]} {ic[1]}" for ic in ICON_LIBRARY]
                        cur_icon_idx = icon_vals.index(cat["icon"]) if cat["icon"] in icon_vals else 0
                        new_icon = st.selectbox("Icon", range(len(ICON_LIBRARY)), index=cur_icon_idx,
                                                format_func=lambda i: icon_labels[i],
                                                key=f"ci_{cat['id']}")
                        new_icon = icon_vals[new_icon]
                        new_short = st.text_input("Short Label", value=cat.get("short_label", ""), key=f"cs_{cat['id']}")
                    with ec2:
                        new_avg = st.number_input("Avg Time (min)", value=cat["avg_time"], min_value=1, key=f"ca_{cat['id']}")
                        new_order = st.number_input("Sort Order", value=cat.get("sort_order", 0), min_value=0, key=f"co_{cat['id']}")

                    new_desc = st.text_input("Description (shown to members & staff)",
                                             value=cat.get("description", "") or "",
                                             key=f"cd_{cat['id']}",
                                             placeholder="e.g., For retirement, death, and funeral benefit claims",
                                             max_chars=150)

                    st.markdown("**BQMS Number Series**")
                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        new_pfx = st.text_input("Prefix", value=pfx, key=f"cp_{cat['id']}", placeholder="e.g., L-")
                    with bc2:
                        new_rs = st.number_input("Range Start", value=rs if rs else 0, min_value=0, key=f"crs_{cat['id']}")
                    with bc3:
                        new_re = st.number_input("Range End", value=re_ if re_ else 0, min_value=0, key=f"cre_{cat['id']}")

                    if st.form_submit_button("💾 Save Category", type="primary"):
                        upd = {
                            "label": new_label.strip(), "icon": new_icon.strip(),
                            "short_label": new_short.strip(), "avg_time": new_avg,
                            "sort_order": new_order, "description": new_desc.strip(),
                            "bqms_prefix": new_pfx.strip(),
                            "bqms_range_start": new_rs if new_rs > 0 else None,
                            "bqms_range_end": new_re if new_re > 0 else None,
                        }
                        if new_rs > 0 and new_re > 0 and new_rs >= new_re:
                            st.error("Range Start must be less than Range End.")
                        else:
                            update_category(cat["id"], **upd)
                            st.success("✅ Category saved!")
                            st.rerun()

                # Delete (outside form)
                if has_active_entries(cat["id"]):
                    st.warning("⚠️ Cannot delete — active queue entries exist today.")
                else:
                    if st.button(f"🗑️ Delete {cat['label']}", key=f"del_{cat['id']}"):
                        delete_category(cat["id"])
                        st.success(f"✅ Deleted {cat['label']}")
                        st.rerun()

        st.markdown("---")
        st.markdown("**➕ Add New Category**")
        with st.form("add_cat"):
            ac1, ac2 = st.columns(2)
            with ac1:
                nc_id = st.text_input("Category ID (unique, lowercase)", placeholder="e.g., loans_regular")
                nc_label = st.text_input("Full Label", placeholder="e.g., Loans - Regular Lane")
                # Icon picker from library
                nc_icon_idx = st.selectbox("Icon", range(len(ICON_LIBRARY)),
                                           format_func=lambda i: f"{ICON_LIBRARY[i][0]} {ICON_LIBRARY[i][1]}",
                                           key="nc_icon_sel")
                nc_icon = ICON_LIBRARY[nc_icon_idx][0]
            with ac2:
                nc_short = st.text_input("Short Label", placeholder="e.g., Loans-Reg")
                nc_avg = st.number_input("Avg Service Time (min)", value=10, min_value=1)
                nc_cap = st.number_input("Daily Cap", value=50, min_value=1)
            nc_order = st.number_input("Sort Order", value=len(cats) + 1, min_value=0)
            nc_desc = st.text_input("Description", placeholder="Short note for members & staff", max_chars=150)

            st.markdown("**BQMS Series**")
            nbc1, nbc2, nbc3 = st.columns(3)
            with nbc1:
                nc_pfx = st.text_input("Prefix", value="", placeholder="optional")
            with nbc2:
                nc_rs = st.number_input("Range Start", value=0, min_value=0, key="nc_rs")
            with nbc3:
                nc_re = st.number_input("Range End", value=0, min_value=0, key="nc_re")

            if st.form_submit_button("➕ Add Category", type="primary"):
                nid = nc_id.strip().lower().replace(" ", "_")
                if not nid or not nc_label.strip():
                    st.error("ID and Label required.")
                elif any(c["id"] == nid for c in cats):
                    st.error(f"ID '{nid}' already exists.")
                elif nc_rs > 0 and nc_re > 0 and nc_rs >= nc_re:
                    st.error("Range Start must be less than Range End.")
                else:
                    add_category(nid, nc_label.strip(), nc_icon.strip(),
                                 nc_short.strip(), nc_avg, nc_cap, nc_order,
                                 nc_pfx.strip(),
                                 nc_rs if nc_rs > 0 else None,
                                 nc_re if nc_re > 0 else None,
                                 description=nc_desc.strip())
                    st.success(f"✅ Added {nc_label.strip()}!")
                    st.rerun()

    # ══════════ SUB-CATEGORIES ══════════
    with atabs[1]:
        st.markdown("**Manage Sub-Categories / Services**")
        st.caption("Specific services under each category. Courtesy Lanes automatically inherit subcategories from their paired Regular Lane.")

        all_svcs = get_services()
        for cat in cats:
            st.markdown(f"### {cat['icon']} {cat['label']}")
            svcs = [s for s in all_svcs if s.get("category_id") == cat["id"]]
            svcs.sort(key=lambda s: s.get("sort_order", 0))

            if not svcs:
                st.caption("No sub-categories yet.")
            for j, svc in enumerate(svcs):
                sc1, sc2, sc3, sc4, sc5 = st.columns([3, 2, 0.5, 0.5, 0.5])
                with sc1:
                    new_slabel = st.text_input("Label", value=svc["label"],
                                               key=f"sl_{svc['id']}",
                                               label_visibility="collapsed")
                with sc2:
                    new_sdesc = st.text_input("Desc", value=svc.get("description", "") or "",
                                              key=f"sdsc_{svc['id']}",
                                              label_visibility="collapsed",
                                              placeholder="Short description")
                with sc3:
                    if st.button("💾", key=f"ss_{svc['id']}", help="Save"):
                        upd = {"label": new_slabel.strip()}
                        upd["description"] = new_sdesc.strip()
                        if new_slabel.strip():
                            update_service(svc["id"], **upd)
                            st.toast("✅ Saved!")
                            st.rerun()
                with sc4:
                    # Reorder: swap with previous
                    if j > 0:
                        if st.button("⬆", key=f"sup_{svc['id']}", help="Move up"):
                            swap_service_order(svc["id"], svcs[j - 1]["id"])
                            st.toast("✅ Moved!")
                            st.rerun()
                    else:
                        st.write("")
                with sc5:
                    if st.button("🗑️", key=f"sd_{svc['id']}", help="Delete"):
                        delete_service(svc["id"])
                        st.toast("✅ Deleted!")
                        st.rerun()

            with st.form(f"add_svc_{cat['id']}"):
                ns1, ns2, ns3 = st.columns([3, 2, 1])
                with ns1:
                    new_svc_label = st.text_input("New sub-category",
                                                  placeholder="e.g., Calamity Loan",
                                                  key=f"nsv_{cat['id']}")
                with ns2:
                    new_svc_desc = st.text_input("Description",
                                                 placeholder="Short note",
                                                 key=f"nsvd_{cat['id']}")
                with ns3:
                    if st.form_submit_button("➕ Add"):
                        label = new_svc_label.strip()
                        if label:
                            sid = f"{cat['id']}_{uuid.uuid4().hex[:8]}"
                            add_service(sid, cat["id"], label, len(svcs) + 1,
                                        description=new_svc_desc.strip())
                            st.toast("✅ Added!")
                            st.rerun()
            st.markdown("---")

    # ══════════ DAILY CAPS ══════════
    with atabs[2]:
        st.markdown("**📊 Daily Caps — Slots per Category**")
        st.caption("Set maximum members per category for the WHOLE DAY. Served = still counted. Only Cancel/Void frees a slot.")

        for cat in cats:
            s = sc.get(cat["id"], {"used": 0, "cap": 50, "remaining": 50})
            st.markdown(f"**{cat['icon']} {cat['label']}** — Used: {s['used']} / Cap: {s['cap']} · Remaining: **{s['remaining']}**")

            with st.form(f"cap_{cat['id']}"):
                new_cap = st.number_input(
                    f"Daily cap",
                    value=s["cap"], min_value=1, max_value=999,
                    key=f"capv_{cat['id']}")
                if st.form_submit_button("💾 Save", use_container_width=True):
                    if new_cap != s["cap"]:
                        update_category(cat["id"], cap=new_cap)
                        st.success(f"✅ {cat['label']} cap → {new_cap}")
                        st.rerun()

            pct = (s["used"] / s["cap"] * 100) if s["cap"] > 0 else 0
            bar_color = "#22c55e" if pct < 70 else "#f59e0b" if pct < 90 else "#ef4444"
            st.markdown(f"""<div style="margin-bottom:12px;">
                <div style="background:rgba(128,128,128,.1);border-radius:4px;height:8px;overflow:hidden;">
                    <div style="background:{bar_color};width:{min(pct,100):.0f}%;height:100%;border-radius:4px;"></div>
                </div></div>""", unsafe_allow_html=True)

    # ══════════ USERS (Full CRUD) ══════════
    with atabs[3]:
        st.markdown("**👥 Staff Users Management**")
        st.caption("Add, edit, deactivate staff accounts, and reset passwords.")

        users = get_users()
        for u in users:
            rl = ROLE_LABELS.get(u["role"], u["role"])
            active = u.get("active", True)
            icon = ROLE_ICONS.get(u["role"], "👤")
            status_dot = "🟢" if active else "🔴 Inactive"

            with st.expander(f"{icon} {u['display_name']} — {rl} · `{u['username']}` · {status_dot}"):
                with st.form(f"edit_user_{u['id']}"):
                    uc1, uc2 = st.columns(2)
                    with uc1:
                        u_name = st.text_input("Display Name", value=u["display_name"],
                                               key=f"un_{u['id']}")
                        u_uname = st.text_input("Username", value=u["username"],
                                                key=f"uu_{u['id']}")
                    with uc2:
                        role_opts = list(ROLE_LABELS.keys())
                        role_idx = role_opts.index(u["role"]) if u["role"] in role_opts else 0
                        u_role = st.selectbox("Role", role_opts,
                                              format_func=lambda x: ROLE_LABELS.get(x, x),
                                              index=role_idx, key=f"ur_{u['id']}")
                        u_active = st.checkbox("Active", value=active, key=f"ua_{u['id']}")

                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        update_user(u["id"],
                                    display_name=u_name.strip(),
                                    username=u_uname.strip().lower(),
                                    role=u_role,
                                    active=u_active)
                        st.success(f"✅ Updated {u_name.strip()}")
                        st.rerun()

                # Reset password — outside form
                st.markdown("**🔑 Reset Password**")
                rp1, rp2 = st.columns([3, 1])
                with rp1:
                    new_pw = st.text_input("New password", type="password",
                                           key=f"rp_{u['id']}")
                with rp2:
                    st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
                    if st.button("🔑 Reset", key=f"rpb_{u['id']}",
                                 use_container_width=True):
                        if not new_pw or len(new_pw) < 4:
                            st.error("Min 4 characters.")
                        else:
                            reset_password(u["id"], new_pw)
                            st.success(f"✅ Password reset for {u['display_name']}")

                # Delete — outside form, with confirmation
                if u["id"] != user["id"]:  # Can't delete yourself
                    if st.button(f"🗑️ Delete Account", key=f"du_{u['id']}"):
                        delete_user(u["id"])
                        st.success(f"✅ Deleted {u['display_name']}")
                        st.rerun()

        st.markdown("---")
        st.markdown("**➕ Add New Staff User**")
        with st.form("add_user"):
            nu1, nu2 = st.columns(2)
            with nu1:
                new_uname = st.text_input("Username *", placeholder="e.g., jdcruz")
                new_dname = st.text_input("Display Name *", placeholder="e.g., Juan Dela Cruz")
            with nu2:
                new_urole = st.selectbox("Role *", list(ROLE_LABELS.keys()),
                                         format_func=lambda x: ROLE_LABELS.get(x, x))
                new_upw = st.text_input("Initial Password *", type="password",
                                        placeholder="Min 4 characters")

            if st.form_submit_button("➕ Add User", type="primary"):
                errs = []
                nu = new_uname.strip().lower()
                nd = new_dname.strip()
                if not nu:
                    errs.append("Username required.")
                if not nd:
                    errs.append("Display Name required.")
                if not new_upw or len(new_upw) < 4:
                    errs.append("Password: min 4 characters.")
                if any(u["username"].lower() == nu for u in users):
                    errs.append(f"Username '{nu}' already exists.")
                if errs:
                    for e in errs:
                        st.error(f"❌ {e}")
                else:
                    uid = f"user_{gen_id()}"
                    add_user(uid, nu, nd, new_urole, new_upw)
                    st.success(f"✅ Added {nd}!")
                    st.rerun()

    # ══════════ BRANCH ══════════
    with atabs[4]:
        st.markdown("**🏢 Branch Configuration**")

        # ── Basic Info ──
        with st.form("branch_basic"):
            st.markdown("**Branch Info**")
            bn = st.text_input("Branch Name", value=branch.get("name", ""))
            ba = st.text_input("Address", value=branch.get("address", ""))
            bh = st.text_input("Operating Hours (display)", value=branch.get("hours", ""),
                               help="Shown on member portal header. e.g., Mon-Fri 8AM-5PM")

            st.markdown("**🖼️ Branch Logo**")
            st.caption("Paste a direct image URL (PNG/JPG). Use a publicly accessible link — e.g., from Google Drive (set to 'Anyone with link'), Imgur, or any hosted image. Leave empty for default SSS logo.")
            cur_logo = branch.get("logo_url", "") or ""
            new_logo = st.text_input("Logo URL", value=cur_logo,
                                     placeholder="https://drive.google.com/... or https://i.imgur.com/...")
            if new_logo.strip():
                st.image(new_logo.strip(), width=64, caption="Preview")

            if st.form_submit_button("💾 Save Branch Info", type="primary"):
                update_branch(name=bn, address=ba, hours=bh, logo_url=new_logo.strip())
                st.success("✅ Branch info saved!")
                st.rerun()

        st.markdown("---")

        # ── Queue Operations Config ──
        with st.form("branch_ops"):
            st.markdown("**⏰ Queue Operations Config**")

            # Batch assign time
            bt_val = branch.get("batch_assign_time", "08:00")
            bt = st.text_input("Batch Assign Time (HH:MM, 24h)", value=bt_val,
                               help="When staff runs batch BQMS assignment. Default: 08:00")

            # Priority lane mode
            plm_opts = ["integrated", "separate"]
            plm_val = branch.get("priority_lane_mode", "integrated")
            plm_idx = plm_opts.index(plm_val) if plm_val in plm_opts else 0
            plm = st.selectbox("Priority Lane Mode (for single-lane categories only)", plm_opts, index=plm_idx,
                               format_func=lambda x: "Integrated — priority gets lower # in same queue (default)" if x == "integrated"
                                   else "Separate — no priority radio shown",
                               help="Integrated: members can self-select Priority via radio button → priority gets lower BQMS# in same series.\n\n"
                                    "Separate: hides the priority radio.")

            if st.form_submit_button("💾 Save Queue Config", type="primary"):
                import re as re_mod
                if not re_mod.match(r'^\d{2}:\d{2}$', bt.strip()):
                    st.error("Batch time must be HH:MM format (e.g., 08:00, 08:15).")
                else:
                    update_branch(batch_assign_time=bt.strip(), priority_lane_mode=plm)
                    st.success("✅ Queue config saved!")
                    st.rerun()

        st.markdown("---")

        # ── Reservation Hours ──
        with st.form("branch_res_hours"):
            st.markdown("**🕐 Online Reservation Hours**")
            st.caption("Members can only make online reservations within this time window. Walk-ins at the branch are always accepted during operating hours.")

            rh1, rh2 = st.columns(2)
            with rh1:
                rot = branch.get("reservation_open_time", "06:00") or "06:00"
                res_open = st.text_input("Opening Time (HH:MM, 24h)", value=rot,
                                         help="When online reservations open. Default: 06:00")
            with rh2:
                rct = branch.get("reservation_close_time", "17:00") or "17:00"
                res_close = st.text_input("Closing Time (HH:MM, 24h)", value=rct,
                                          help="When online reservations close. Default: 17:00")

            if st.form_submit_button("💾 Save Reservation Hours", type="primary"):
                import re as re_mod
                ok = True
                for tv, tn in [(res_open, "Opening"), (res_close, "Closing")]:
                    if not re_mod.match(r'^\d{2}:\d{2}$', tv.strip()):
                        st.error(f"{tn} time must be HH:MM format.")
                        ok = False
                if ok:
                    update_branch(reservation_open_time=res_open.strip(),
                                  reservation_close_time=res_close.strip())
                    st.success(f"✅ Reservations: {format_time_12h(res_open.strip())} – {format_time_12h(res_close.strip())}")
                    st.rerun()

        st.markdown("---")

        # ── Working Days + Holidays ──
        with st.form("branch_schedule"):
            st.markdown("**📅 Working Days & Holidays**")
            st.caption("Set which days the branch operates. Online reservations are blocked on non-working days and holidays.")

            all_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            current_wd = [d.strip() for d in (branch.get("working_days", "Mon,Tue,Wed,Thu,Fri") or "Mon,Tue,Wed,Thu,Fri").split(",") if d.strip()]

            wd_cols = st.columns(7)
            selected_days = []
            for idx_d, day in enumerate(all_days):
                with wd_cols[idx_d]:
                    if st.checkbox(day, value=(day in current_wd), key=f"wd_{day}"):
                        selected_days.append(day)

            st.markdown("**Holidays** (blocked dates)")
            st.caption("Enter holiday dates, one per line (YYYY-MM-DD). Members cannot make online reservations on these dates.")
            current_hol = branch.get("holidays", "") or ""
            # Convert comma-separated to newline for display
            hol_display = current_hol.replace(",", "\n").strip()
            holidays_input = st.text_area("Holiday Dates", value=hol_display,
                                          placeholder="2026-01-01\n2026-04-09\n2026-06-12",
                                          height=120)

            if st.form_submit_button("💾 Save Schedule", type="primary"):
                wd_str = ",".join(selected_days) if selected_days else "Mon,Tue,Wed,Thu,Fri"
                # Parse holidays: accept newlines or commas
                hol_lines = [h.strip() for h in holidays_input.replace("\n", ",").split(",") if h.strip()]
                import re as re_mod
                valid_hol = []
                bad_hol = []
                for h in hol_lines:
                    if re_mod.match(r'^\d{4}-\d{2}-\d{2}$', h):
                        valid_hol.append(h)
                    else:
                        bad_hol.append(h)
                if bad_hol:
                    st.error(f"Invalid date format: {', '.join(bad_hol)}. Use YYYY-MM-DD.")
                else:
                    hol_str = ",".join(sorted(set(valid_hol)))
                    update_branch(working_days=wd_str, holidays=hol_str)
                    st.success(f"✅ Schedule saved! Working: {wd_str} · Holidays: {len(valid_hol)}")
                    st.rerun()

        st.markdown("---")

        # ── Test Mode ──
        st.markdown("**🧪 Test / Mock Mode**")
        st.caption("When ON, bypasses reservation time + day restrictions. Use for testing outside operating hours.")
        test_on = branch.get("test_mode", False)
        test_label = "🧪 **TEST MODE: ON** — All time/day restrictions bypassed" if test_on else "Test mode is OFF"
        st.markdown(test_label)

        if test_on:
            if st.button("⏹️ Turn OFF Test Mode", type="secondary", use_container_width=True):
                update_branch(test_mode=False)
                st.success("✅ Test mode disabled. Normal schedule active.")
                st.rerun()
        else:
            if st.button("🧪 Turn ON Test Mode", type="primary", use_container_width=True):
                update_branch(test_mode=True)
                st.success("✅ Test mode enabled! Reservations open regardless of time/day.")
                st.rerun()

# ═══════════════════════════════════════════════════
#  DASHBOARD TAB
# ═══════════════════════════════════════════════════
elif tab == "dash" and role in ("th", "staff", "bh", "dh"):
    st.subheader("📊 Dashboard")

    st.markdown("**📅 Select Date Range**")
    dc1, dc2 = st.columns(2)
    with dc1:
        d_start = st.date_input("From", value=today_pht(), key="dash_start")
    with dc2:
        d_end = st.date_input("To", value=today_pht(), key="dash_end")

    if d_start > d_end:
        st.error("Start date must be before end date.")
        st.stop()

    is_today = (d_start == today_pht() and d_end == today_pht())

    if is_today:
        dash_q = queue
        date_label = "Today"
    elif d_start == d_end:
        dash_q = get_queue_by_date(d_start.isoformat())
        date_label = d_start.strftime("%b %d, %Y")
    else:
        dash_q = get_queue_date_range(d_start.isoformat(), d_end.isoformat())
        date_label = f"{d_start.strftime('%b %d')} — {d_end.strftime('%b %d, %Y')}"

    st.caption(f"📊 **{date_label}** · {len(dash_q)} entries")

    tot = len(dash_q)
    done = len([r for r in dash_q if r.get("status") == "COMPLETED"])
    cancelled = len([r for r in dash_q if r.get("status") == "CANCELLED"])
    voided = len([r for r in dash_q if r.get("status") == "VOID"])
    expired = len([r for r in dash_q if r.get("status") == "EXPIRED"])
    onl = len([r for r in dash_q if r.get("source") == "ONLINE"])
    ksk = len([r for r in dash_q if r.get("source") == "KIOSK"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total", tot)
    with c2:
        st.metric("Completed", done)
    with c3:
        st.metric("Cancelled", cancelled)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📱 Online", onl)
    with c2:
        st.metric("🏢 Kiosk", ksk)
    with c3:
        st.metric("⚙️ Voided", voided)
    if tot:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("📱 Online %", f"{onl / tot * 100:.0f}%")
        with c2:
            st.metric("🚫 Cancel %", f"{cancelled / tot * 100:.1f}%")
        with c3:
            st.metric("⏰ Expired", expired)

    if is_today:
        st.markdown("**Per Category — Today's Cap**")
        for cat in cats:
            s = sc.get(cat["id"], {"used": 0, "cap": 50, "remaining": 50})
            st.markdown(f"{cat['icon']} **{cat.get('short_label', '')}** — {s['used']}/{s['cap']} · {s['remaining']} remaining")

    # ── CSV Export ──
    st.markdown("---")
    st.markdown(f"**📥 Export: {date_label}**")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Res#", "Source", "Last", "First", "Category", "Service",
                "Status", "BQMS#", "BQMS_Prev", "Mobile", "Priority",
                "Issued", "Arrived", "Serving_At", "Completed", "Cancelled_At",
                "Void_Reason", "Voided_By", "Voided_At", "Expired_At"])
    for r in dash_q:
        w.writerow([
            r.get("queue_date", ""), r.get("res_num", ""), r.get("source", ""),
            r.get("last_name", ""), r.get("first_name", ""),
            r.get("category", ""), r.get("service", ""),
            r.get("status", ""), r.get("bqms_number", ""), r.get("bqms_prev", ""),
            r.get("mobile", ""), r.get("priority", ""),
            r.get("issued_at", ""), r.get("arrived_at", ""), r.get("serving_at", ""),
            r.get("completed_at", ""),
            r.get("cancelled_at", ""),
            r.get("void_reason", ""), r.get("voided_by", ""), r.get("voided_at", ""),
            r.get("expired_at", ""),
        ])

    fname = f"MabiliSSS_{d_start.isoformat()}"
    if d_start != d_end:
        fname += f"_to_{d_end.isoformat()}"
    fname += ".csv"

    st.download_button(
        f"📥 Download CSV ({len(dash_q)} records)",
        data=out.getvalue(),
        file_name=fname,
        mime="text/csv",
        use_container_width=True
    )

# ═══════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""<div style="text-align:center;font-size:10px;opacity:.3;padding:8px;">
    RPTayo / SSS-MND · MabiliSSS Queue {VER}
</div>""", unsafe_allow_html=True)
