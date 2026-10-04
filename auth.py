"""
Local login / registration for the Streamlit app.

- Users are stored in data/users.db (SQLite), separate from the demo databases.
- Passwords are never stored as plain text: PBKDF2-SHA256 + random salt (standard library only).
- Usage in app.py:  apply_style(); require_login() ... see app.py.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time

import streamlit as st

USERS_DB = "data/users.db"
ITERATIONS = 200_000
MAX_FAILS = 5
LOCK_SECONDS = 30


# ---------------- database ----------------

def _conn():
    os.makedirs(os.path.dirname(USERS_DB), exist_ok=True)
    c = sqlite3.connect(USERS_DB)
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    return c


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()


def register_user(username, email, password, confirm):
    username, email = username.strip(), email.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Please enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if password != confirm:
        return False, "Passwords do not match."
    salt = secrets.token_bytes(16)
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO users (username, email, salt, pw_hash) VALUES (?,?,?,?)",
                (username, email, salt.hex(), _hash(password, salt)),
            )
    except sqlite3.IntegrityError:
        return False, "That username or email is already registered."
    return True, "Account created. You can log in now."


def check_login(identifier, password):
    """identifier = username or email. Returns username on success, else None."""
    with _conn() as c:
        row = c.execute(
            "SELECT username, salt, pw_hash FROM users WHERE username=? OR email=?",
            (identifier.strip(), identifier.strip()),
        ).fetchone()
    if not row:
        return None
    username, salt, stored = row
    if hmac.compare_digest(_hash(password, bytes.fromhex(salt)), stored):
        return username
    return None


# ---------------- styling ----------------

_COMMON = """
#MainMenu, footer {visibility: hidden;}
@keyframes ombre {0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%}}
@keyframes rise {from{opacity:0; transform:translateY(28px) scale(.97)} to{opacity:1; transform:none}}
@keyframes floaty {0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)}}
@keyframes sheen {0%{transform:translateX(-130%) skewX(-20deg)} 60%,100%{transform:translateX(230%) skewX(-20deg)}}
@keyframes blob1 {0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(90px,70px) scale(1.25)}}
@keyframes blob2 {0%,100%{transform:translate(0,0) scale(1.1)} 50%{transform:translate(-100px,-60px) scale(.9)}}
@keyframes textshine {to{background-position:200% center}}
.stButton > button, div[data-testid="stFormSubmitButton"] button {
    position: relative; overflow: hidden; border: none; border-radius: 14px; font-weight: 600;
    color: #fff; background: linear-gradient(120deg,#2563eb,#7c3aed,#dc2626,#f97316);
    background-size: 250% 250%; animation: ombre 6s ease infinite;
    transition: transform .25s cubic-bezier(.34,1.56,.64,1), box-shadow .25s;
    box-shadow: 0 6px 20px rgba(168,85,247,.35);}
.stButton > button::after, div[data-testid="stFormSubmitButton"] button::after {
    content:""; position:absolute; top:0; left:0; width:40%; height:100%;
    background: linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);
    animation: sheen 3.5s ease-in-out infinite;}
