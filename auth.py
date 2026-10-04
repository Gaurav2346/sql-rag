import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from email_service import send_password_reset_email


# ============================================================
# CONFIG
# ============================================================

USERS_DB = "data/users.db"

ITERATIONS = 200_000

MAX_FAILS = 5
LOCK_SECONDS = 30

OTP_EXPIRY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5
OTP_RESEND_SECONDS = 60


# ============================================================
# DATABASE
# ============================================================

def _conn():
    os.makedirs(
        os.path.dirname(USERS_DB),
        exist_ok=True,
    )

    conn = sqlite3.connect(USERS_DB)

    # Users table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Password reset table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            otp_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER DEFAULT 0,
            verified_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
            REFERENCES users(id)
        )
        """
    )

    return conn


# ============================================================
# PASSWORD HASHING
# ============================================================

def _hash(
    password: str,
    salt: bytes,
) -> str:

    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    ).hex()


# ============================================================
# REGISTER
# ============================================================

def register_user(
    username,
    email,
    password,
    confirm,
):
    username = username.strip()
    email = email.strip()

    if len(username) < 3:
        return (
            False,
            "Username must be at least 3 characters.",
        )

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email,
    ):
        return (
            False,
            "Please enter a valid email address.",
        )

    if len(password) < 8:
        return (
            False,
            "Password must be at least 8 characters.",
        )

    if password != confirm:
        return (
            False,
            "Passwords do not match.",
        )

    salt = secrets.token_bytes(16)

    try:

        with _conn() as conn:

            conn.execute(
                """
                INSERT INTO users
                (
                    username,
                    email,
                    salt,
                    pw_hash
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    email,
                    salt.hex(),
                    _hash(password, salt),
                ),
            )

    except sqlite3.IntegrityError:

        return (
            False,
            "That username or email is already registered.",
        )

    return (
        True,
        "Account created. You can log in now.",
    )


# ============================================================
# LOGIN
# ============================================================

def check_login(
    identifier,
    password,
):
    """
    identifier can be username or email.
    Returns username on successful login.
    """

    identifier = identifier.strip()

    with _conn() as conn:

        row = conn.execute(
            """
            SELECT
                username,
                salt,
                pw_hash
            FROM users
            WHERE username = ?
               OR email = ?
            """,
            (
                identifier,
                identifier,
            ),
        ).fetchone()

    if not row:
        return None

    username, salt, stored_hash = row

    calculated_hash = _hash(
        password,
        bytes.fromhex(salt),
    )

    if hmac.compare_digest(
        calculated_hash,
        stored_hash,
    ):
        return username

    return None


# ============================================================
# OTP
# ============================================================

def generate_otp():
    """
    Generate a secure 6-digit OTP.
    """

    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp):
    """
    Hash OTP before storing it.
    """

    return hashlib.sha256(
        otp.encode("utf-8")
    ).hexdigest()


# ============================================================
# REQUEST PASSWORD RESET
# ============================================================

def request_password_reset(email):

    email = email.strip()

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email,
    ):
        return (
            False,
            "Please enter a valid email address.",
        )

    with _conn() as conn:

        # ----------------------------------------------------
        # Find user
        # ----------------------------------------------------

        user = conn.execute(
            """
            SELECT
                id,
                email
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        # Don't reveal whether email exists
        if not user:

            return (
                True,
                "If this email is registered, "
                "a password reset OTP has been sent.",
            )

        user_id = user[0]

        # ----------------------------------------------------
        # Check resend cooldown
        # ----------------------------------------------------

        previous = conn.execute(
            """
            SELECT created_at
            FROM password_resets
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if previous:

            try:

                previous_time = datetime.fromisoformat(
                    previous[0]
                )

                now = datetime.now(
                    timezone.utc
                ).replace(
                    tzinfo=None
                )

                elapsed = (
                    now - previous_time
                ).total_seconds()

                if elapsed < OTP_RESEND_SECONDS:

                    remaining = int(
                        OTP_RESEND_SECONDS
                        - elapsed
                    )

                    return (
                        False,
                        f"Please wait {remaining} "
                        "seconds before requesting "
                        "another OTP.",
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # Generate OTP
        # ----------------------------------------------------

        otp = generate_otp()

        otp_hash = hash_otp(otp)

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=OTP_EXPIRY_MINUTES
            )
        ).isoformat()

        # ----------------------------------------------------
        # Invalidate previous reset requests
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE password_resets
            SET verified_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND verified_at IS NULL
            """,
            (user_id,),
        )

        # ----------------------------------------------------
        # Store new OTP
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO password_resets
            (
                user_id,
                otp_hash,
                expires_at,
                attempts
            )
            VALUES (?, ?, ?, 0)
            """,
            (
                user_id,
                otp_hash,
                expires_at,
            ),
        )

    # --------------------------------------------------------
    # Send OTP email
    # --------------------------------------------------------

    try:

        send_password_reset_email(
            email,
            otp,
        )

    except Exception as e:

        return (
            False,
            f"Unable to send OTP email: {e}",
        )

    return (
        True,
        "If this email is registered, "
        "a password reset OTP has been sent.",
    )


