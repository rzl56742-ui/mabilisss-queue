"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Staff Console V2.1.0 (Protected)
 © RPT / SSS Gingoog Branch 2026
═══════════════════════════════════════════════════════════
"""

import streamlit as st
import time, csv, io
from datetime import datetime, date, timedelta
from db import (
    VER, SSS_LOGO, get_branch, update_branch, get_categories_with_services,
    get_categories, get_services,
    get_queue_today, get_queue_by_date, get_queue_date_range, get_available_dates,
    insert_queue_entry, update_queue_entry,
    get_bqms_state, update_bqms_state, get_users, authenticate,
    update_password, update_category_cap,
    add_category, update_category, delete_category,
    add_service, update_service, delete_service,
    slot_counts, next_slot_num, is_duplicate, is_bqms_taken,
    gen_id, today_mmdd, today_iso,
    OSTATUS, STATUS_LABELS
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
.stButton>button{border-radius:8px;font-weight:700}
</style>""", unsafe_allow_html=True)

_ar_ok = False
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=15_000, limit=None, key="staff_ar")
    _ar_ok = True
except ImportError:
    pass

for k, v in {"auth_user":None,"fail_count":0,"lock_until":0,
             "staff_tab":"queue","last_activity":time.time()}.items():
    if k not in st.session_state:
        st.session_state[k] = v

now = datetime.now()
ROLE_ICONS  = {"kiosk":"🏢","staff":"🛡️","th":"👔","bh":"🏛️","dh":"⭐"}
ROLE_LABELS = {"kiosk":"Kiosk","staff":"Staff","th":"Team Head","bh":"Branch Head","dh":"Division Head"}

# ═══════════════════════════════════════════════════
#  LOGIN — NO DEFAULT PASSWORD HINT
# ═══════════════════════════════════════════════════
if not st.session_state.auth_user:
    st.markdown(f"""<div class="sss-header" style="text-align:center;">
        <img src="{SSS_LOGO}" width="48" style="border-radius:8px;background:#fff;padding:3px;margin-bottom:8px;"/>
        <h2>Staff Portal</h2>
        <p>MabiliSSS Queue · Authorized Personnel Only</p>
    </div>""", unsafe_allow_html=True)

    locked = time.time() < st.session_state.lock_until
    if locked:
        st.error(f"🔒 Locked. Wait {int(st.session_state.lock_until - time.time())}s.")

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login", type="primary", use_container_width=True, disabled=locked):
            u = authenticate(username, password)
            if u:
                st.session_state.auth_user = u
                st.session_state.fail_count = 0
                st.session_state.last_activity = time.time()
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
#  SESSION TIMEOUT
# ═══════════════════════════════════════════════════
if time.time() - st.session_state.last_activity > 30 * 60:
    st.session_state.auth_user = None
    st.warning("Session expired. Please login again.")
    st.rerun()

st.session_state.last_activity = time.time()
user = st.session_state.auth_user
role = user["role"]
is_ro = role in ("bh","dh")

branch = get_branch()
cats   = get_categories_with_services()
queue  = get_queue_today()
bqms   = get_bqms_state()
o_stat = branch.get("o_stat", "online")
sc     = slot_counts(cats, queue)

# ═══════════════════════════════════════════════════
#  HEADER + NAV
# ═══════════════════════════════════════════════════
st.markdown(f"""<div class="sss-header">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="display:flex;align-items:center;gap:12px;">
            <img src="{SSS_LOGO}" width="38" style="border-radius:8px;background:#fff;padding:2px;"/>
            <div><h2>Staff Console</h2>
                <p>{user['display_name']} · {ROLE_LABELS.get(role,role)}</p></div>
        </div>
        <div style="text-align:right;font-size:12px;opacity:.8;">{now.strftime('%I:%M %p')}<br/>{date.today().isoformat()}</div>
    </div></div>""", unsafe_allow_html=True)

st.caption(f"🔄 {'Auto-refresh 15s' if _ar_ok else 'Manual refresh'} · {len(queue)} entries · oStat: {o_stat}")