.stButton > button:hover, div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-4px) scale(1.04); color:#fff; box-shadow: 0 14px 34px rgba(249,115,22,.5);}
.stButton > button:active, div[data-testid="stFormSubmitButton"] button:active {transform: scale(.96);}
"""

_LOGIN = """
.stApp {
    background: linear-gradient(-45deg,#0f172a,#3730a3,#7c3aed,#dc2626,#f97316,#0284c7,#0f172a);
    background-size: 500% 500%; animation: ombre 20s ease infinite; color:#fff;}
[data-testid="stHeader"] {background: transparent;}
[data-testid="stAppViewContainer"]::before, [data-testid="stAppViewContainer"]::after {
    content:""; position:fixed; border-radius:50%; filter: blur(70px); pointer-events:none; z-index:0;}
[data-testid="stAppViewContainer"]::before {
    width:420px; height:420px; top:-90px; left:-90px;
    background: radial-gradient(circle,#f97316,transparent 70%); animation: blob1 14s ease-in-out infinite;}
[data-testid="stAppViewContainer"]::after {
    width:480px; height:480px; bottom:-120px; right:-100px;
    background: radial-gradient(circle,#38bdf8,transparent 70%); animation: blob2 17s ease-in-out infinite;}
.block-container {position:relative; z-index:1; padding-top:2rem; max-width:620px;}
.auth-hero {text-align:center; margin:1rem 0 1.4rem; animation: rise .9s ease both;}
.auth-logo {font-size:3.4rem; display:inline-block; animation: floaty 3.2s ease-in-out infinite;
    filter: drop-shadow(0 8px 18px rgba(0,0,0,.35));}
.auth-hero h1 {margin:.3rem 0 .4rem; font-weight:800; letter-spacing:-.5px; font-size:2rem;
    background: linear-gradient(90deg,#fff,#fed7aa,#fde68a,#a5f3fc,#ddd6fe,#fff); background-size:200% auto;
    -webkit-background-clip:text; background-clip:text; color:transparent;
    animation: textshine 6s linear infinite;}
.auth-hero p {color: rgba(255,255,255,.8); margin:0;}
div[data-testid="stForm"] {
    position:relative; overflow:hidden; padding:1.8rem; border-radius:28px;
    background: linear-gradient(135deg, rgba(255,255,255,.22), rgba(255,255,255,.06));
    backdrop-filter: blur(24px) saturate(170%); -webkit-backdrop-filter: blur(24px) saturate(170%);
    border: 1px solid rgba(255,255,255,.38);
    box-shadow: 0 18px 50px rgba(0,0,0,.32), inset 0 1.5px 0 rgba(255,255,255,.65),
                inset 0 -1.5px 0 rgba(255,255,255,.12), inset 0 0 40px rgba(255,255,255,.06);
    animation: rise .8s .15s ease both;}
div[data-testid="stForm"]::before {
    content:""; position:absolute; top:0; left:0; width:35%; height:100%; pointer-events:none;
    background: linear-gradient(90deg,transparent,rgba(255,255,255,.18),transparent);
    animation: sheen 7s ease-in-out infinite;}
.stTabs [data-baseweb="tab-list"] {
    gap:6px; padding:5px; border-radius:18px; background: rgba(255,255,255,.14);
    backdrop-filter: blur(14px); border:1px solid rgba(255,255,255,.25); animation: rise .8s .1s ease both;}
.stTabs [data-baseweb="tab"] {border-radius:13px; color:rgba(255,255,255,.8); flex:1; justify-content:center;
    transition: all .3s;}
.stTabs [aria-selected="true"] {background: rgba(255,255,255,.3); color:#fff; box-shadow: 0 4px 14px rgba(0,0,0,.18);}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display:none;}
label, label p, .stTextInput label p {color:#fff !important; font-weight:500;}
div[data-baseweb="input"], div[data-baseweb="base-input"] {
    background: rgba(255,255,255,.16) !important; border-radius:14px !important;
    border: 1px solid rgba(255,255,255,.3) !important; transition: all .25s;}
div[data-baseweb="input"]:focus-within {
    border-color:#fff !important; box-shadow: 0 0 0 3px rgba(255,255,255,.25), 0 0 24px rgba(249,115,22,.5);
    transform: translateY(-2px);}
.stTextInput input {color:#fff !important; -webkit-text-fill-color:#fff;}
.stTextInput input::placeholder {color: rgba(255,255,255,.55) !important; -webkit-text-fill-color: rgba(255,255,255,.55);}
.stTextInput button {color:#fff;}
div[data-testid="stFormSubmitButton"] button {padding:.7rem 0; font-size:1.05rem; animation: ombre 6s ease infinite, floaty 3s ease-in-out infinite;}
div[data-testid="stAlert"] {border-radius:16px; backdrop-filter: blur(12px); animation: rise .5s ease both;}
"""

_APP = """
.block-container {padding-top:2rem; max-width:1150px; animation: rise .6s ease both;}
h1 {font-weight:800; letter-spacing:-.5px;
    background: linear-gradient(90deg,#2563eb,#7c3aed,#dc2626,#f97316,#2563eb); background-size:200% auto;
    -webkit-background-clip:text; background-clip:text; color:transparent; animation: textshine 6s linear infinite;}
div[data-testid="stMetric"] {
    padding:16px 20px; border-radius:20px; border:1px solid rgba(168,85,247,.3);
    background: linear-gradient(135deg, rgba(37,99,235,.14), rgba(249,115,22,.12));
    backdrop-filter: blur(14px); box-shadow: 0 8px 24px rgba(99,102,241,.15), inset 0 1px 0 rgba(255,255,255,.4);
    transition: transform .3s cubic-bezier(.34,1.56,.64,1);}
div[data-testid="stMetric"]:hover {transform: translateY(-5px) scale(1.02);}
div[data-testid="stExpander"] {border-radius:18px; border:1px solid rgba(168,85,247,.25); backdrop-filter: blur(10px);}
.stTextInput div[data-baseweb="input"] {border-radius:14px; transition: all .25s;}
.stTextInput div[data-baseweb="input"]:focus-within {box-shadow: 0 0 0 3px rgba(168,85,247,.3), 0 0 22px rgba(249,115,22,.35);}
div[data-testid="stAlert"] {border-radius:16px; animation: rise .5s ease both;}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(37,99,235,.14), rgba(249,115,22,.08)); backdrop-filter: blur(14px);}
"""


def apply_style():
    """Animated glass/ombre theme. Login page and the main app get different looks."""
    css = _COMMON + (_APP if st.session_state.get("user") else _LOGIN)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ---------------- pages ----------------

def _login_page():
    st.markdown(
        '<div class="auth-hero"><div class="auth-logo">🗄️</div><h1>Agentic Enterprise Database QA</h1>'
        "<p>Sign in to ask questions about your database in plain English.</p></div>",
        unsafe_allow_html=True,
    )
    if True:
        tab_login, tab_reg = st.tabs(["🔑 Login", "📝 Register"])

        with tab_login:
            with st.form("login_form"):
                ident = st.text_input("Username or email")
                pw = st.text_input("Password", type="password")
                go = st.form_submit_button("Log in", type="primary", use_container_width=True)
            if go:
                wait = st.session_state.get("lock_until", 0) - time.time()
                if wait > 0:
                    st.error(f"Too many attempts. Try again in {int(wait)+1}s.")
                elif not ident or not pw:
                    st.warning("Enter your username/email and password.")
                else:
                    user = check_login(ident, pw)
                    if user:
                        st.session_state.user = user
                        st.session_state.fails = 0
                        st.rerun()
                    else:
                        st.session_state.fails = st.session_state.get("fails", 0) + 1
                        if st.session_state.fails >= MAX_FAILS:
                            st.session_state.lock_until = time.time() + LOCK_SECONDS
                            st.session_state.fails = 0
                        st.error("Incorrect username/email or password.")

        with tab_reg:
            with st.form("register_form"):
                u = st.text_input("Username")
                e = st.text_input("Email")
                p1 = st.text_input("Password (min 8 characters)", type="password")
                p2 = st.text_input("Confirm password", type="password")
                go = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if go:
                ok, msg = register_user(u, e, p1, p2)
                (st.success if ok else st.error)(msg)


def require_login():
    """Show the login page and stop the script unless the user is logged in."""
    if not st.session_state.get("user"):
        _login_page()
        st.stop()


def sidebar_user():
    """Greeting + logout button at the top of the sidebar."""
    st.sidebar.markdown(f"👤 Signed in as **{st.session_state.user}**")
    if st.sidebar.button("Log out", use_container_width=True):
        st.session_state.clear()
        st.rerun()