# ============================================================
# VERIFY OTP
# ============================================================

def verify_reset_otp(
    email,
    otp,
):

    email = email.strip()
    otp = otp.strip()

    if not re.fullmatch(
        r"\d{6}",
        otp,
    ):
        return (
            False,
            "OTP must contain exactly 6 digits.",
        )

    with _conn() as conn:

        row = conn.execute(
            """
            SELECT
                pr.id,
                pr.otp_hash,
                pr.expires_at,
                pr.attempts

            FROM password_resets pr

            INNER JOIN users u
                ON u.id = pr.user_id

            WHERE u.email = ?
              AND pr.verified_at IS NULL

            ORDER BY pr.id DESC

            LIMIT 1
            """,
            (email,),
        ).fetchone()

        if not row:

            return (
                False,
                "Invalid or expired OTP.",
            )

        reset_id = row[0]
        stored_hash = row[1]
        expires_at = row[2]
        attempts = row[3]

        # ----------------------------------------------------
        # Attempt limit
        # ----------------------------------------------------

        if attempts >= MAX_OTP_ATTEMPTS:

            return (
                False,
                "Too many incorrect OTP attempts. "
                "Please request a new OTP.",
            )

        # ----------------------------------------------------
        # Expiry
        # ----------------------------------------------------

        try:

            expiry = datetime.fromisoformat(
                expires_at
            )

            now = datetime.now(
                timezone.utc
            )

            if now > expiry:

                return (
                    False,
                    "OTP has expired. "
                    "Please request a new OTP.",
                )

        except Exception:

            return (
                False,
                "Invalid OTP expiry.",
            )

        # ----------------------------------------------------
        # Compare OTP hash
        # ----------------------------------------------------

        entered_hash = hash_otp(otp)

        if not hmac.compare_digest(
            entered_hash,
            stored_hash,
        ):

            conn.execute(
                """
                UPDATE password_resets
                SET attempts = attempts + 1
                WHERE id = ?
                """,
                (reset_id,),
            )

            return (
                False,
                "Incorrect OTP.",
            )

        return (
            True,
            reset_id,
        )


# ============================================================
# RESET PASSWORD
# ============================================================

def reset_password(
    email,
    reset_id,
    new_password,
    confirm_password,
):

    email = email.strip()

    if len(new_password) < 8:

        return (
            False,
            "Password must be at least 8 characters.",
        )

    if new_password != confirm_password:

        return (
            False,
            "Passwords do not match.",
        )

    with _conn() as conn:

        # ----------------------------------------------------
        # Find reset request
        # ----------------------------------------------------

        row = conn.execute(
            """
            SELECT
                pr.id,
                pr.user_id,
                pr.expires_at,
                pr.verified_at

            FROM password_resets pr

            INNER JOIN users u
                ON u.id = pr.user_id

            WHERE pr.id = ?
              AND u.email = ?
            """,
            (
                reset_id,
                email,
            ),
        ).fetchone()

        if not row:

            return (
                False,
                "Invalid password reset request.",
            )

        actual_reset_id = row[0]
        user_id = row[1]
        expires_at = row[2]
        verified_at = row[3]

        # ----------------------------------------------------
        # Already used
        # ----------------------------------------------------

        if verified_at:

            return (
                False,
                "This password reset request "
                "has already been used.",
            )

        # ----------------------------------------------------
        # Check expiry again
        # ----------------------------------------------------

        try:

            expiry = datetime.fromisoformat(
                expires_at
            )

            if datetime.now(
                timezone.utc
            ) > expiry:

                return (
                    False,
                    "Password reset request has expired.",
                )

        except Exception:

            return (
                False,
                "Invalid password reset expiry.",
            )

        # ----------------------------------------------------
        # Create new password hash
        # ----------------------------------------------------

        salt = secrets.token_bytes(16)

        password_hash = _hash(
            new_password,
            salt,
        )

        # ----------------------------------------------------
        # Update password
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE users
            SET
                salt = ?,
                pw_hash = ?
            WHERE id = ?
            """,
            (
                salt.hex(),
                password_hash,
                user_id,
            ),
        )

        # ----------------------------------------------------
        # Mark reset request as used
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE password_resets
            SET verified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (actual_reset_id,),
        )

    return (
        True,
        "Password changed successfully.",
    )


# ============================================================
# STYLING
# ============================================================

_COMMON = """
#MainMenu, footer {
    visibility: hidden;
}