nav = [("📋 Queue","queue")]
if role in ("th","staff"): nav.append(("👔 Admin","admin"))
if role in ("th","staff","bh","dh"): nav.append(("📊 Dashboard","dash"))
nav += [("🔑 Password","pw"),("🚪 Logout","logout")]
cols = st.columns(len(nav))
for i,(lbl,key) in enumerate(nav):
    with cols[i]:
        if key == "logout":
            if st.button(lbl, use_container_width=True):
                st.session_state.auth_user = None; st.rerun()
        else:
            bt = "primary" if st.session_state.staff_tab == key else "secondary"
            if st.button(lbl, use_container_width=True, type=bt):
                st.session_state.staff_tab = key; st.rerun()

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
            if len(np1) < 4: st.error("Min 4 characters.")
            elif np1 != np2: st.error("Passwords don't match.")
            else:
                update_password(user["id"], np1)
                st.success("✅ Password changed!")
                st.session_state.staff_tab = "queue"; st.rerun()

# ═══════════════════════════════════════════════════
#  QUEUE CONSOLE
# ═══════════════════════════════════════════════════
elif tab == "queue":
    unassigned = [r for r in queue if not r.get("bqms_number") and r.get("status") not in ("NO_SHOW","COMPLETED")]

    if not is_ro:
        st.markdown("**System Status**")
        _sopts = ["🟢 Online","🟡 Intermittent","🔴 Offline"]
        _smap  = {"🟢 Online":"online","🟡 Intermittent":"intermittent","🔴 Offline":"offline"}
        _srev  = {v:k for k,v in _smap.items()}
        cur_lbl= _srev.get(o_stat, "🟢 Online")
        new_s  = st.radio("Status:", _sopts, horizontal=True, index=_sopts.index(cur_lbl))
        if _smap[new_s] != o_stat:
            update_branch(o_stat=_smap[new_s])
            st.rerun()

        if role != "kiosk":
            with st.expander(f"📢 Announcement {'(ACTIVE)' if branch.get('announcement','').strip() else '(none)'}"):
                with st.form("ann_form"):
                    ann_text = st.text_area("Scrolling banner on member app", value=branch.get("announcement",""), height=80)
                    ac1, ac2 = st.columns([3,1])
                    with ac1:
                        if st.form_submit_button("📢 Post", type="primary"):
                            update_branch(announcement=ann_text.strip())
                            st.success("✅ Posted!"); st.rerun()
                    with ac2:
                        if st.form_submit_button("🗑️ Clear"):
                            update_branch(announcement="")
                            st.success("✅ Cleared!"); st.rerun()

        if unassigned:
            st.markdown(f'<div class="sss-alert sss-alert-red" style="font-size:16px;">🔴 <strong>{len(unassigned)} NEED BQMS#</strong></div>', unsafe_allow_html=True)

        with st.expander("🔄 BQMS — Now Serving"):
            with st.form("bqms_form"):
                new_bqms = {}
                for i in range(0, len(cats), 2):
                    cols2 = st.columns(2)
                    for j, col in enumerate(cols2):
                        idx = i + j
                        if idx >= len(cats): break
                        c = cats[idx]
                        with col:
                            cur = bqms.get(c["id"], "")
                            val = st.text_input(f"{c['icon']} {c.get('short_label','')}", value=cur, key=f"bqms_{c['id']}")
                            new_bqms[c["id"]] = val.strip().upper()
                if st.form_submit_button("Update", type="primary", use_container_width=True):
                    for cid, ns in new_bqms.items():
                        if ns != bqms.get(cid, ""):
                            update_bqms_state(cid, ns)
                    st.success("✅ Updated!"); st.rerun()

        with st.expander("➕ Add Walk-in"):
            with st.form("walkin"):
                cat_labels = ["-- Select --"] + [f"{c['icon']} {c['label']} ({sc.get(c['id'],{}).get('remaining',0)} left)" for c in cats]
                w_cat_i = st.selectbox("Category *", range(len(cat_labels)), format_func=lambda i: cat_labels[i])
                w_cat = cats[w_cat_i - 1] if w_cat_i > 0 else None
                w_svc = None
                if w_cat:
                    svc_labels = ["-- None --"] + [s["label"] for s in w_cat.get("services",[])]
                    w_svc_i = st.selectbox("Sub-service", range(len(svc_labels)), format_func=lambda i: svc_labels[i])
                    w_svc = w_cat["services"][w_svc_i-1] if w_svc_i > 0 else None

                wc1,wc2 = st.columns(2)
                with wc1: wl = st.text_input("Last Name *", key="wl")
                with wc2: wf = st.text_input("First Name *", key="wf")
                wc1,wc2 = st.columns([1,3])
                with wc1: wmi = st.text_input("M.I.", max_chars=2, key="wmi")
                with wc2: wmob = st.text_input("Mobile (optional)", key="wmob")
                wpri = st.radio("Lane:", ["👤 Regular","⭐ Priority"], horizontal=True, key="wpri")
                wbqms = ""
                if role != "kiosk":
                    wbqms = st.text_input("BQMS # (if issued)", placeholder="Leave blank if not yet", key="wbqms")

                if st.form_submit_button("Register Walk-in", type="primary", use_container_width=True):
                    wlu = wl.strip().upper(); wfu = wf.strip().upper(); wmu = wmob.strip()
                    errs = []
                    if not w_cat: errs.append("Select category.")
                    if not wlu: errs.append("Last Name required.")
                    if not wfu: errs.append("First Name required.")
                    if errs:
                        for e in errs: st.error(f"❌ {e}")
                    else:
                        fresh_q = get_queue_today()
                        fsc = slot_counts(cats, fresh_q)
                        bv_check = wbqms.strip().upper() if wbqms else ""
                        if is_duplicate(fresh_q, wlu, wfu, wmu):
                            st.error("Duplicate entry.")
                        elif fsc.get(w_cat["id"],{}).get("remaining",0) <= 0:
                            st.error(f"Daily cap reached for {w_cat['label']}.")
                        elif bv_check and is_bqms_taken(fresh_q, bv_check):
                            st.error(f"❌ BQMS **{bv_check}** already assigned!")
                        else:
                            slot = next_slot_num(fresh_q)
                            rn = f"K-{today_mmdd()}-{slot:03d}"
                            svc_lbl = w_svc["label"] if w_svc else "Walk-in"
                            svc_id  = w_svc["id"] if w_svc else "walkin"
                            entry = {
                                "id": gen_id(), "queue_date": today_iso(),
                                "slot": slot, "res_num": rn,
                                "last_name": wlu, "first_name": wfu,
                                "mi": wmi.strip().upper(), "mobile": wmu,
                                "service": svc_lbl, "service_id": svc_id,
                                "category": w_cat["label"], "category_id": w_cat["id"],
                                "cat_icon": w_cat["icon"],
                                "priority": "priority" if "Priority" in wpri else "regular",
                                "status": "ARRIVED" if bv_check else "RESERVED",
                                "bqms_number": bv_check or None, "source": "KIOSK",
                                "issued_at": now.isoformat(),
                                "arrived_at": now.isoformat() if bv_check else None,
                            }
                            insert_queue_entry(entry)
                            st.success(f"✅ **{rn}** — Share this with the member!")
                            st.rerun()

    # ── QUEUE LIST ──
    st.markdown("---")
    _fm = {"🔴 Need BQMS":"UNASSIGNED","All":"all","🏢 Kiosk":"KIOSK","📱 Online":"ONLINE","✅ Arrived":"ARRIVED","✔ Done":"COMPLETED","❌ No-Show":"NO_SHOW"}
    sel_f = st.radio("Filter:", list(_fm.keys()), horizontal=True, index=0)
    qf = _fm[sel_f]
    search = st.text_input("🔍 Search", key="qsearch")

    sorted_q = sorted(queue, key=lambda r: (0 if not r.get("bqms_number") and r.get("status") not in ("NO_SHOW","COMPLETED") else 1, r.get("issued_at","")))
    filt = sorted_q
    if qf == "UNASSIGNED": filt = [r for r in filt if not r.get("bqms_number") and r.get("status") not in ("NO_SHOW","COMPLETED")]
    elif qf == "KIOSK": filt = [r for r in filt if r.get("source") == "KIOSK"]
    elif qf == "ONLINE": filt = [r for r in filt if r.get("source") == "ONLINE"]
    elif qf != "all": filt = [r for r in filt if r.get("status") == qf]
    if search:
        sl = search.strip().lower()
        filt = [r for r in filt if sl in r.get("last_name","").lower() or sl in r.get("first_name","").lower() or sl in (r.get("bqms_number","") or "").lower() or sl in (r.get("res_num","") or "").lower()]

    st.caption(f"Showing {len(filt)} of {len(queue)} entries")

    if not filt:
        if qf == "UNASSIGNED": st.success("✅ All entries have BQMS#!")
        else: st.info("No entries.")
    else:
        for r in filt:
            needs_b = not r.get("bqms_number") and r.get("status") not in ("NO_SHOW","COMPLETED")
            bdr = "#ef4444" if needs_b else "rgba(128,128,128,.15)"
            src = "🏢" if r.get("source") == "KIOSK" else "📱"
            pri = "⭐" if r.get("priority") == "priority" else ""
            bqms_h = f'<div style="font-family:monospace;font-size:20px;font-weight:900;color:#22B8CF;margin-top:4px;">BQMS: {r["bqms_number"]}</div>' if r.get("bqms_number") else ""

            st.markdown(f"""<div class="sss-card" style="border-left:4px solid {bdr};">
                <div style="display:flex;justify-content:space-between;">
                    <div><span style="font-family:monospace;font-size:15px;font-weight:800;color:#3399CC;">{r.get('res_num','')}</span>
                        <span style="font-size:11px;opacity:.5;margin-left:6px;">{src}</span>{pri}<br/>
                        <strong>{r.get('cat_icon','')} {r['last_name']}, {r['first_name']} {r.get('mi','')}</strong><br/>
                        <span style="font-size:12px;opacity:.6;">{r.get('category','')} → {r.get('service','')}</span>
                        {f'<br/><span style="font-size:11px;opacity:.5;">📱 {r["mobile"]}</span>' if r.get('mobile') else ''}
                    </div>
                    <div style="text-align:right;">
                        <span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;background:rgba(51,153,204,.15);color:#3399CC;">
                            {STATUS_LABELS.get(r['status'],r['status'])}</span>{bqms_h}
                    </div>
                </div></div>""", unsafe_allow_html=True)

            if not is_ro:
                if needs_b:
                    st.markdown(f"""<div style="background:rgba(220,53,69,.08);border:1px solid rgba(220,53,69,.25);border-radius:8px;padding:10px 14px;margin-bottom:8px;">
                        <span style="font-size:12px;font-weight:700;color:#ef4444;">🎫 Assign BQMS for {r.get('res_num','')}</span></div>""", unsafe_allow_html=True)
                    ac1,ac2 = st.columns([3,1])
                    with ac1: bv = st.text_input(f"BQMS#", key=f"a_{r['id']}", placeholder="e.g., L-023")
                    with ac2:
                        st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
                        if st.button("🎫 Assign", key=f"ba_{r['id']}", type="primary", use_container_width=True):
                            if bv.strip():
                                bv_clean = bv.strip().upper()
                                fresh_q = get_queue_today()
                                if is_bqms_taken(fresh_q, bv_clean):
                                    st.error(f"❌ BQMS **{bv_clean}** is already assigned! Use a different number.")
                                else:
                                    update_queue_entry(r["id"],
                                        bqms_number=bv_clean,
                                        status="ARRIVED",
                                        arrived_at=now.isoformat())
                                    st.rerun()
                            else:
                                st.warning("Enter BQMS# first.")
                    if st.button("❌ No-Show", key=f"ns_{r['id']}", use_container_width=True):
                        update_queue_entry(r["id"], status="NO_SHOW")
                        st.rerun()

                elif r.get("status") == "ARRIVED":
                    ac1,ac2,ac3 = st.columns(3)
                    with ac1:
                        if st.button("🔵 Serving", key=f"srv_{r['id']}", use_container_width=True):
                            update_queue_entry(r["id"], status="SERVING")
                            st.rerun()
                    with ac2:
                        if st.button("✅ Complete", key=f"dn_{r['id']}", use_container_width=True):
                            update_queue_entry(r["id"], status="COMPLETED", completed_at=now.isoformat())
                            st.rerun()
                    with ac3:
                        if st.button("❌ NS", key=f"ns2_{r['id']}", use_container_width=True):
                            update_queue_entry(r["id"], status="NO_SHOW")
                            st.rerun()

                elif r.get("status") == "SERVING":
                    if st.button("✅ Complete", key=f"dn2_{r['id']}", type="primary", use_container_width=True):
                        update_queue_entry(r["id"], status="COMPLETED", completed_at=now.isoformat())
                        st.rerun()
            st.markdown("")

    st.markdown("---")
    if st.button("🔄 Refresh Queue", use_container_width=True): st.rerun()

