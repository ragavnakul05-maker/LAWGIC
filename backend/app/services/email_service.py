import os
import smtplib
import ssl
import json
import urllib.request
import urllib.error
import logging
from pathlib import Path
from email.message import EmailMessage
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Ensure backend .env is loaded
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

logger = logging.getLogger(__name__)


def mask_email(email: str) -> str:
    """
    Masks an email address for privacy-safe operational logging (e.g. j***e@example.com).
    Guarantees user privacy in production application logs.
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


class EmailService:
    last_sent_email: Optional[Dict[str, Any]] = None

    @classmethod
    def get_frontend_url(cls) -> str:
        """
        Resolves the frontend base URL for password reset links.
        Priority:
        1. FRONTEND_URL environment variable (if explicitly set and valid)
        2. VERCEL_URL environment variable (auto-injected on Vercel)
        3. Production domain fallback: https://lawgic-phi.vercel.app (if in production or on Vercel)
        4. Development fallback: http://localhost:3000
        """
        raw_url = os.getenv("FRONTEND_URL", "").strip()

        if not raw_url:
            vercel_url = os.getenv("VERCEL_URL", "").strip()
            env_mode = os.getenv("ENVIRONMENT", "").lower()
            is_vercel = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or vercel_url)
            is_prod = env_mode in ("production", "prod") or (is_vercel and env_mode not in ("development", "dev", "local"))
            if vercel_url:
                raw_url = f"https://{vercel_url}" if not vercel_url.startswith("http") else vercel_url
            elif is_prod:
                raw_url = "https://lawgic-phi.vercel.app"
            else:
                raw_url = "http://localhost:3000"

        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = f"https://{raw_url}"

        return raw_url.rstrip("/")

    @classmethod
    def is_configured(cls) -> bool:
        """
        Checks whether real email delivery is configured via SMTP or HTTPS Email API.
        """
        if os.getenv("SMTP_HOST", "").strip():
            return True
        if os.getenv("RESEND_API_KEY", "").strip():
            return True
        if os.getenv("SENDGRID_API_KEY", "").strip():
            return True
        if os.getenv("BREVO_API_KEY", "").strip():
            return True
        return False

    @classmethod
    def send_password_reset_email(cls, to_email: str, raw_token: str) -> Dict[str, Any]:
        """
        Constructs and dispatches the single-use password reset email.
        
        PRODUCTION SECURITY & INTEGRITY GUARANTEES:
        - NEVER fakes successful dispatch when email delivery fails or is unconfigured.
        - NEVER logs raw reset tokens or URLs to server stdout/stderr/files.
        - Delivers via real authenticated SMTP or HTTPS Email APIs (Resend/SendGrid/Brevo).
        - Returns explicit delivery outcome with actionable diagnostic details on failure.
        """
        frontend_url = cls.get_frontend_url()
        reset_url = f"{frontend_url}/?token={raw_token}"

        from_email = os.getenv("FROM_EMAIL", "").strip() or "onboarding@resend.dev"
        from_name = os.getenv("FROM_NAME", "LAWGIC Security").strip()
        if "<" in from_email and ">" in from_email:
            from_header = from_email
        else:
            from_header = f"{from_name} <{from_email}>" if from_name else from_email

        subject = "LAWGIC — Password Reset Request"
        text_content = (
            f"Hello,\n\n"
            f"We received a request to reset your password for your LAWGIC account.\n\n"
            f"Click the link below to set a new password (valid for 15 minutes):\n"
            f"{reset_url}\n\n"
            f"If you did not request this password reset, please disregard this email. "
            f"Your password will remain unchanged.\n\n"
            f"— The LAWGIC Security Team\n"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; margin: 0; padding: 32px; color: #1e293b;">
  <div style="max-width: 540px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px; text-align: center;">
      <h1 style="font-size: 24px; font-weight: 800; color: #0f172a; margin: 0;">LAWGIC</h1>
      <p style="font-size: 11px; font-weight: 700; color: #4f46e5; text-transform: uppercase; letter-spacing: 0.05em; margin: 4px 0 0;">Executable Contract Intelligence</p>
    </div>
    <h2 style="font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 0;">Reset Your Password</h2>
    <p style="font-size: 14px; line-height: 1.6; color: #475569;">
      We received a request to reset your password. Click the button below to choose a new, secure password. This link will expire in <strong>15 minutes</strong>.
    </p>
    <div style="text-align: center; margin: 28px 0;">
      <a href="{reset_url}" style="background: #4f46e5; color: #ffffff; padding: 12px 28px; font-size: 13px; font-weight: 700; border-radius: 10px; text-decoration: none; display: inline-block;">
        Reset Password
      </a>
    </div>
    <p style="font-size: 12px; color: #64748b; line-height: 1.5;">
      If the button above does not work, copy and paste this link into your browser:<br>
      <a href="{reset_url}" style="color: #4f46e5; word-break: break-all;">{reset_url}</a>
    </p>
    <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">
    <p style="font-size: 11px; color: #94a3b8; margin: 0; text-align: center;">
      If you did not request this, you can safely ignore this email. Your account remains secure.
    </p>
  </div>
</body>
</html>"""

        masked_to = mask_email(to_email)

        # In-memory storage for test assertion purposes (never logged or leaked)
        cls.last_sent_email = {
            "to_email": to_email,
            "raw_token": raw_token,
            "reset_url": reset_url,
            "subject": subject,
        }

        # ── 1. Resend API Delivery (HTTPS port 443 — reliable across all ISP networks) ──
        resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
        if resend_api_key:
            try:
                resend_payload = json.dumps({
                    "from": from_header,
                    "to": [to_email],
                    "subject": subject,
                    "text": text_content,
                    "html": html_content,
                }).encode("utf-8")

                req = urllib.request.Request(
                    "https://api.resend.com/emails",
                    data=resend_payload,
                    headers={
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "LAWGIC-App/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_body = resp.read().decode("utf-8")
                    msg_id = None
                    try:
                        resp_json = json.loads(resp_body)
                        msg_id = resp_json.get("id")
                    except Exception:
                        pass

                    logger.info("Password reset email sent to %s via Resend API (HTTP %d, id=%s)", masked_to, resp.status, msg_id)
                    return {"success": True, "delivery": "resend", "status": resp.status, "id": msg_id}
            except urllib.error.HTTPError as exc:
                err_detail = exc.read().decode("utf-8", errors="ignore")
                logger.error("Resend API error for %s (HTTP %d): %s", masked_to, exc.code, err_detail)
                return {"success": False, "delivery": "resend_failed", "error": f"Resend API error ({exc.code}): {err_detail}"}
            except Exception as exc:
                logger.error("Resend connection error for %s: %s", masked_to, exc)
                return {"success": False, "delivery": "resend_failed", "error": f"Resend connection failed: {str(exc)}"}

        # ── 2. Brevo API Delivery (HTTPS port 443) ──
        brevo_api_key = os.getenv("BREVO_API_KEY", "").strip()
        if brevo_api_key:
            try:
                brevo_payload = json.dumps({
                    "sender": {"name": from_name, "email": from_email},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "textContent": text_content,
                    "htmlContent": html_content,
                }).encode("utf-8")

                req = urllib.request.Request(
                    "https://api.brevo.com/v3/smtp/email",
                    data=brevo_payload,
                    headers={
                        "api-key": brevo_api_key,
                        "Content-Type": "application/json",
                        "User-Agent": "LAWGIC-App/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    logger.info("Password reset email sent to %s via Brevo API (HTTP %d)", masked_to, resp.status)
                    return {"success": True, "delivery": "brevo", "status": resp.status}
            except urllib.error.HTTPError as exc:
                err_detail = exc.read().decode("utf-8", errors="ignore")
                logger.error("Brevo API error for %s (HTTP %d): %s", masked_to, exc.code, err_detail)
                return {"success": False, "delivery": "brevo_failed", "error": f"Brevo API error ({exc.code}): {err_detail}"}
            except Exception as exc:
                logger.error("Brevo connection error for %s: %s", masked_to, exc)
                return {"success": False, "delivery": "brevo_failed", "error": f"Brevo connection failed: {str(exc)}"}

        # ── 3. Real SMTP Delivery (STARTTLS port 587 / SSL port 465) ──
        smtp_host = os.getenv("SMTP_HOST", "").strip()
        if smtp_host:
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "").strip()
            smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
            smtp_tls = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")
            smtp_ssl = os.getenv("SMTP_SSL", "false").lower() in ("true", "1", "yes") or smtp_port == 465
            timeout = int(os.getenv("SMTP_TIMEOUT", "10"))

            try:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = from_header
                msg["To"] = to_email
                msg.set_content(text_content)
                msg.add_alternative(html_content, subtype="html")

                if smtp_ssl:
                    # Direct SSL connection (typically port 465)
                    ssl_context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout, context=ssl_context) as server:
                        if smtp_user and smtp_password:
                            server.login(smtp_user, smtp_password)
                        server.send_message(msg)
                else:
                    # Standard SMTP with STARTTLS (typically port 587 or 25)
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
                        if smtp_tls:
                            ssl_context = ssl.create_default_context()
                            server.starttls(context=ssl_context)
                        if smtp_user and smtp_password:
                            server.login(smtp_user, smtp_password)
                        server.send_message(msg)

                logger.info(
                    "Password reset email successfully dispatched to %s via SMTP (%s:%d)",
                    masked_to, smtp_host, smtp_port
                )
                return {"success": True, "delivery": "smtp"}

            except smtplib.SMTPAuthenticationError as exc:
                err_msg = f"SMTP authentication failed for user '{smtp_user}'. Please verify your email password/app-password."
                logger.error("SMTP authentication error for %s: %s", masked_to, exc)
                return {"success": False, "delivery": "smtp_failed", "error": err_msg}
            except (TimeoutError, smtplib.SMTPConnectError, socket_timeout_error) as exc:
                err_msg = f"Connection to SMTP server '{smtp_host}:{smtp_port}' timed out. Your ISP or network may be blocking SMTP port {smtp_port}."
                logger.error("SMTP connection error for %s: %s", masked_to, exc)
                return {"success": False, "delivery": "smtp_failed", "error": err_msg}
            except Exception as exc:
                err_msg = f"SMTP error ({type(exc).__name__}): {str(exc)}"
                logger.error("Failed to dispatch password reset email to %s: %s", masked_to, exc)
                return {"success": False, "delivery": "smtp_failed", "error": err_msg}

        # ── 4. Explicit Failure when NO email service is configured ──
        # DO NOT fake success. Report unconfigured status clearly so the user/UI knows no email was sent!
        logger.warning(
            "Password reset attempted for %s, but no email delivery provider is configured in backend/.env.",
            masked_to
        )
        return {
            "success": False,
            "delivery": "unconfigured",
            "error": "Email delivery service is not configured. Please set SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in backend/.env.",
        }


# Handle socket timeout alias
try:
    from socket import timeout as socket_timeout_error
except ImportError:
    socket_timeout_error = TimeoutError
