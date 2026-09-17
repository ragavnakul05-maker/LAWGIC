import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

# Load .env
env_file = backend_root / ".env"
load_dotenv(env_file)

from app.services.email_service import EmailService, mask_email


def main():
    recipient = sys.argv[1] if len(sys.argv) > 1 else "harshikaas1603@gmail.com"
    print("=" * 65)
    print(" LAWGIC Real Email Delivery Tester")
    print("=" * 65)
    print(f"Target Recipient: {recipient}")
    print(f"Loaded .env from: {env_file}")
    print("-" * 65)

    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()
    sendgrid_key = os.getenv("SENDGRID_API_KEY", "").strip()
    smtp_host = os.getenv("SMTP_HOST", "").strip()

    if resend_key:
        print(f"[Provider] Resend API (key ending in ...{resend_key[-4:]})")
    elif brevo_key:
        print(f"[Provider] Brevo API (key ending in ...{brevo_key[-4:]})")
    elif sendgrid_key:
        print(f"[Provider] SendGrid API (key ending in ...{sendgrid_key[-4:]})")
    elif smtp_host:
        port = os.getenv("SMTP_PORT", "587")
        user = os.getenv("SMTP_USER", "")
        print(f"[Provider] SMTP Host: {smtp_host}:{port} (User: {mask_email(user)})")
    else:
        print("[Provider] NONE configured in .env!")
        print("\nPlease add one of the following to backend/.env:")
        print("\n  Option A — Resend (HTTPS 443, recommended):")
        print("    RESEND_API_KEY=re_...")
        print("    FROM_EMAIL=onboarding@resend.dev  # or custom domain")
        print("\n  Option B — Brevo:")
        print("    BREVO_API_KEY=xkeysib-...")
        print("    FROM_EMAIL=your_email@domain.com")
        print("\n  Option C — Gmail SMTP:")
        print("    SMTP_HOST=smtp.gmail.com")
        print("    SMTP_PORT=465")
        print("    SMTP_SSL=true")
        print("    SMTP_USER=your_email@gmail.com")
        print("    SMTP_PASSWORD=your_16_char_google_app_password")
        print("    FROM_EMAIL=your_email@gmail.com")
        print("=" * 65)
        return

    from app.core.security import generate_reset_token
    from app.core.database import SessionLocal
    from app.models.schemas import UserModel, PasswordResetTokenModel
    from datetime import datetime, timedelta
    import uuid

    raw_token, token_hash = generate_reset_token()

    # Persist token to database if recipient user exists so link in test email is fully testable
    try:
        db = SessionLocal()
        clean_email = recipient.strip().lower()
        user = db.query(UserModel).filter(UserModel.email == clean_email).first()
        if user:
            # Invalidate previous unused tokens for this user
            db.query(PasswordResetTokenModel).filter(
                PasswordResetTokenModel.user_id == user.id,
                PasswordResetTokenModel.is_used == False,
            ).update({"is_used": True})

            expire_minutes = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
            token_rec = PasswordResetTokenModel(
                id=f"PRT-{uuid.uuid4().hex[:8].upper()}",
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(minutes=expire_minutes),
                is_used=False,
                created_at=datetime.utcnow(),
            )
            db.add(token_rec)
            db.commit()
            print(f"[Database] Password reset token stored in database for user '{clean_email}' (Expires in {expire_minutes}m).")
        else:
            print(f"[Database Note] Recipient '{clean_email}' does not exist in users table; token will only be tested for delivery.")
        db.close()
    except Exception as e:
        print(f"[Database Warning] Could not persist token record: {e}")

    print("\nAttempting outbound email transmission...")
    result = EmailService.send_password_reset_email(recipient, raw_token)

    print("-" * 65)
    if result.get("success"):
        print(f"SUCCESS! Email was successfully accepted by provider ({result.get('delivery')}).")
        print(f"Check the inbox and spam folder for {recipient}.")
    else:
        print("FAILED to deliver email!")
        print(f"Error detail: {result.get('error')}")
    print("=" * 65)


if __name__ == "__main__":
    main()
