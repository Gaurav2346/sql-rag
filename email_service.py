import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_password_reset_email(email: str, otp: str) -> bool:
    """
    Send password reset OTP email using SMTP.
    Works with Mailpit locally and real SMTP providers in production.
    """

    smtp_host = os.getenv("SMTP_HOST", "127.0.0.1")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    smtp_username = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", "hello@example.com")
    smtp_from_name = os.getenv(
        "SMTP_FROM_NAME",
        "Agentic Enterprise Database QA"
    )

    message = EmailMessage()

    message["Subject"] = "Your Password Reset OTP"
    message["From"] = f"{smtp_from_name} <{smtp_from}>"
    message["To"] = email

    # ---------------------------------------------------------
    # Plain-text fallback
    # ---------------------------------------------------------
    message.set_content(
        f"""
Hello,

We received a request to reset your password.

Your verification code is:

{otp}

This OTP will expire in 5 minutes.

If you did not request a password reset, you can safely ignore this email.

Regards,
{smtp_from_name}
"""
    )

    # ---------------------------------------------------------
    # Premium HTML Email
    # ---------------------------------------------------------
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Password Reset</title>
</head>

<body style="
    margin:0;
    padding:0;
    background:#f4f7fb;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#f4f7fb;padding:40px 16px;">

    <tr>
        <td align="center">

            <!-- Main Container -->
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="
                       max-width:560px;
                       background:#ffffff;
                       border-radius:18px;
                       overflow:hidden;
                       box-shadow:0 10px 35px rgba(15,23,42,0.10);
                   ">

                <!-- Header -->
                <tr>
                    <td style="
                        background:linear-gradient(135deg,#111827,#1e293b);
                        padding:34px 30px;
                        text-align:center;
                    ">

                        <div style="
                            width:58px;
                            height:58px;
                            margin:0 auto 16px;
                            border-radius:16px;
                            background:#ffffff;
                            text-align:center;
                            line-height:58px;
                            font-size:28px;
                        ">
                            🔐
                        </div>

                        <div style="
                            color:#ffffff;
                            font-size:21px;
                            font-weight:700;
                            letter-spacing:-0.3px;
                        ">
                            {smtp_from_name}
                        </div>

                        <div style="
                            color:#cbd5e1;
                            font-size:14px;
                            margin-top:7px;
                        ">
                            Account Security
                        </div>

                    </td>
                </tr>

                <!-- Content -->
                <tr>
                    <td style="padding:38px 34px 30px;">

                        <h1 style="
                            margin:0;
                            color:#111827;
                            font-size:25px;
                            line-height:1.3;
                            text-align:center;
                        ">
                            Reset your password
                        </h1>

                        <p style="
                            margin:14px 0 0;
                            color:#64748b;
                            font-size:15px;
                            line-height:1.7;
                            text-align:center;
                        ">
                            We received a request to reset the password
                            associated with your account.
                        </p>

                        <!-- OTP Card -->
                        <div style="
                            margin:30px 0;
                            padding:26px 20px;
                            background:#f8fafc;
                            border:1px solid #e2e8f0;
                            border-radius:14px;
                            text-align:center;
                        ">

                            <div style="
                                color:#64748b;
                                font-size:12px;
                                font-weight:600;
                                text-transform:uppercase;
                                letter-spacing:1.5px;
                                margin-bottom:12px;
                            ">
                                Your verification code
                            </div>

                            <div style="
                                color:#111827;
                                font-size:38px;
                                font-weight:800;
                                letter-spacing:9px;
                                line-height:1.2;
                                padding-left:9px;
                            ">
                                {otp}
                            </div>

                            <div style="
                                margin-top:14px;
                                color:#dc2626;
                                font-size:13px;
                                font-weight:600;
                            ">
                                ⏱ This code expires in 5 minutes
                            </div>

                        </div>

                        <!-- Security Message -->
                        <div style="
                            background:#eff6ff;
                            border-left:4px solid #2563eb;
                            border-radius:8px;
                            padding:15px 16px;
                            margin-bottom:24px;
                        ">

                            <div style="
                                color:#1e3a8a;
                                font-size:13px;
                                line-height:1.6;
                            ">
                                <strong>Security tip:</strong><br>
                                Never share this verification code with anyone.
                                Our team will never ask you for your OTP.
                            </div>

                        </div>

                        <p style="
                            margin:0;
                            color:#64748b;
                            font-size:13px;
                            line-height:1.7;
                            text-align:center;
                        ">
                            If you didn't request a password reset,
                            you can safely ignore this email.
                        </p>

                    </td>
                </tr>

                <!-- Divider -->
                <tr>
                    <td style="padding:0 34px;">
                        <div style="
                            height:1px;
                            background:#e5e7eb;
                        "></div>
                    </td>
                </tr>

                <!-- Footer -->
                <tr>
                    <td style="
                        padding:24px 30px 28px;
                        text-align:center;
                    ">

                        <div style="
                            color:#64748b;
                            font-size:12px;
                            line-height:1.6;
                        ">
                            This is an automated security email.
                            Please do not reply to this message.
                        </div>

                        <div style="
                            margin-top:12px;
                            color:#94a3b8;
                            font-size:11px;
                        ">
                            © 2026 {smtp_from_name}
                        </div>

                    </td>
                </tr>

            </table>

        </td>
    </tr>

</table>

</body>
</html>
"""

    message.add_alternative(html, subtype="html")

    try:
        # -----------------------------------------------------
        # Mailpit / Local SMTP
        # -----------------------------------------------------
        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=20
        ) as server:

            # Only authenticate when credentials are provided.
            if smtp_username and smtp_password:
                server.starttls()
                server.login(
                    smtp_username,
                    smtp_password
                )

            server.send_message(message)

        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False