@keyframes ombre {
    0% {
        background-position: 0% 50%;
    }

    50% {
        background-position: 100% 50%;
    }

    100% {
        background-position: 0% 50%;
    }
}

@keyframes rise {
    from {
        opacity: 0;
        transform: translateY(28px) scale(.97);
    }

    to {
        opacity: 1;
        transform: none;
    }
}

@keyframes floaty {
    0%, 100% {
        transform: translateY(0);
    }

    50% {
        transform: translateY(-5px);
    }
}

.stButton > button,
div[data-testid="stFormSubmitButton"] button {

    position: relative;
    overflow: hidden;

    border: none;
    border-radius: 14px;

    font-weight: 600;

    color: #fff;

    background:
        linear-gradient(
            120deg,
            #2563eb,
            #7c3aed,
            #dc2626,
            #f97316
        );

    background-size: 250% 250%;

    animation: ombre 6s ease infinite;

    transition:
        transform .25s,
        box-shadow .25s;

    box-shadow:
        0 6px 20px
        rgba(168,85,247,.35);
}

.stButton > button:hover,
div[data-testid="stFormSubmitButton"] button:hover {

    transform:
        translateY(-4px)
        scale(1.04);

    color: #fff;

    box-shadow:
        0 14px 34px
        rgba(249,115,22,.5);
}

.stButton > button:active,
div[data-testid="stFormSubmitButton"] button:active {

    transform: scale(.96);
}
"""


_LOGIN = """
.stApp {

    background:
        linear-gradient(
            -45deg,
            #0f172a,
            #3730a3,
            #7c3aed,
            #dc2626,
            #f97316,
            #0284c7,
            #0f172a
        );

    background-size: 500% 500%;

    animation: ombre 20s ease infinite;

    color: #fff;
}

[data-testid="stHeader"] {
    background: transparent;
}

.block-container {

    position: relative;
    z-index: 1;

    padding-top: 2rem;

    max-width: 620px;
}

.auth-hero {

    text-align: center;

    margin:
        1rem
        0
        1.4rem;

    animation:
        rise .9s ease both;
}

.auth-logo {

    font-size: 3.4rem;

    display: inline-block;

    animation:
        floaty 3.2s ease-in-out infinite;

    filter:
        drop-shadow(
            0 8px 18px
            rgba(0,0,0,.35)
        );
}

.auth-hero h1 {

    margin:
        .3rem
        0
        .4rem;

    font-weight: 800;

    letter-spacing:
        -.5px;

    font-size: 2rem;

    background:
        linear-gradient(
            90deg,
            #fff,
            #fed7aa,
            #fde68a,
            #a5f3fc,
            #ddd6fe,
            #fff
        );

    background-size: 200% auto;

    -webkit-background-clip: text;
    background-clip: text;

    color: transparent;
}

.auth-hero p {

    color:
        rgba(255,255,255,.8);

    margin: 0;
}

div[data-testid="stForm"] {

    position: relative;

    overflow: hidden;

    padding: 1.8rem;

    border-radius: 28px;

    background:
        linear-gradient(
            135deg,
            rgba(255,255,255,.22),
            rgba(255,255,255,.06)
        );

    backdrop-filter:
        blur(24px)
        saturate(170%);

    -webkit-backdrop-filter:
        blur(24px)
        saturate(170%);

    border:
        1px solid
        rgba(255,255,255,.38);

    box-shadow:
        0 18px 50px
        rgba(0,0,0,.32),

        inset 0 1.5px 0
        rgba(255,255,255,.65);
}

label,
label p,
.stTextInput label p {

    color: #fff !important;

    font-weight: 500;
}

