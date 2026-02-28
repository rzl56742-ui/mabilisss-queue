"""
═══════════════════════════════════════════════════════════
 MabiliSSS Queue — Member Portal V2.3.0-P2 (Public)
 © RPTayo / SSS-MND 2026
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
    count_arrived_in_category, count_reserved_position, calc_est_wait,
    get_category_groups, get_services_for_category,
    is_reservation_open, format_time_12h, get_logo,
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
for k, v in {"screen": "home", "sel_group": None, "sel_cat": None,
             "sel_svc": None, "ticket": None, "tracked_id": None}.items():
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
if screen in ("home", "select_cat", "select_lane", "select_svc", "member_form"):
    load_queue_data()
if screen == "tracker":
    load_queue_data()
    load_bqms_data()

o_stat = branch.get("o_stat", "online")
is_open = o_stat != "offline"

# Dynamic logo: use branch config if set, fallback to default
logo_url = get_logo(branch)

# ═══════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════
st.markdown(f"""<div class="sss-header">
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="display:flex;align-items:center;gap:12px;">
            <img src="{logo_url}" width="44" height="44"
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

# ── Persistent 🏠 Home button (every screen except home) ──
if screen != "home":
    if st.button("🏠 Home", key="nav_home"):
        go("home")

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

    # V2.3.0-P2: Reservation time gate
    res_open, res_msg = is_reservation_open(branch)
    can_reserve = is_open and res_open

    with c1:
        if st.button("📋 Reserve a Slot", use_container_width=True, type="primary", disabled=not can_reserve):
            st.session_state.sel_group = None
            st.session_state.sel_cat = None
            st.session_state.sel_svc = None
            go("select_cat")
    with c2:
        if st.button("🔍 Track My Queue", use_container_width=True):
            st.session_state.tracked_id = None
            go("track_input")

    if not is_open:
        st.warning("🔴 Reservation is currently closed.")
    elif not res_open:
        # Show reservation hours info
        open_t = format_time_12h(branch.get("reservation_open_time", "06:00") or "06:00")
        close_t = format_time_12h(branch.get("reservation_close_time", "17:00") or "17:00")
        st.markdown(f"""<div class="sss-alert sss-alert-yellow" style="font-size:13px;">
            <strong>🕐 {res_msg}</strong><br/>
            Online reservations: <b>{open_t} – {close_t}</b>
        </div>""", unsafe_allow_html=True)
    if branch.get("test_mode"):
        st.markdown('<div class="sss-alert sss-alert-blue" style="font-size:11px;">🧪 TEST MODE — Time restrictions bypassed</div>', unsafe_allow_html=True)

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
#  SELECT CATEGORY — V2.3.0-P2: Group-based flow
# ═══════════════════════════════════════════════════
elif screen == "select_cat":
    if st.button("← Back to Home"):
        go("home")
    st.subheader("Step 1: Choose Transaction")

    groups = get_category_groups(cats)

    for grp in groups:
        # Calculate combined remaining for all lanes in group
        total_rem = 0
        total_cap = 0
        for lane_cat in grp["lanes"]:
            s = sc.get(lane_cat["id"], {"remaining": lane_cat.get("cap", 50), "cap": lane_cat.get("cap", 50)})
            total_rem += s["remaining"]
            total_cap += s["cap"]

        full = total_rem <= 0
        gicon = grp["group_icon"] or (grp["lanes"][0]["icon"] if grp["lanes"] else "📋")
        glabel = grp["group_label"]

        c1, c2 = st.columns([5, 1])
        with c1:
            btn_label = f"{gicon} {glabel}"
            if st.button(btn_label, key=f"grp_{grp['group_id']}", disabled=full, use_container_width=True):
                if grp["is_single"] or len(grp["lanes"]) == 1:
                    # Single lane — skip lane selection, go straight to service
                    st.session_state.sel_group = grp["group_id"]
                    st.session_state.sel_cat = grp["lanes"][0]["id"]
                    go("select_svc")
                else:
                    # Paired lanes — go to lane selection
                    st.session_state.sel_group = grp["group_id"]
                    go("select_lane")
        with c2:
            if full:
                st.markdown('<div style="text-align:center;"><span style="font-size:12px;font-weight:900;color:#ef4444;">FULL</span></div>', unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center;'><span style='font-size:20px;font-weight:900;color:#3399CC;'>{total_rem}</span><br/><span style='font-size:10px;opacity:.5;'>left</span></div>", unsafe_allow_html=True)

        # Show group description (from first lane that has one)
        desc = ""
        for lane_cat in grp["lanes"]:
            if lane_cat.get("description"):
                desc = lane_cat["description"]
                break
        if desc:
            st.caption(f"ℹ️ {desc}")

    all_full = all(
        sum(sc.get(lc["id"], {}).get("remaining", 0) for lc in g["lanes"]) <= 0
        for g in groups
    )
    if all_full:
        open_t = format_time_12h(branch.get("reservation_open_time", "06:00") or "06:00")
        st.markdown(f"""<div class="sss-alert sss-alert-red" style="font-size:14px;">
            <strong>⚠️ All slots for today are full.</strong><br/>
            Please try again on the next working day starting at {open_t}.
            <br/><br/>Thank you for your patience!
        </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
#  SELECT LANE (Regular vs Courtesy) — V2.3.0-P2
# ═══════════════════════════════════════════════════
elif screen == "select_lane":
    sel_grp_id = st.session_state.sel_group
    if not sel_grp_id:
        go("select_cat")
    else:
        # Find all lanes for this group
        grp_cats = [c for c in cats if c.get("group_id") == sel_grp_id]
        if not grp_cats:
            st.error("Group not found.")
            if st.button("← Back"):
                go("select_cat")
        else:
            if st.button("← Back"):
                go("select_cat")

            gicon = grp_cats[0].get("group_icon") or grp_cats[0]["icon"]
            glabel = grp_cats[0].get("group_label") or grp_cats[0]["label"]
            st.subheader(f"Step 2: {gicon} {glabel}")
            st.markdown("Choose your lane:")

            # Sort: regular first, then courtesy
            lane_order = {"regular": 0, "courtesy": 1, "single": 2}
            grp_cats.sort(key=lambda c: lane_order.get(c.get("lane_type", "single"), 9))

            for lcat in grp_cats:
                lt = lcat.get("lane_type", "single")
                s = sc.get(lcat["id"], {"remaining": lcat.get("cap", 50), "cap": lcat.get("cap", 50)})
                full = s["remaining"] <= 0

                if lt == "courtesy":
                    lane_icon = "⭐"
                    lane_label = "Courtesy Lane"
                    lane_note = "Senior Citizens (60+) · PWD · Pregnant Women"
                elif lt == "regular":
                    lane_icon = "👤"
                    lane_label = "Regular Lane"
                    lane_note = "General members"
                else:
                    lane_icon = lcat["icon"]
                    lane_label = lcat["label"]
                    lane_note = lcat.get("description", "")

                c1, c2 = st.columns([5, 1])
                with c1:
                    if st.button(f"{lane_icon} {lane_label}", key=f"lane_{lcat['id']}",
                                 disabled=full, use_container_width=True):
                        st.session_state.sel_cat = lcat["id"]
                        go("select_svc")
                with c2:
                    if full:
                        st.markdown('<div style="text-align:center;"><span style="font-size:12px;font-weight:900;color:#ef4444;">FULL</span></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='text-align:center;'><span style='font-size:20px;font-weight:900;color:#3399CC;'>{s['remaining']}</span><br/><span style='font-size:10px;opacity:.5;'>left</span></div>", unsafe_allow_html=True)

                if lane_note:
                    st.caption(f"ℹ️ {lane_note}")

            # Courtesy lane verification note
            has_courtesy = any(c.get("lane_type") == "courtesy" for c in grp_cats)
            if has_courtesy:
                st.markdown("""<div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);
                    border-radius:8px;padding:10px 14px;margin-top:8px;font-size:12px;">
                    ⚠️ <b>Courtesy Lane</b> is reserved for Senior Citizens (60+), PWD, and Pregnant Women.
                    You will be asked to present valid proof at the counter.
                </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════
#  SELECT SERVICE — V2.3.0-P2: Courtesy inherits from Regular
# ═══════════════════════════════════════════════════
elif screen == "select_svc":
    sel_cat_id = st.session_state.sel_cat
    if not sel_cat_id:
        go("select_cat")
    else:
        cat = next((c for c in cats if c["id"] == sel_cat_id), None)
        if not cat:
            st.error("Category not found. It may have been removed.")
            if st.button("← Back"):
                go("select_cat")
        else:
            # Back button: go to lane selection if grouped, else to group selection
            has_group = bool(cat.get("group_id"))
            grp_lanes = [c for c in cats if c.get("group_id") == cat.get("group_id")] if has_group else []
            back_screen = "select_lane" if has_group and len(grp_lanes) > 1 else "select_cat"
            if st.button("← Back"):
                go(back_screen)

            # Re-check cap with fresh data
            fresh_q = get_queue_today()
            fsc = slot_counts(cats, fresh_q)
            s = fsc.get(cat["id"], {"remaining": 0, "cap": cat.get("cap", 50)})

            if s["remaining"] <= 0:
                open_t = format_time_12h(branch.get("reservation_open_time", "06:00") or "06:00")
                st.markdown(f"""<div class="sss-alert sss-alert-red" style="font-size:14px;">
                    <strong>⚠️ No available slots for {cat['icon']} {cat['label']} today.</strong><br/>
                    Daily limit of <b>{s['cap']}</b> has been reached.<br/><br/>
                    Please try again on the next working day starting at {open_t}.
                </div>""", unsafe_allow_html=True)
            else:
                lt = cat.get("lane_type", "single")
                step_num = "Step 3" if has_group and len(grp_lanes) > 1 else "Step 2"
                lane_badge = " ⭐ Courtesy" if lt == "courtesy" else (" 👤 Regular" if lt == "regular" else "")
                st.subheader(f"{step_num}: Choose Service")
                st.markdown(f"**{cat['icon']} {cat.get('short_label', cat['label'])}{lane_badge}**")
                st.caption(f"Slots remaining: {s['remaining']} of {s['cap']}")

                if cat.get("description"):
                    st.caption(f"ℹ️ {cat['description']}")

                # Get services (courtesy inherits from paired regular)
                svcs_list = get_services_for_category(cats, cat)
                if not svcs_list:
                    st.info("No specific services configured. Please contact branch staff.")
                for svc in svcs_list:
                    svc_desc = svc.get("description", "")
                    btn_text = f"● {svc['label']}"
                    if st.button(btn_text, key=f"svc_{svc['id']}", use_container_width=True):
                        st.session_state.sel_svc = svc["id"]
                        go("member_form")
                    if svc_desc:
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;ℹ️ {svc_desc}")

# ═══════════════════════════════════════════════════
#  MEMBER FORM — V2.3.0-P2
# ═══════════════════════════════════════════════════
elif screen == "member_form":
    sel_cat_id = st.session_state.sel_cat
    sel_svc_id = st.session_state.sel_svc
    if not sel_cat_id or not sel_svc_id:
        go("select_cat")
    else:
        cat = next((c for c in cats if c["id"] == sel_cat_id), None)
        # Find service using inheritance-aware lookup
        svcs_list = get_services_for_category(cats, cat) if cat else []
        svc = next((s for s in svcs_list if s["id"] == sel_svc_id), None)
        if not cat or not svc:
            st.error("Selection not found. Please start over.")
            if st.button("← Start Over"):
                go("select_cat")
        else:
            if st.button("← Back"):
                go("select_svc")

            lt = cat.get("lane_type", "single")
            has_group = bool(cat.get("group_id"))
            grp_lanes = [c for c in cats if c.get("group_id") == cat.get("group_id")] if has_group else []
            step_num = "Step 4" if has_group and len(grp_lanes) > 1 else "Step 3"
            st.subheader(f"{step_num}: Your Details")

            lane_badge = ""
            if lt == "courtesy":
                lane_badge = " · ⭐ Courtesy Lane"
            elif lt == "regular":
                lane_badge = " · 👤 Regular Lane"

            st.markdown(f'<div class="sss-card">{cat["icon"]} <strong>{svc["label"]}</strong><br/><span style="opacity:.6;">{cat["label"]}{lane_badge}</span></div>', unsafe_allow_html=True)

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

                # Priority: auto-set from lane type, or show radio for single-lane categories
                pri_value = "regular"
                pri_confirmed = True

                if lt == "courtesy":
                    # Auto-priority: user already chose Courtesy Lane
                    pri_value = "priority"
                    st.markdown("""<div style="background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
                        border-radius:8px;padding:10px 14px;margin:6px 0;font-size:12px;">
                        ⭐ <b>Courtesy Lane — Verification Required</b><br/><br/>
                        Reserved for: 👴 <b>Senior Citizens</b> (60+) · ♿ <b>PWD</b> · 🤰 <b>Pregnant Women</b><br/><br/>
                        📋 Please present <b>valid proof at the counter</b>:<br/>
                        &nbsp;&nbsp;• Senior Citizen ID or gov't ID showing date of birth<br/>
                        &nbsp;&nbsp;• PWD ID<br/>
                        &nbsp;&nbsp;• Medical certificate or visible evidence of pregnancy<br/><br/>
                        ❌ <b>If you cannot present valid proof, you will be moved to the Regular Lane</b>
                        and your queue position will be adjusted.
                    </div>""", unsafe_allow_html=True)
                    pri_confirmed = st.checkbox("✅ I qualify and will present proof at the counter.", key="pri_confirm")

                elif lt == "single":
                    # Single-lane category: behavior depends on branch priority_lane_mode
                    plm = branch.get("priority_lane_mode", "integrated")
                    if plm == "integrated":
                        # Integrated: show priority radio — priority gets lower BQMS # in same queue
                        pri = st.radio("Lane:", ["👤 Regular", "⭐ Priority (Senior/PWD/Pregnant)"], horizontal=True)
                        if "Priority" in pri:
                            pri_value = "priority"
                            st.markdown("""<div style="background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.3);
                                border-radius:8px;padding:10px 14px;margin:6px 0;font-size:12px;">
                                ⚠️ <b>Priority Lane — Verification Required</b><br/><br/>
                                Reserved for: 👴 <b>Senior Citizens</b> (60+) · ♿ <b>PWD</b> · 🤰 <b>Pregnant Women</b><br/><br/>
                                📋 You will be asked to present <b>valid proof at the counter</b>.<br/><br/>
                                ❌ <b>If you cannot present valid proof, you will be moved to the Regular Lane.</b>
                            </div>""", unsafe_allow_html=True)
                            pri_confirmed = st.checkbox("✅ I qualify and will present proof at the counter.", key="pri_confirm_s")
                    else:
                        # Separate: no radio — inform the guard at the branch for priority routing
                        st.caption("💡 Senior Citizens, PWD, and Pregnant Women: Please inform the guard at the branch for priority accommodation.")
                # For "regular" lane_type, no radio needed — always regular

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

                    mob_clean = validate_mobile_ph(mob_raw)
                    if not mob_raw:
                        errors.append("Mobile number required.")
                    elif not mob_clean:
                        errors.append("Invalid mobile. Use 09XX format (11 digits).")

                    if not consent:
                        errors.append("Check privacy consent.")

                    if pri_value == "priority" and not pri_confirmed:
                        errors.append("Please confirm you qualify for the Courtesy/Priority Lane.")

                    # Fresh cap check
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
                            "mobile": mob_clean,
                            "service": svc["label"],
                            "service_id": svc["id"],
                            "category": cat["label"],
                            "category_id": cat["id"],
                            "cat_icon": cat["icon"],
                            "priority": pri_value,
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
            <img src="{logo_url}" width="32"
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
            <b>2.</b> Go to <strong>{branch.get('name','')}</strong> during office hours ({branch.get('hours','Mon-Fri, 8AM-5PM')}).<br/>
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
            <img src="{logo_url}" width="28"
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
                ahead = count_ahead(fresh, t)

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
                    # V2.3.0: Improved estimated wait (range, actual speed)
                    if ahead == 0:
                        wt = "Any moment!"
                        wt_note = ""
                    else:
                        est_low, est_high, est_src = calc_est_wait(fresh, t, cats)
                        if est_low is not None and est_high is not None:
                            if est_high < 60:
                                wt = f"~{est_low}–{est_high} min"
                            else:
                                wt = f"~{est_low // 60}h{est_low % 60}m–{est_high // 60}h{est_high % 60}m"
                            wt_note = "today's speed" if est_src == "today" else "typical speed"
                        else:
                            avg = cat_obj["avg_time"] if cat_obj else 10
                            est = ahead * avg
                            wt = f"~{est} min" if est < 60 else f"~{est // 60}h {est % 60}m"
                            wt_note = "estimate"
                    st.markdown(f'<div class="sss-metric"><div class="val">{wt}</div><div class="lbl">Est. Wait</div></div>', unsafe_allow_html=True)

                # V2.3.0: Wait time disclaimer
                if ahead > 0:
                    st.caption("⏱ Estimate based on today's average service speed. Actual wait may vary.")

                if not ns_val:
                    st.caption("💡 'Now Serving' updates automatically when staff processes entries.")
        else:
            # ── V2.3.0: PRE-8AM TRACKER (no BQMS yet) ──
            if not is_terminal:
                st.markdown(f'<div class="sss-card" style="text-align:center;"><div style="font-size:11px;opacity:.5;">RESERVATION NUMBER</div><div class="sss-resnum">{t["res_num"]}</div></div>', unsafe_allow_html=True)

                cat_id = t.get("category_id", "")
                at_branch = count_arrived_in_category(fresh, cat_id)
                my_pos = count_reserved_position(fresh, t)
                is_arrived = t.get("status") == "ARRIVED"
                batch_time = branch.get("batch_assign_time", "08:00")

                if is_arrived:
                    # Member is at the branch, checked in, waiting for batch assign
                    st.markdown(f"""<div class="sss-alert sss-alert-green">
                        ✅ <strong>You're checked in!</strong><br/>
                        BQMS numbers will be assigned at <b>{batch_time} AM</b>.<br/>
                        You are among <b>{at_branch} members</b> at the branch for this category.
                    </div>""", unsafe_allow_html=True)
                else:
                    # Member reserved online, not yet at branch
                    m1, m2 = st.columns(2)
                    with m1:
                        at_color = "#f59e0b" if at_branch > 0 else "#22c55e"
                        st.markdown(f'<div class="sss-metric"><div class="val" style="color:{at_color};">🏢 {at_branch}</div><div class="lbl">At Branch</div></div>', unsafe_allow_html=True)
                    with m2:
                        st.markdown(f'<div class="sss-metric"><div class="val" style="color:#3399CC;">📱 #{my_pos}</div><div class="lbl">Online Pos</div></div>', unsafe_allow_html=True)

                    st.markdown(f"""<div class="sss-alert sss-alert-yellow">
                        ⏳ <strong>Waiting for BQMS Number</strong><br/>
                        Your queue number will be assigned at <b>{batch_time} AM</b> when the branch opens.<br/>
                        <span style="font-size:12px;opacity:.8;">You are online reservation <b>#{my_pos}</b> for this category. No need to rush — your slot is secured!</span>
                    </div>""", unsafe_allow_html=True)

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
    RPTayo / SSS-MND · MabiliSSS Queue {VER}
</div>""", unsafe_allow_html=True)
