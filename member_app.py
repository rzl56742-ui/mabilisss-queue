"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Member Portal V2.2.0 (Public)
 © RPT / SSS Gingoog Branch 2026
═══════════════════════════════════════════════════════════
"""

import streamlit as st
from datetime import datetime
from db import (
    VER, SSS_LOGO, PHT, now_pht, today_pht, today_iso, today_mmdd,
    get_branch, get_categories_with_services, get_queue_today,
    insert_queue_entry, get_bqms_state, slot_counts, next_slot_num,
    is_duplicate, count_ahead, cancel_entry, expire_old_reserved,
    validate_mobile_ph, gen_id, extract_bqms_num,
    OSTATUS, STATUS_LABELS, TERMINAL, FREED
)

st.set_page_config(page_title="MabiliSSS Queue", page_icon="🏛️", layout="centered")

st.markdown("""<style>
.sss-header{background:linear-gradient(135deg,#002E52,#0066A1);color:#fff!important;padding:18px 22px;border-radius:12px;margin-bottom:16px}
.sss-header h2{margin:0;font-size:22px;color:#fff!important}
.sss-header p{margin:4px 0 0;opacity:.75;font-size:13px;color:#fff!important}
.sss-card{background:var(--secondary-background-color,#fff);color:var(--text-color,#1a1a2e);border-radius:10px;padding:16px;margin-bottom:12px;border:1px solid rgba(128,128,128,.15)}
.sss-card strong,.sss-card b{color:var(--text-color,#1a1a2e)}
.sss-metric{text-align:center;padding:14px 8px;border-radius:10px;background:var(--secondary-background-color,#f5f5f5);border:1px solid rgba(128,128,128,.1)}
.sss-metric .val{font-size:30px;font-weight:900;line-height:1.2}
.sss-metric .lbl{font-size:12px;opacity:.8;margin-top:4px;font-weight:600}
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

# ── Session state ──
for k, v in {"screen": "home", "sel_cat": None, "sel_svc": None,
             "ticket": None, "tracked_id": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def go(scr):
    st.session_state.screen = scr
    st.rerun()

# ── Auto-expire old RESERVED entries (runs once per session) ──
if "expired_run" not in st.session_state:
    expire_old_reserved()
    st.session_state.expired_run = True

# ── Time (PHT) ──
now = now_pht()
screen = st.session_state.screen

# ── Conditional data loading (PERF fix: only load what's needed) ──
branch = get_branch()
cats = None
queue = None
bqms = None
sc = None

def load_queue_data():
    global cats, queue, sc
    if cats is None:
        cats = get_categories_with_services()
    if queue is None:
        queue = get_queue_today()
    if sc is None:
        sc = slot_counts(cats, queue)

def load_bqms_data():
    global bqms
    if bqms is None:
        bqms = get_bqms_state()

# Screens that need full data
if screen in ("home", "select_cat", "select_svc", "member_form"):
    load_queue_data()
if screen == "tracker":
    load_queue_data()
    load_bqms_data()

o_stat = branch.get("o_stat", "online")
is_open = o_stat != "offline"

# ═══════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════
st.markdown(f"""<div class="sss-header">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="display:flex;align-items:center;gap:12px;">
            <img src="{SSS_LOGO}" width="44" height="44"
                 style="border-radius:8px;background:#fff;padding:2px;"
                 onerror="this.style.display='none'"/>
            <div><h2>MabiliSSS Queue</h2>
                <p>{branch.get('name','')} · {VER}</p></div>
        </div>
        <div style="text-align:right;font-size:13px;opacity:.8;">
            {now.strftime('%A, %b %d, %Y')}<br/>{now.strftime('%I:%M %p')} PHT</div>
    </div></div>""", unsafe_allow_html=True)

# ── Status bar ──
sm = OSTATUS.get(o_stat, OSTATUS["online"])
st.markdown(f"""<div class="sss-alert sss-alert-{sm['color']}" style="font-size:15px;">
    <strong>{sm['emoji']} {sm['label']}</strong></div>""", unsafe_allow_html=True)

# ── Announcement ──
_ann = branch.get("announcement", "").strip()
if _ann:
    st.markdown(f"""<div style="background:linear-gradient(90deg,#002E52,#0066A1);
        color:#fff;padding:10px 0;margin-bottom:12px;border-radius:8px;overflow:hidden;
        box-shadow:0 2px 8px rgba(0,0,0,.15);">
        <div style="display:inline-block;white-space:nowrap;
            animation:sss-scroll 18s linear infinite;font-weight:700;font-size:14px;">
            📢&nbsp;&nbsp;{_ann}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            📢&nbsp;&nbsp;{_ann}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            📢&nbsp;&nbsp;{_ann}
        </div></div>""", unsafe_allow_html=True)

# ── Manual refresh fallback ──
if not _ar_ok:
    if st.button("🔄 Refresh Page", type="primary", use_container_width=True):
        st.rerun()

# ═══════════════════════════════════════════════════
#  HOME
# ═══════════════════════════════════════════════════
if screen == "home":
    waiting_q = len([r for r in queue if r.get("status") in ("RESERVED", "ARRIVED")])
    serving_q = len([r for r in queue if r.get("status") == "SERVING"])
    total_remaining = sum(sc.get(c["id"], {}).get("remaining", 0) for c in cats)

    # ── Live Queue Snapshot — helps members decide if now is a good time ──
    st.markdown(f"""<div class="sss-card" style="padding:10px 14px;">
        <div style="font-size:11px;opacity:.5;text-align:center;margin-bottom:8px;letter-spacing:1px;">
            📊 LIVE QUEUE STATUS — {branch.get('name','').upper()}</div></div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        wc = "#f59e0b" if waiting_q > 0 else "#22c55e"
        st.markdown(f'<div class="sss-metric"><div class="val" style="color:{wc};">📋 {waiting_q}</div><div class="lbl">In Queue</div></div>', unsafe_allow_html=True)
    with c2:
        sc_color = "#3399CC" if serving_q > 0 else "rgba(128,128,128,.4)"
        st.markdown(f'<div class="sss-metric"><div class="val" style="color:{sc_color};">🔵 {serving_q}</div><div class="lbl">Being Served</div></div>', unsafe_allow_html=True)
    with c3:
        rc = "#22c55e" if total_remaining > 10 else "#f59e0b" if total_remaining > 0 else "#ef4444"
        rl = "FULL" if total_remaining <= 0 else str(total_remaining)
        st.markdown(f'<div class="sss-metric"><div class="val" style="color:{rc};">🎫 {rl}</div><div class="lbl">Slots Left Today</div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📋 Reserve a Slot", use_container_width=True, type="primary", disabled=not is_open):
            st.session_state.sel_cat = None
            st.session_state.sel_svc = None
            go("select_cat")
    with c2:
        if st.button("🔍 Track My Queue", use_container_width=True):
            st.session_state.tracked_id = None
            go("track_input")

    if not is_open:
        st.warning("🔴 Reservation is currently closed.")

    st.markdown(f"""<div class="sss-card" style="border-left:4px solid #0066A1;">
        <strong>📌 Paano Gamitin / How It Works</strong><br/><br/>
        <b>Step 1:</b> Tap <b>"Reserve a Slot"</b> → choose your transaction → fill in your name and mobile number.<br/><br/>
        <b>Step 2:</b> Save your <b>Reservation Number</b> (ex: R-0215-001).<br/><br/>
        <b>Step 3:</b> Go to <b>{branch.get('name','')}</b> during office hours. Show your reservation to the guard.<br/><br/>
        <b>Step 4:</b> Staff will assign your official <b>BQMS queue number</b>.<br/><br/>
        <b>Step 5:</b> Tap <b>"Track My Queue"</b> anytime to check your position and estimated wait time!<br/><br/>
        <b>📱 Need to cancel?</b> Tap "Track My Queue" → find your entry → tap <b>Cancel</b>. Your slot will be released for other members.
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
#  SELECT CATEGORY
# ═══════════════════════════════════════════════════
elif screen == "select_cat":
    if st.button("← Back to Home"):
        go("home")
    st.subheader("Step 1: Choose Transaction")

    for cat in cats:
        s = sc.get(cat["id"], {"remaining": cat.get("cap", 50), "used": 0, "cap": cat.get("cap", 50)})
        full = s["remaining"] <= 0
        c1, c2 = st.columns([5, 1])
        with c1:
            if st.button(f"{cat['icon']} {cat['label']}", key=f"cat_{cat['id']}",
                         disabled=full, use_container_width=True):
                st.session_state.sel_cat = cat["id"]  # Store ID only, not stale dict
                go("select_svc")
        with c2:
            if full:
                st.markdown('<div style="text-align:center;"><span style="font-size:12px;font-weight:900;color:#ef4444;">FULL</span></div>', unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center;'><span style='font-size:20px;font-weight:900;color:#3399CC;'>{s['remaining']}</span><br/><span style='font-size:10px;opacity:.5;'>left</span></div>", unsafe_allow_html=True)

    all_full = all(sc.get(c["id"], {}).get("remaining", 0) <= 0 for c in cats)
    if all_full:
        st.markdown("""<div class="sss-alert sss-alert-red" style="font-size:14px;">
            <strong>⚠️ All slots for today are full.</strong><br/>
            Please try again on the next working day (Mon-Fri, 8AM-5PM).
            <br/><br/>Thank you for your patience!
        </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
#  SELECT SERVICE
# ═══════════════════════════════════════════════════
elif screen == "select_svc":
    sel_cat_id = st.session_state.sel_cat
    if not sel_cat_id:
        go("select_cat")
    else:
        # Always use FRESH category data (not stale session copy)
        cat = next((c for c in cats if c["id"] == sel_cat_id), None)
        if not cat:
            st.error("Category not found. It may have been removed.")
            if st.button("← Back"):
                go("select_cat")
        else:
            if st.button("← Back"):
                go("select_cat")

            # Re-check cap with fresh data
            fresh_q = get_queue_today()
            fsc = slot_counts(cats, fresh_q)
            s = fsc.get(cat["id"], {"remaining": 0, "cap": cat.get("cap", 50)})

            if s["remaining"] <= 0:
                st.markdown(f"""<div class="sss-alert sss-alert-red" style="font-size:14px;">
                    <strong>⚠️ No available slots for {cat['icon']} {cat['label']} today.</strong><br/>
                    Daily limit of <b>{s['cap']}</b> has been reached.<br/><br/>
                    Please try again on the <b>next working day</b> (Mon-Fri, 8AM-5PM).
                </div>""", unsafe_allow_html=True)
            else:
                st.subheader(f"Step 2: {cat['icon']} {cat.get('short_label', cat['label'])}")
                st.caption(f"Slots remaining: {s['remaining']} of {s['cap']}")
                for svc in cat.get("services", []):
                    if st.button(f"● {svc['label']}", key=f"svc_{svc['id']}", use_container_width=True):
                        st.session_state.sel_svc = svc["id"]  # Store ID only
                        go("member_form")

# ═══════════════════════════════════════════════════
#  MEMBER FORM
# ═══════════════════════════════════════════════════
elif screen == "member_form":
    sel_cat_id = st.session_state.sel_cat
    sel_svc_id = st.session_state.sel_svc
    if not sel_cat_id or not sel_svc_id:
        go("select_cat")
    else:
        cat = next((c for c in cats if c["id"] == sel_cat_id), None)
        svc = next((s for s in (cat.get("services", []) if cat else []) if s["id"] == sel_svc_id), None)
        if not cat or not svc:
            st.error("Selection not found. Please start over.")
            if st.button("← Start Over"):
                go("select_cat")
        else:
            if st.button("← Back"):
                go("select_svc")
            st.subheader("Step 3: Your Details")
            st.markdown(f'<div class="sss-card">{cat["icon"]} <strong>{svc["label"]}</strong><br/><span style="opacity:.6;">{cat["label"]}</span></div>', unsafe_allow_html=True)

            with st.form("reserve_form"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    last_name = st.text_input("Last Name *", placeholder="DELA CRUZ")
                with fc2:
                    first_name = st.text_input("First Name *", placeholder="JUAN")
                fc1, fc2 = st.columns([1, 3])
                with fc1:
                    mi = st.text_input("M.I.", max_chars=2)
                with fc2:
                    mobile = st.text_input("Mobile * (09XX XXX XXXX)", placeholder="09171234567")
                pri = st.radio("Lane:", ["👤 Regular", "⭐ Priority (Senior/PWD/Pregnant)"], horizontal=True)
                st.markdown("**🔒 Data Privacy (RA 10173)**")
                consent = st.checkbox("I consent to data collection for today's queue.")

                if st.form_submit_button("📋 Reserve My Slot", type="primary", use_container_width=True):
                    lu = last_name.strip().upper()
                    fu = first_name.strip().upper()
                    mob_raw = mobile.strip()

                    errors = []
                    if not lu:
                        errors.append("Last Name required.")
                    if not fu:
                        errors.append("First Name required.")

                    # Validate PH mobile
                    mob_clean = validate_mobile_ph(mob_raw)
                    if not mob_raw:
                        errors.append("Mobile number required.")
                    elif not mob_clean:
                        errors.append("Invalid mobile. Use 09XX format (11 digits).")

                    if not consent:
                        errors.append("Check privacy consent.")

                    # Fresh cap check at submission time
                    fresh_q = get_queue_today()
                    fsc = slot_counts(cats, fresh_q)
                    remaining = fsc.get(cat["id"], {}).get("remaining", 0)
                    if remaining <= 0:
                        errors.append(f"No slots left for {cat['label']} today (cap: {fsc.get(cat['id'],{}).get('cap',0)}). Try next working day.")

                    if mob_clean and is_duplicate(fresh_q, lu, fu, mob_clean):
                        errors.append("You already have an active reservation today.")

                    if errors:
                        for e in errors:
                            st.error(f"❌ {e}")
                    else:
                        slot = next_slot_num(fresh_q)
                        rn = f"R-{today_mmdd()}-{slot:03d}"
                        ts = now_pht().isoformat()
                        entry = {
                            "id": gen_id(),
                            "queue_date": today_iso(),
                            "slot": slot,
                            "res_num": rn,
                            "last_name": lu,
                            "first_name": fu,
                            "mi": mi.strip().upper(),
                            "mobile": mob_clean,  # Stored as clean 11-digit
                            "service": svc["label"],
                            "service_id": svc["id"],
                            "category": cat["label"],
                            "category_id": cat["id"],
                            "cat_icon": cat["icon"],
                            "priority": "priority" if "Priority" in pri else "regular",
                            "status": "RESERVED",
                            "bqms_number": None,
                            "source": "ONLINE",
                            "issued_at": ts,
                        }
                        insert_queue_entry(entry)
                        st.session_state.ticket = entry
                        go("ticket")

# ═══════════════════════════════════════════════════
#  TICKET
# ═══════════════════════════════════════════════════
elif screen == "ticket":
    t = st.session_state.ticket
    if not t:
        go("home")
    else:
        st.markdown('<div style="text-align:center;"><span style="font-size:48px;">✅</span><h2 style="color:#22c55e;">Slot Reserved!</h2></div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="sss-card" style="border-top:4px solid #3399CC;text-align:center;">
            <img src="{SSS_LOGO}" width="32"
                 style="border-radius:6px;background:#fff;padding:2px;margin-bottom:4px;"
                 onerror="this.style.display='none'"/>
            <div style="font-size:11px;opacity:.5;letter-spacing:2px;">MABILISSS QUEUE — {branch.get('name','').upper()}</div>
            <div style="font-weight:700;margin:4px 0;">{t['category']} — {t['service']}</div>
            <hr style="border:1px dashed rgba(128,128,128,.2);"/>
            <div style="font-size:11px;opacity:.5;">RESERVATION NUMBER</div>
            <div class="sss-resnum">{t['res_num']}</div>
            <hr style="border:1px dashed rgba(128,128,128,.2);"/>
            <div style="font-size:12px;">{t['last_name']}, {t['first_name']} {t.get('mi','')}<br/>📱 {t['mobile']}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div class="sss-card" style="border-left:4px solid #0066A1;">
            <strong>📋 What to Do Next:</strong><br/><br/>
            <b>1.</b> Save your Reservation Number: <code style="font-size:16px;font-weight:900;">{t['res_num']}</code><br/>
            <b>2.</b> Go to <strong>{branch.get('name','')}</strong> during office hours (Mon-Fri, 8AM-5PM).<br/>
            <b>3.</b> Show your reservation to the guard → you'll get your <strong>official BQMS queue number</strong>.<br/>
            <b>4.</b> Tap <strong>"Track My Queue"</strong> anytime to check your position!<br/>
            <b>5.</b> Need to cancel? Track your queue and tap <strong>Cancel</strong>.
        </div>""", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.ticket = None
                go("home")
        with c2:
            if st.button("🔍 Track Now", use_container_width=True, type="primary"):
                st.session_state.tracked_id = t["id"]
                go("tracker")

# ═══════════════════════════════════════════════════
#  TRACK INPUT
# ═══════════════════════════════════════════════════
elif screen == "track_input":
    if st.button("← Back to Home"):
        go("home")
    st.markdown('<div style="text-align:center;"><span style="font-size:36px;">🔍</span><h3>Track Your Queue</h3></div>', unsafe_allow_html=True)
    st.caption("💡 Online = **R-** prefix (R-0215-001). Walk-in = **K-** prefix (K-0215-001).")

    track_mode = st.radio("Search by:", ["📱 Mobile Number", "#️⃣ Reservation Number"], horizontal=True)
    with st.form("track_form"):
        if "Mobile" in track_mode:
            track_val = st.text_input("Mobile number", placeholder="09171234567")
        else:
            track_val = st.text_input("Reservation #", placeholder="R-0215-005 or K-0215-001")

        if st.form_submit_button("🔍 Find My Queue", type="primary", use_container_width=True):
            fresh = get_queue_today()
            v = track_val.strip()
            if not v:
                st.error("Enter a value.")
            else:
                found = None
                if "Mobile" in track_mode:
                    v_clean = validate_mobile_ph(v) or v.strip()
                    # Prefer active entry, fall back to any
                    for r in fresh:
                        r_mob = r.get("mobile", "")
                        if r_mob == v_clean and r.get("status") not in TERMINAL:
                            found = r
                            break
                    if not found:
                        for r in fresh:
                            if r.get("mobile", "") == v_clean:
                                found = r
                                break
                else:
                    vu = v.upper()
                    for r in fresh:
                        if r.get("res_num") == vu and r.get("status") not in TERMINAL:
                            found = r
                            break
                    if not found:
                        for r in fresh:
                            if r.get("res_num") == vu:
                                found = r
                                break

                if not found:
                    st.error(f"❌ Not found for '{v}'. Check your input or try the other search method.")
                else:
                    st.session_state.tracked_id = found["id"]
                    go("tracker")

# ═══════════════════════════════════════════════════
#  TRACKER (with CANCEL option)
# ═══════════════════════════════════════════════════
elif screen == "tracker":
    tid = st.session_state.tracked_id
    fresh = get_queue_today()
    fbq = get_bqms_state()
    t = next((r for r in fresh if r.get("id") == tid), None)

    if not t:
        st.error("❌ Entry not found.")
        if st.button("← Try Again"):
            go("track_input")
    else:
        has_bqms = bool(t.get("bqms_number"))
        status = t.get("status", "")
        is_done = status == "COMPLETED"
        is_cancelled = status == "CANCELLED"
        is_void = status == "VOID"
        is_expired = status == "EXPIRED"
        is_terminal = status in TERMINAL
        is_srv = status == "SERVING"

        # ── Status banners ──
        if is_srv:
            st.markdown('<div class="sss-alert sss-alert-blue" style="font-size:18px;">🎉 <strong>YOU\'RE BEING SERVED!</strong></div>', unsafe_allow_html=True)
        elif is_done:
            st.markdown('<div class="sss-alert sss-alert-green">✅ <strong>Transaction Completed</strong> — Thank you for visiting SSS!</div>', unsafe_allow_html=True)
        elif is_cancelled:
            st.markdown('<div class="sss-alert sss-alert-yellow">🚫 <strong>Reservation Cancelled</strong> — Your slot has been released.</div>', unsafe_allow_html=True)
        elif is_void:
            st.markdown(f'<div class="sss-alert sss-alert-yellow">⚙️ <strong>Entry Voided</strong> — {t.get("void_reason","Administrative action")}.</div>', unsafe_allow_html=True)
        elif is_expired:
            st.markdown('<div class="sss-alert sss-alert-yellow">⏰ <strong>Reservation Expired</strong> — This was from a previous day.</div>', unsafe_allow_html=True)

        # ── Entry card ──
        status_color = "#22B8CF" if has_bqms else "#3399CC"
        st.markdown(f"""<div class="sss-card" style="border-top:4px solid {status_color};text-align:center;">
            <img src="{SSS_LOGO}" width="28"
                 style="border-radius:6px;background:#fff;padding:2px;margin-bottom:4px;"
                 onerror="this.style.display='none'"/>
            <div style="font-size:11px;opacity:.5;">{branch.get('name','').upper()}</div>
            <div style="font-weight:700;margin:4px 0;">{t.get('category','')} — {t.get('service','')}</div>
            <span style="display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;
                background:rgba(51,153,204,.15);color:#3399CC;">
                {STATUS_LABELS.get(status, status)}</span>
        </div>""", unsafe_allow_html=True)

        # ── BQMS and queue position ──
        if has_bqms:
            st.markdown(f'<div class="sss-card" style="text-align:center;"><div style="font-size:11px;opacity:.5;">YOUR BQMS NUMBER</div><div class="sss-bqms">{t["bqms_number"]}</div></div>', unsafe_allow_html=True)

            if not is_terminal:
                cat_obj = next((c for c in cats if c["id"] == t.get("category_id")), None)
                ns_val = fbq.get(t.get("category_id", ""), "")
                avg = cat_obj["avg_time"] if cat_obj else 10
                ahead = count_ahead(fresh, t)
                est = ahead * avg

                m1, m2 = st.columns(2)
                with m1:
                    ns_display = ns_val if ns_val else "—"
                    st.markdown(f'<div class="sss-metric"><div class="val" style="color:#22B8CF;">{ns_display}</div><div class="lbl">Now Serving</div></div>', unsafe_allow_html=True)
                with m2:
                    st.markdown(f'<div class="sss-metric"><div class="val">{t["bqms_number"]}</div><div class="lbl">Your Number</div></div>', unsafe_allow_html=True)

                m3, m4 = st.columns(2)
                with m3:
                    ahead_display = "You're Next!" if ahead == 0 else str(ahead)
                    ahead_color = "#22c55e" if ahead == 0 else "#f59e0b"
                    st.markdown(f'<div class="sss-metric"><div class="val" style="color:{ahead_color};">{ahead_display}</div><div class="lbl">Queue Ahead</div></div>', unsafe_allow_html=True)
                with m4:
                    if ahead == 0:
                        wt = "Any moment!"
                    elif est < 60:
                        wt = f"~{est} min"
                    else:
                        wt = f"~{est // 60}h {est % 60}m"
                    st.markdown(f'<div class="sss-metric"><div class="val">{wt}</div><div class="lbl">Est. Wait</div></div>', unsafe_allow_html=True)

                if not ns_val:
                    st.caption("💡 'Now Serving' updates automatically when staff processes entries.")
        else:
            if not is_terminal:
                st.markdown(f'<div class="sss-card" style="text-align:center;"><div style="font-size:11px;opacity:.5;">RESERVATION NUMBER</div><div class="sss-resnum">{t["res_num"]}</div></div>', unsafe_allow_html=True)
                st.markdown('<div class="sss-alert sss-alert-yellow">⏳ <strong>Waiting for BQMS Number</strong><br/>Staff will assign when you arrive at the branch. Auto-refreshes.</div>', unsafe_allow_html=True)

        # ── Action buttons ──
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Refresh", use_container_width=True, type="primary"):
                st.rerun()
        with c2:
            if st.button("🔍 Track Another", use_container_width=True):
                st.session_state.tracked_id = None
                go("track_input")

        # ── CANCEL BUTTON (member self-service) ──
        # Available for RESERVED and ARRIVED (before SERVING)
        if status in ("RESERVED", "ARRIVED"):
            st.markdown("---")
            st.markdown(f"""<div class="sss-card" style="border-left:4px solid #ef4444;">
                <strong>Need to cancel?</strong><br/>
                <span style="font-size:13px;opacity:.7;">
                Your slot will be released for other members. You may reserve again tomorrow.</span>
            </div>""", unsafe_allow_html=True)

            # Use session state for confirmation to avoid accidental cancels
            if f"confirm_cancel_{tid}" not in st.session_state:
                st.session_state[f"confirm_cancel_{tid}"] = False

            if not st.session_state[f"confirm_cancel_{tid}"]:
                if st.button("🚫 Cancel My Reservation", use_container_width=True):
                    st.session_state[f"confirm_cancel_{tid}"] = True
                    st.rerun()
            else:
                st.warning("⚠️ Are you sure? This cannot be undone.")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("✅ Yes, Cancel", type="primary", use_container_width=True):
                        cancel_entry(tid)
                        st.session_state[f"confirm_cancel_{tid}"] = False
                        st.rerun()
                with cc2:
                    if st.button("← Keep It", use_container_width=True):
                        st.session_state[f"confirm_cancel_{tid}"] = False
                        st.rerun()

        # ── Auto-refresh note ──
        if not is_terminal:
            st.caption(f"🔄 Auto-refreshes every 20s · Last: {now.strftime('%I:%M:%S %p')} PHT")

# ═══════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""<div style="text-align:center;font-size:10px;opacity:.3;padding:8px;">
    RPT / SSS Gingoog Branch · MabiliSSS Queue {VER}
</div>""", unsafe_allow_html=True)