div[data-baseweb="input"] {

    background:
        rgba(255,255,255,.16)
        !important;

    border-radius:
        14px !important;

    border:
        1px solid
        rgba(255,255,255,.3)
        !important;
}

.stTextInput input {

    color: #fff !important;

    -webkit-text-fill-color:
        #fff;
}

.stTextInput input::placeholder {

    color:
        rgba(255,255,255,.55)
        !important;

    -webkit-text-fill-color:
        rgba(255,255,255,.55);
}

div[data-testid="stAlert"] {

    border-radius:
        16px;
}
"""


_APP = """
.block-container {

    padding-top: 2rem;

    max-width: 1150px;

    animation:
        rise .6s ease both;
}

h1 {

    font-weight: 800;

    letter-spacing:
        -.5px;

    background:
        linear-gradient(
            90deg,
            #2563eb,
            #7c3aed,
            #dc2626,
            #f97316,
            #2563eb
        );

    background-size:
        200% auto;

    -webkit-background-clip:
        text;

    background-clip:
        text;

    color: transparent;
}

div[data-testid="stMetric"] {

    padding:
        16px 20px;

    border-radius:
        20px;

    border:
        1px solid
        rgba(168,85,247,.3);

    background:
        linear-gradient(
            135deg,
            rgba(37,99,235,.14),
            rgba(249,115,22,.12)
        );

    backdrop-filter:
        blur(14px);

    box-shadow:
        0 8px 24px
        rgba(99,102,241,.15);
}

div[data-testid="stExpander"] {

    border-radius:
        18px;

    border:
        1px solid
        rgba(168,85,247,.25);
}

section[data-testid="stSidebar"] {

    background:
        linear-gradient(
            180deg,
            rgba(37,99,235,.14),
            rgba(249,115,22,.08)
        );

    backdrop-filter:
        blur(14px);
}
"""


def apply_style():

    css = (
        _APP
        if st.session_state.get("user")
        else _LOGIN
    )

    st.markdown(
        f"<style>{_COMMON}{css}</style>",
        unsafe_allow_html=True,
    )


# ============================================================
# FORGOT PASSWORD PAGE
# ============================================================

def _forgot_password_page():

    st.markdown(
        """
<div class="auth-hero">
    <div class="auth-logo">🔐</div>
    <h1>Reset Password</h1>
    <p>Reset your password using a 6-digit email OTP.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Initialize state
    # --------------------------------------------------------

    if "reset_step" not in st.session_state:
        st.session_state.reset_step = 1

    if "reset_email" not in st.session_state:
        st.session_state.reset_email = ""

    # ========================================================
    # STEP 1 - EMAIL
    # ========================================================

    if st.session_state.reset_step == 1:

        with st.form(
            "forgot_password_form"
        ):

            email = st.text_input(
                "Registered Email",
                placeholder="you@example.com",
            )

            send = st.form_submit_button(
                "Send OTP",
                type="primary",
                use_container_width=True,
            )

        if send:

            if not email.strip():

                st.warning(
                    "Please enter your email address."
                )

            else:

                ok, message = (
                    request_password_reset(
                        email
                    )
                )

                if ok:

                    st.session_state.reset_email = (
                        email.strip()
                    )

                    st.session_state.reset_step = 2

                    st.success(message)

                    st.rerun()

                else:

                    st.error(message)

    # ========================================================
    # STEP 2 - OTP
    # ========================================================

    elif st.session_state.reset_step == 2:

        st.info(
            "A 6-digit OTP has been sent to your email. "
            "The OTP is valid for 5 minutes."
        )

        with st.form(
            "verify_otp_form"
        ):

            otp = st.text_input(
                "Enter OTP",
                max_chars=6,
                placeholder="123456",
            )

            verify = st.form_submit_button(
                "Verify OTP",
                type="primary",
                use_container_width=True,
            )

        if verify:

            ok, result = verify_reset_otp(
                st.session_state.reset_email,
                otp,
            )

            if ok:

                st.session_state.reset_id = result

                st.session_state.reset_step = 3

                st.success(
                    "OTP verified successfully."
                )

                st.rerun()

            else:

                st.error(result)

        st.divider()

        if st.button(
            "Send OTP Again",
            use_container_width=True,
        ):

            ok, message = (
                request_password_reset(
                    st.session_state.reset_email
                )
            )

            if ok:
                st.success(message)
            else:
                st.error(message)

    # ========================================================
    # STEP 3 - NEW PASSWORD
    # ========================================================

    elif st.session_state.reset_step == 3:

        st.success(
            "OTP verified. Create your new password."
        )

        with st.form(
            "reset_password_form"
        ):

            new_password = st.text_input(
                "New Password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm New Password",
                type="password",
            )

            reset = st.form_submit_button(
                "Change Password",
                type="primary",
                use_container_width=True,
            )

        if reset:

            ok, message = reset_password(
                st.session_state.reset_email,
                st.session_state.reset_id,
                new_password,
                confirm_password,
            )

            if ok:

                st.success(
                    "Password changed successfully!"
                )

                st.session_state.pop(
                    "reset_email",
                    None,
                )

                st.session_state.pop(
                    "reset_id",
                    None,
                )

                st.session_state.reset_step = 1

                time.sleep(1)

                st.rerun()

            else:

                st.error(message)

    # ========================================================
    # BACK TO LOGIN
    # ========================================================

    st.divider()

    if st.button(
        "← Back to Login",
        use_container_width=True,
    ):

        st.session_state.pop(
            "reset_email",
            None,
        )

        st.session_state.pop(
            "reset_id",
            None,
        )

        st.session_state.reset_step = 1

        st.session_state.show_forgot_password = False

        st.rerun()


