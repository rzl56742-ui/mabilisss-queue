"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Member Portal (Public)
 Reserve slots online + track queue status in real-time.
 Run: streamlit run member_app.py --server.port 8501
 © RPT / SSS Gingoog Branch 2026
═══════════════════════════════════════════════════════════
"""

import streamlit as st
from datetime import datetime, date
from db import (
    VER, get_branch, get_categories_with_services, get_queue_today,
    insert_queue_entry, get_bqms_state, slot_counts, next_slot_num,
    is_duplicate, gen_id, today_mmdd, today_iso, OSTATUS, STATUS_LABELS
)

# ── Page Config ──
st.set_page_config(page_title="MabiliSSS Queue", page_icon="🏛️", layout="centered")

# ── CSS ──
st.markdown("""<style>
.sss-header{background:linear-gradient(135deg,#002E52,#0066A1);color:#fff!important;padding:18px 22px;border-radius:12px;margin-bottom:16px}
.sss-header h2{margin:0;font-size:22px;color:#fff!important}
.sss-header p{margin:4px 0 0;opacity:.75;font-size:13px;color:#fff!important}
.sss-card{background:var(--secondary-background-color,#fff);color:var(--text-color,#1a1a2e);border-radius:10px;padding:16px;margin-bottom:12px;border:1px solid rgba(128,128,128,.15)}
.sss-card strong,.sss-card b{color:var(--text-color,#1a1a2e)}
.sss-metric{text-align:center;padding:14px 8px;border-radius:10px;background:var(--secondary-background-color,#f5f5f5);border:1px solid rgba(128,128,128,.1)}
.sss-metric .val{font-size:30px;font-weight:900;line-height:1.2}
.sss-metric .lbl{font-size:11px;opacity:.6;margin-top:2px}
.sss-alert{border-radius:8px;padding:12px 16px;margin-bottom:12px;font-weight:600;text-align:center}
.sss-alert-red{background:rgba(220,53,69,.15);color:#ef4444;border:1px solid rgba(220,53,69,.3)}
.sss-alert-green{background:rgba(15,157,88,.12);color:#22c55e;border:1px solid rgba(15,157,88,.25)}
.sss-alert-blue{background:rgba(59,130,246,.12);color:#60a5fa;border:1px solid rgba(59,130,246,.25)}
.sss-alert-yellow{background:rgba(217,119,6,.12);color:#f59e0b;border:1px solid rgba(217,119,6,.25)}
.sss-alert strong,.sss-alert b{color:inherit}
.sss-bqms{font-family:monospace;font-size:36px;font-weight:900;color:#22B8CF;text-align:center}
.sss-resnum{font-family:monospace;font-size:26px;font-weight:900;color:#3399CC;text-align:center}
.sss-card td{color:var(--text-color,#1a1a2e);padding:4px 0}
.stButton>button{border-radius:8px;font-weight:700}
@keyframes sss-scroll{0%{transform:translateX(0%)}100%{transform:translateX(-33.33%)}}
</style>""", unsafe_allow_html=True)

# ── Auto-refresh ──
_ar_ok = False
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=20_000, limit=None, key="member_ar")
    _ar_ok = True
except ImportError:
    pass

# ── Session defaults ──
for k, v in {"screen":"home","sel_cat":None,"sel_svc":None,"ticket":None,"tracked_id":None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def go(scr):
    st.session_state.screen = scr
    st.rerun()

now = datetime.now()

# ── Load data (fresh every render = real-time sync) ──
branch = get_branch()
cats   = get_categories_with_services()
queue  = get_queue_today()
bqms   = get_bqms_state()
o_stat = branch.get("o_stat", "online")
is_open= o_stat != "offline"
sc     = slot_counts(cats, queue)

# ═══════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════
st.markdown(f"""<div class="sss-header">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div><h2>🏛️ MabiliSSS Queue</h2><p>{branch.get('name','')} · {VER}</p></div>
        <div style="text-align:right;font-size:13px;opacity:.8;">
            {now.strftime('%A, %b %d, %Y')}<br/>{now.strftime('%I:%M %p')}</div>
    </div></div>""", unsafe_allow_html=True)

# Status bar
sm = OSTATUS.get(o_stat, OSTATUS["online"])
st.markdown(f"""<div class="sss-alert sss-alert-{sm['color']}" style="font-size:15px;">
    <strong>{sm['emoji']} {sm['label']}</strong></div>""", unsafe_allow_html=True)

# Announcement
_ann = branch.get("announcement", "").strip()
if _ann:
    st.markdown(f"""<div style="position:sticky;top:0;z-index:999;
        background:linear-gradient(90deg,#002E52,#0066A1);
        color:#fff;padding:10px 0;margin-bottom:12px;border-radius:8px;overflow:hidden;
        box-shadow:0 2px 8px rgba(0,0,0,.15);">
        <div style="display:inline-block;white-space:nowrap;
            animation:sss-scroll 18s linear infinite;font-weight:700;font-size:14px;">
            📢&nbsp;&nbsp;{_ann}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            📢&nbsp;&nbsp;{_ann}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            📢&nbsp;&nbsp;{_ann}
        </div></div>""", unsafe_allow_html=True)

if not _ar_ok:
    if st.button("🔄 Refresh Page", type="primary", use_container_width=True):
        st.rerun()

screen = st.session_state.screen

# ═══════════════════════════════════════════════════
#  HOME
# ═══════════════════════════════════════════════════
if screen == "home":
    active_q = len([r for r in queue if r.get("status") not in ("COMPLETED","NO_SHOW")])
    done_q   = len([r for r in queue if r.get("status") == "COMPLETED"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="sss-metric"><div class="val" style="color:#3399CC;">{active_q}</div><div class="lbl">Active Queue</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="sss-metric"><div class="val" style="color:#22c55e;">{done_q}</div><div class="lbl">Served Today</div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📋 Reserve a Slot", use_container_width=True, type="primary", disabled=not is_open):
            st.session_state.sel_cat = None; st.session_state.sel_svc = None; go("select_cat")
    with c2:
        if st.button("🔍 Track My Queue", use_container_width=True):
            st.session_state.tracked_id = None; go("track_input")

    if not is_open:
        st.warning("🔴 Reservation is currently closed.")

    st.markdown(f"""<div class="sss-card" style="border-left:4px solid #f59e0b;">
        <strong>📌 How It Works</strong><br/><br/>
        1. Tap <b>"Reserve a Slot"</b> and fill in your details.<br/>
        2. Go to {branch.get('name','')} during office hours.<br/>
        3. Present your reservation to the guard.<br/>
        4. Staff assigns your <b>official BQMS queue number</b>.<br/>
        5. Tap <b>"Track My Queue"</b> to monitor live!
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
#  SELECT CATEGORY
# ═══════════════════════════════════════════════════
elif screen == "select_cat":
    if st.button("← Back to Home"): go("home")
    st.subheader("Step 1: Choose Transaction")
    for cat in cats:
        s = sc.get(cat["id"], {"remaining": cat.get("cap",50)})
        full = s["remaining"] <= 0
        c1, c2 = st.columns([5, 1])
        with c1:
            if st.button(f"{cat['icon']} {cat['label']}", key=f"cat_{cat['id']}", disabled=full, use_container_width=True):
                st.session_state.sel_cat = cat; go("select_svc")
        with c2:
            if full:
                st.error("FULL")
            else:
                st.markdown(f"<div style='text-align:center;'><span style='font-size:20px;font-weight:900;color:#3399CC;'>{s['remaining']}</span><br/><span style='font-size:10px;opacity:.5;'>left</span></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
#  SELECT SERVICE
# ═══════════════════════════════════════════════════
elif screen == "select_svc":
    cat = st.session_state.sel_cat
    if not cat: go("select_cat")
    else:
        if st.button("← Back"): go("select_cat")
        st.subheader(f"Step 2: {cat['icon']} {cat.get('short_label','')}")
        for svc in cat.get("services", []):
            if st.button(f"● {svc['label']}", key=f"svc_{svc['id']}", use_container_width=True):
                st.session_state.sel_svc = svc; go("member_form")

# ═══════════════════════════════════════════════════
#  MEMBER FORM
# ═══════════════════════════════════════════════════
elif screen == "member_form":
    cat = st.session_state.sel_cat
    svc = st.session_state.sel_svc
    if not cat or not svc: go("select_cat")
    else:
        if st.button("← Back"): go("select_svc")
        st.subheader("Step 3: Your Details")
        st.markdown(f'<div class="sss-card">{cat["icon"]} <strong>{svc["label"]}</strong><br/><span style="opacity:.6;">{cat["label"]}</span></div>', unsafe_allow_html=True)

        with st.form("reserve_form"):
            fc1, fc2 = st.columns(2)
            with fc1: last_name = st.text_input("Last Name *", placeholder="DELA CRUZ")
            with fc2: first_name = st.text_input("First Name *", placeholder="JUAN")
            fc1, fc2 = st.columns([1,3])
            with fc1: mi = st.text_input("M.I.", max_chars=2)
            with fc2: mobile = st.text_input("Mobile *", placeholder="09XX XXX XXXX")
            pri = st.radio("Lane:", ["👤 Regular", "⭐ Priority (Senior/PWD/Pregnant)"], horizontal=True)
            st.markdown("**🔒 Data Privacy (RA 10173)**")
            consent = st.checkbox("I consent to data collection for today's queue.")

            if st.form_submit_button("📋 Reserve My Slot", type="primary", use_container_width=True):
                lu = last_name.strip().upper(); fu = first_name.strip().upper(); mob = mobile.strip()
                # Fresh read for validation
                fresh_q = get_queue_today()
                errors = []
                if not lu: errors.append("Last Name required.")
                if not fu: errors.append("First Name required.")
                if not mob or len(mob) < 10: errors.append("Valid mobile required.")
                if not consent: errors.append("Check privacy consent.")
                fsc = slot_counts(cats, fresh_q)
                if fsc.get(cat["id"],{}).get("remaining",0) <= 0: errors.append("Slots full.")
                if is_duplicate(fresh_q, lu, fu, mob): errors.append("Duplicate reservation.")

                if errors:
                    for e in errors: st.error(f"❌ {e}")
                else:
                    slot = next_slot_num(fresh_q)
                    rn = f"R-{today_mmdd()}-{slot:03d}"
                    entry = {
                        "id": gen_id(), "queue_date": today_iso(),
                        "slot": slot, "res_num": rn,
                        "last_name": lu, "first_name": fu,
                        "mi": mi.strip().upper(), "mobile": mob,
                        "service": svc["label"], "service_id": svc["id"],
                        "category": cat["label"], "category_id": cat["id"],
                        "cat_icon": cat["icon"],
                        "priority": "priority" if "Priority" in pri else "regular",
                        "status": "RESERVED", "bqms_number": None,
                        "source": "ONLINE", "issued_at": now.isoformat(),
                    }
                    insert_queue_entry(entry)
                    st.session_state.ticket = entry; go("ticket")

# ═══════════════════════════════════════════════════
#  TICKET
# ═══════════════════════════════════════════════════
elif screen == "ticket":
    t = st.session_state.ticket
    if not t: go("home")
    else:
        st.markdown('<div style="text-align:center;"><span style="font-size:48px;">✅</span><h2 style="color:#22c55e;">Slot Reserved!</h2></div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="sss-card" style="border-top:4px solid #3399CC;text-align:center;">
            <div style="font-size:11px;opacity:.5;letter-spacing:2px;">MABILISSS QUEUE — {branch.get('name','').upper()}</div>
            <div style="font-weight:700;margin:4px 0;">{t['category']} — {t['service']}</div>
            <hr style="border:1px dashed rgba(128,128,128,.2);"/>
            <div style="font-size:11px;opacity:.5;">RESERVATION NUMBER</div>
            <div class="sss-resnum">{t['res_num']}</div>
            <hr style="border:1px dashed rgba(128,128,128,.2);"/>
            <div style="font-size:12px;">{t['last_name']}, {t['first_name']} {t.get('mi','')}<br/>📱 {t['mobile']}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="sss-card" style="border-left:4px solid #3399CC;">
            <strong>📋 Next Steps:</strong><br/>
            1. Save: <code style="font-size:16px;font-weight:900;">{t['res_num']}</code><br/>
            2. Go to <strong>{branch.get('name','')}</strong><br/>
            3. Present to guard → get <strong>BQMS number</strong><br/>
            4. Tap <strong>"Track My Queue"</strong> anytime!
        </div>""", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.ticket = None; go("home")
        with c2:
            if st.button("🔍 Track Now", use_container_width=True, type="primary"):
                st.session_state.tracked_id = t["id"]; go("tracker")

# ═══════════════════════════════════════════════════
#  TRACK INPUT
# ═══════════════════════════════════════════════════
elif screen == "track_input":
    if st.button("← Back to Home"): go("home")
    st.markdown('<div style="text-align:center;"><span style="font-size:36px;">🔍</span><h3>Track Your Queue</h3></div>', unsafe_allow_html=True)
    st.caption("💡 Online = **R-** prefix (R-0214-001). Walk-in/kiosk = **K-** prefix (K-0214-001).")

    track_mode = st.radio("Search by:", ["📱 Mobile Number", "#️⃣ Reservation Number"], horizontal=True)
    with st.form("track_form"):
        if "Mobile" in track_mode:
            track_val = st.text_input("Mobile number", placeholder="09XX XXX XXXX")
        else:
            track_val = st.text_input("Reservation #", placeholder="R-0214-005 or K-0214-001")

        if st.form_submit_button("🔍 Find My Queue", type="primary", use_container_width=True):
            fresh = get_queue_today()
            v = track_val.strip()
            if not v:
                st.error("Enter a value.")
            else:
                found = None
                if "Mobile" in track_mode:
                    for r in fresh:
                        if r.get("mobile") == v and r.get("status") not in ("COMPLETED","NO_SHOW"):
                            found = r; break
                    if not found:
                        for r in fresh:
                            if r.get("mobile") == v: found = r; break
                else:
                    vu = v.upper()
                    for r in fresh:
                        if r.get("res_num") == vu and r.get("status") not in ("COMPLETED","NO_SHOW"):
                            found = r; break
                    if not found:
                        for r in fresh:
                            if r.get("res_num") == vu: found = r; break

                if not found:
                    st.error(f"❌ Not found for '{v}'. Check input.")
                    if fresh:
                        st.caption(f"Queue has {len(fresh)} entries today.")
                    else:
                        st.caption("Queue is empty — no entries today.")
                else:
                    st.session_state.tracked_id = found["id"]; go("tracker")

# ═══════════════════════════════════════════════════
#  TRACKER
# ═══════════════════════════════════════════════════
elif screen == "tracker":
    tid = st.session_state.tracked_id
    fresh = get_queue_today()
    fbq   = get_bqms_state()
    t = next((r for r in fresh if r.get("id") == tid), None)

    if not t:
        st.error("❌ Entry not found.")
        if st.button("← Try Again"): go("track_input")
    else:
        has_bqms = bool(t.get("bqms_number"))
        is_done  = t.get("status") == "COMPLETED"
        is_ns    = t.get("status") == "NO_SHOW"
        is_srv   = t.get("status") == "SERVING"

        if is_srv:
            st.markdown('<div class="sss-alert sss-alert-blue" style="font-size:18px;">🎉 <strong>YOU\'RE BEING SERVED!</strong></div>', unsafe_allow_html=True)
        elif is_done:
            st.markdown('<div class="sss-alert sss-alert-green">✅ <strong>Completed</strong> — Thank you!</div>', unsafe_allow_html=True)
        elif is_ns:
            st.markdown('<div class="sss-alert sss-alert-red">❌ <strong>No-Show</strong></div>', unsafe_allow_html=True)

        st.markdown(f"""<div class="sss-card" style="border-top:4px solid {'#22B8CF' if has_bqms else '#3399CC'};text-align:center;">
            <div style="font-size:11px;opacity:.5;">{branch.get('name','').upper()}</div>
            <div style="font-weight:700;margin:4px 0;">{t.get('category','')} — {t.get('service','')}</div>
            <span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;background:rgba(51,153,204,.15);color:#3399CC;">
                {STATUS_LABELS.get(t['status'],t['status'])}</span>
        </div>""", unsafe_allow_html=True)

        if has_bqms:
            st.markdown(f'<div class="sss-card" style="text-align:center;"><div style="font-size:11px;opacity:.5;">YOUR BQMS NUMBER</div><div class="sss-bqms">{t["bqms_number"]}</div></div>', unsafe_allow_html=True)
            if not is_done and not is_ns:
                cat_obj = next((c for c in cats if c["id"] == t.get("category_id")), None)
                ns_val = fbq.get(t.get("category_id",""), "")
                avg = cat_obj["avg_time"] if cat_obj else 10
                ahead = 0
                try:
                    ns_num = int("".join(filter(str.isdigit, str(ns_val))))
                    my_num = int("".join(filter(str.isdigit, str(t["bqms_number"]))))
                    ahead = max(0, my_num - ns_num)
                except: pass
                est = ahead * avg
                m1,m2,m3 = st.columns(3)
                with m1: st.markdown(f'<div class="sss-metric"><div class="val" style="color:#22B8CF;">{ns_val or "—"}</div><div class="lbl">Now Serving</div></div>', unsafe_allow_html=True)
                with m2: st.markdown(f'<div class="sss-metric"><div class="val">{t["bqms_number"]}</div><div class="lbl">Your #</div></div>', unsafe_allow_html=True)
                with m3:
                    wt = "Next!" if est == 0 else f"~{est}m"
                    st.markdown(f'<div class="sss-metric"><div class="val">{wt}</div><div class="lbl">Est. Wait</div></div>', unsafe_allow_html=True)
        else:
            if not is_done and not is_ns:
                st.markdown(f'<div class="sss-card" style="text-align:center;"><div style="font-size:11px;opacity:.5;">RESERVATION NUMBER</div><div class="sss-resnum">{t["res_num"]}</div></div>', unsafe_allow_html=True)
                st.markdown('<div class="sss-alert sss-alert-yellow">⏳ <strong>Waiting for BQMS Number</strong><br/>Staff will assign when you arrive. Auto-refreshes.</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Refresh", use_container_width=True, type="primary"): st.rerun()
        with c2:
            if st.button("🔍 Track Another", use_container_width=True):
                st.session_state.tracked_id = None; go("track_input")

        if not is_done and not is_ns:
            st.caption(f"🔄 Auto-refreshes every 20s · Last: {now.strftime('%I:%M:%S %p')}")

# ═══════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""<div style="text-align:center;font-size:10px;opacity:.3;padding:8px;">
    RPT / SSS Gingoog Branch · MabiliSSS Queue {VER}
</div>""", unsafe_allow_html=True)
