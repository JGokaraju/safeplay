"""SafePlay dashboard. Run: streamlit run monitor/app.py --server.address 0.0.0.0"""
import hmac
import os

import streamlit as st

from core import Monitor

st.set_page_config(page_title="SafePlay", page_icon="🛝", layout="centered")


@st.cache_resource
def get_monitor():
    m = Monitor()
    m.start()  # background poller lives once per server process, not per rerun
    return m


# Optional password gate: these buttons can text the parent, so protect them when exposed.
pw = os.getenv("DASHBOARD_PASSWORD")
if pw and not st.session_state.get("authed"):
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(entered, pw):
            st.session_state["authed"] = True
            st.rerun()
        st.error("Wrong password")
    st.stop()

mon = get_monitor()
st.title("🛝 SafePlay Monitor")


def run(label, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        st.toast(label)
    except Exception as e:
        st.error(f"{label} failed: {e}")


if st.button("📸 Take Photo Now", use_container_width=True, type="primary"):
    run("Photo requested", mon.request_capture)

st.subheader("Simulate situations")
bypass = st.toggle("Bypass SMS cooldown", value=True)
c1, c2 = st.columns(2)
if c1.button("🚑 Simulate injury", use_container_width=True):
    run("Injury simulated", mon.handle_injury, "Simulated injury (demo).", bypass)
if c2.button("⚠️ Simulate horseplay", use_container_width=True):
    run("Horseplay simulated", mon.handle_horseplay)


@st.fragment(run_every=3)
def live():
    if mon.last_verdict:
        t, status, reason = mon.last_verdict
        msg = f"**{status.upper()}** at {t:%H:%M:%S} — {reason}"
        {"injured": st.error, "dangerous": st.warning}.get(status, st.success)(msg)
    if mon.last_image:
        st.image(mon.last_image, caption="Last analyzed image", use_container_width=True)
    st.subheader("Event log")
    st.code("\n".join(reversed(list(mon.events))) or "No events yet", language=None)


live()