# ============================================================
# LOGIN PAGE
# ============================================================

def _login_page():

    # --------------------------------------------------------
    # Forgot password page
    # --------------------------------------------------------

    if st.session_state.get(
        "show_forgot_password",
        False,
    ):

        _forgot_password_page()

        return

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    st.markdown(
        """
<div class="auth-hero">
    <div class="auth-logo">🗄️</div>
    <h1>Agentic Enterprise Database QA</h1>
    <p>Sign in to ask questions about your database in plain English.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(
        [
            "🔑 Login",
            "📝 Register",
        ]
    )

    # ========================================================
    # LOGIN
    # ========================================================

    with tab_login:

        with st.form(
            "login_form"
        ):

            identifier = st.text_input(
                "Username or email"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            login = st.form_submit_button(
                "Log in",
                type="primary",
                use_container_width=True,
            )

        if login:

            wait = (
                st.session_state.get(
                    "lock_until",
                    0,
                )
                - time.time()
            )

            if wait > 0:

                st.error(
                    f"Too many attempts. "
                    f"Try again in "
                    f"{int(wait) + 1}s."
                )

            elif not identifier or not password:

                st.warning(
                    "Enter your username/email "
                    "and password."
                )

            else:

                user = check_login(
                    identifier,
                    password,
                )

                if user:

                    st.session_state.user = user
                    st.session_state.fails = 0

                    st.rerun()

                else:

                    st.session_state.fails = (
                        st.session_state.get(
                            "fails",
                            0,
                        )
                        + 1
                    )

                    if (
                        st.session_state.fails
                        >= MAX_FAILS
                    ):

                        st.session_state.lock_until = (
                            time.time()
                            + LOCK_SECONDS
                        )

                        st.session_state.fails = 0

                    st.error(
                        "Incorrect username/email "
                        "or password."
                    )

        # ----------------------------------------------------
        # Forgot password
        # ----------------------------------------------------

        st.divider()

        if st.button(
            "Forgot Password?",
            use_container_width=True,
        ):

            st.session_state.show_forgot_password = True
            st.session_state.reset_step = 1

            st.rerun()

    # ========================================================
    # REGISTER
    # ========================================================

    with tab_register:

        with st.form(
            "register_form"
        ):

            username = st.text_input(
                "Username"
            )

            email = st.text_input(
                "Email"
            )

            password = st.text_input(
                "Password (min 8 characters)",
                type="password",
            )

            confirm = st.text_input(
                "Confirm password",
                type="password",
            )

            register = st.form_submit_button(
                "Create account",
                type="primary",
                use_container_width=True,
            )

        if register:

            ok, message = register_user(
                username,
                email,
                password,
                confirm,
            )

            if ok:
                st.success(message)
            else:
                st.error(message)


# ============================================================
# REQUIRE LOGIN
# ============================================================

def require_login():

    if not st.session_state.get("user"):

        _login_page()

        st.stop()


# ============================================================
# SIDEBAR USER
# ============================================================

def sidebar_user():

    st.sidebar.markdown(
        f"👤 Signed in as **{st.session_state.user}**"
    )

    if st.sidebar.button(
        "Log out",
        use_container_width=True,
    ):

        st.session_state.clear()

        st.rerun()