# ═══════════════════════════════════════════════════
#  ADMIN TAB (TH/Staff)
# ═══════════════════════════════════════════════════
elif tab == "admin" and role in ("th","staff"):
    st.subheader("👔 Admin Panel")
    atabs = st.tabs(["📋 Categories","🔧 Sub-Categories","📊 Daily Caps","👥 Users","🏢 Branch"])

    # ── CATEGORIES (Full CRUD) ──
    with atabs[0]:
        st.markdown("**Manage BQMS Categories**")
        st.caption("These are the main transaction categories shown to members. Customize them to match your branch BQMS.")

        for cat in cats:
            with st.expander(f"{cat['icon']} {cat['label']} — `{cat['id']}` · Cap: {cat['cap']} · Avg: {cat['avg_time']}m"):
                with st.form(f"edit_cat_{cat['id']}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        new_label = st.text_input("Label", value=cat["label"], key=f"cl_{cat['id']}")
                        new_icon = st.text_input("Icon (emoji)", value=cat["icon"], key=f"ci_{cat['id']}")
                    with ec2:
                        new_short = st.text_input("Short Label", value=cat.get("short_label",""), key=f"cs_{cat['id']}")
                        new_avg = st.number_input("Avg Time (min)", value=cat["avg_time"], min_value=1, key=f"ca_{cat['id']}")
                    new_order = st.number_input("Sort Order", value=cat.get("sort_order",0), min_value=0, key=f"co_{cat['id']}")

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.form_submit_button("💾 Save", type="primary"):
                            update_category(cat["id"],
                                label=new_label.strip(), icon=new_icon.strip(),
                                short_label=new_short.strip(), avg_time=new_avg,
                                sort_order=new_order)
                            st.success("✅ Updated!"); st.rerun()
                    with ec2:
                        if st.form_submit_button("🗑️ Delete Category"):
                            delete_category(cat["id"])
                            st.success(f"✅ Deleted {cat['label']}"); st.rerun()

        st.markdown("---")
        st.markdown("**➕ Add New Category**")
        with st.form("add_cat"):
            ac1, ac2 = st.columns(2)
            with ac1:
                nc_id = st.text_input("Category ID (unique, lowercase)", placeholder="e.g., loans_new")
                nc_label = st.text_input("Full Label", placeholder="e.g., Salary Loans")
                nc_icon = st.text_input("Icon (emoji)", value="📋")
            with ac2:
                nc_short = st.text_input("Short Label", placeholder="e.g., SalLoans")
                nc_avg = st.number_input("Avg Service Time (min)", value=10, min_value=1)
                nc_cap = st.number_input("Daily Cap", value=50, min_value=1)
            nc_order = st.number_input("Sort Order", value=len(cats)+1, min_value=0)

            if st.form_submit_button("➕ Add Category", type="primary"):
                nid = nc_id.strip().lower().replace(" ","_")
                if not nid or not nc_label.strip():
                    st.error("ID and Label required.")
                elif any(c["id"] == nid for c in cats):
                    st.error(f"ID '{nid}' already exists.")
                else:
                    add_category(nid, nc_label.strip(), nc_icon.strip(),
                                 nc_short.strip(), nc_avg, nc_cap, nc_order)
                    st.success(f"✅ Added {nc_label.strip()}!"); st.rerun()

    # ── SUB-CATEGORIES / SERVICES (Full CRUD) ──
    with atabs[1]:
        st.markdown("**Manage Sub-Categories / Services**")
        st.caption("These are the specific services under each category. Customize to match your branch BQMS sub-categories.")

        for cat in cats:
            st.markdown(f"### {cat['icon']} {cat['label']}")
            svcs = cat.get("services", [])
            if not svcs:
                st.caption("No sub-categories yet.")
            for svc in svcs:
                sc1, sc2, sc3 = st.columns([4,1,1])
                with sc1:
                    new_slabel = st.text_input("Label", value=svc["label"], key=f"sl_{svc['id']}", label_visibility="collapsed")
                with sc2:
                    if st.button("💾", key=f"ss_{svc['id']}"):
                        update_service(svc["id"], label=new_slabel.strip())
                        st.rerun()
                with sc3:
                    if st.button("🗑️", key=f"sd_{svc['id']}"):
                        delete_service(svc["id"])
                        st.rerun()

            with st.form(f"add_svc_{cat['id']}"):
                ns1, ns2 = st.columns([3,1])
                with ns1:
                    new_svc_label = st.text_input("New sub-category", placeholder="e.g., Calamity Loan", key=f"nsv_{cat['id']}")
                with ns2:
                    if st.form_submit_button("➕ Add"):
                        if new_svc_label.strip():
                            sid = f"{cat['id']}_{new_svc_label.strip().lower().replace(' ','_')[:20]}"
                            add_service(sid, cat["id"], new_svc_label.strip(), len(svcs)+1)
                            st.success(f"✅ Added!"); st.rerun()
            st.markdown("---")

    # ── DAILY CAPS ──
    with atabs[2]:
        st.markdown("**📊 Daily Caps — Slots per Category**")
        st.caption("Set the maximum number of members accommodated per category for the WHOLE DAY (8AM-5PM). Served entries count toward the cap — only No-Show frees a slot.")

        with st.form("caps"):
            for cat in cats:
                s = sc.get(cat["id"], {"used":0,"cap":50,"remaining":50})
                st.markdown(f"**{cat['icon']} {cat['label']}** — Used: {s['used']} / Cap: {s['cap']} · Remaining: **{s['remaining']}**")
                new_cap = st.number_input(
                    f"Daily cap for {cat.get('short_label',cat['label'])}",
                    value=s["cap"], min_value=1, max_value=999,
                    key=f"cap_{cat['id']}",
                    help=f"Currently {s['used']} used, {s['remaining']} remaining"
                )
                st.session_state[f"_ncap_{cat['id']}"] = new_cap

            if st.form_submit_button("💾 Save All Caps", type="primary", use_container_width=True):
                for cat in cats:
                    nc = st.session_state.get(f"_ncap_{cat['id']}", cat["cap"])
                    if nc != cat["cap"]:
                        update_category_cap(cat["id"], nc)
                st.success("✅ Caps saved!"); st.rerun()

        st.markdown("---")
        st.markdown("**📋 Today's Cap Status**")
        for cat in cats:
            s = sc.get(cat["id"], {"used":0,"cap":50,"remaining":50})
            pct = (s["used"] / s["cap"] * 100) if s["cap"] > 0 else 0
            bar_color = "#22c55e" if pct < 70 else "#f59e0b" if pct < 90 else "#ef4444"
            st.markdown(f"""<div style="margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;font-size:13px;">
                    <span>{cat['icon']} {cat.get('short_label','')}</span>
                    <span><b>{s['used']}</b> / {s['cap']} ({pct:.0f}%)</span>
                </div>
                <div style="background:rgba(128,128,128,.1);border-radius:4px;height:8px;overflow:hidden;">
                    <div style="background:{bar_color};width:{min(pct,100):.0f}%;height:100%;border-radius:4px;"></div>
                </div>
            </div>""", unsafe_allow_html=True)

    # ── USERS ──
    with atabs[3]:
        users = get_users()
        for u in users:
            rl = ROLE_LABELS.get(u["role"], u["role"])
            st.markdown(f"**{u['display_name']}** — {rl} · `{u['username']}` · {'🟢' if u.get('active',True) else '🔴'}")

    # ── BRANCH ──
    with atabs[4]:
        with st.form("branch"):
            bn = st.text_input("Name", value=branch.get("name",""))
            ba = st.text_input("Address", value=branch.get("address",""))
            bh = st.text_input("Hours", value=branch.get("hours",""))
            if st.form_submit_button("Save", type="primary"):
                update_branch(name=bn, address=ba, hours=bh)
                st.success("✅ Saved!"); st.rerun()

# ═══════════════════════════════════════════════════
#  DASHBOARD TAB (TH, Staff, BH, DH)
# ═══════════════════════════════════════════════════
elif tab == "dash" and role in ("th","staff","bh","dh"):
    st.subheader("📊 Dashboard")

    # ── Date Slicer ──
    st.markdown("**📅 Select Date Range**")
    dc1, dc2 = st.columns(2)
    with dc1:
        d_start = st.date_input("From", value=date.today(), key="dash_start")
    with dc2:
        d_end = st.date_input("To", value=date.today(), key="dash_end")

    if d_start > d_end:
        st.error("Start date must be before end date.")
        st.stop()

    is_today = (d_start == date.today() and d_end == date.today())

    if is_today:
        dash_q = queue
        date_label = "Today"
    elif d_start == d_end:
        dash_q = get_queue_by_date(d_start.isoformat())
        date_label = d_start.strftime("%b %d, %Y")
    else:
        dash_q = get_queue_date_range(d_start.isoformat(), d_end.isoformat())
        date_label = f"{d_start.strftime('%b %d')} — {d_end.strftime('%b %d, %Y')}"

    st.caption(f"📊 Showing data for: **{date_label}** · {len(dash_q)} entries")

    tot  = len(dash_q)
    done = len([r for r in dash_q if r.get("status") == "COMPLETED"])
    ns   = len([r for r in dash_q if r.get("status") == "NO_SHOW"])
    onl  = len([r for r in dash_q if r.get("source") == "ONLINE"])
    ksk  = len([r for r in dash_q if r.get("source") == "KIOSK"])

    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Total", tot)
    with c2: st.metric("Completed", done)
    with c3: st.metric("No-Show", ns)
    c1,c2 = st.columns(2)
    with c1: st.metric("📱 Online", onl)
    with c2: st.metric("🏢 Kiosk", ksk)
    if tot:
        c1,c2 = st.columns(2)
        with c1: st.metric("📱 Online Adoption", f"{onl/tot*100:.0f}%")
        with c2: st.metric("❌ No-Show Rate", f"{ns/tot*100:.1f}%")

    if is_today:
        st.markdown("**Per Category — Today's Cap**")
        for cat in cats:
            s = sc.get(cat["id"], {"used":0,"cap":50,"remaining":50})
            st.markdown(f"{cat['icon']} **{cat.get('short_label','')}** — {s['used']}/{s['cap']} · {s['remaining']} remaining")

    # ── CSV Export with Date Slicer ──
    st.markdown("---")
    st.markdown(f"**📥 Export: {date_label}**")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date","Res#","Source","Last","First","Category","Service","Status","BQMS#","Mobile","Priority","Issued","Arrived","Completed"])
    for r in dash_q:
        w.writerow([
            r.get("queue_date",""), r.get("res_num",""), r.get("source",""),
            r.get("last_name",""), r.get("first_name",""),
            r.get("category",""), r.get("service",""),
            r.get("status",""), r.get("bqms_number",""),
            r.get("mobile",""), r.get("priority",""),
            r.get("issued_at",""), r.get("arrived_at",""), r.get("completed_at","")
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
    RPT / SSS Gingoog Branch · MabiliSSS Queue {VER}
</div>""", unsafe_allow_html=True)
