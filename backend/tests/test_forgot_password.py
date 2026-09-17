import os
import logging
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import (
    hash_password,
    verify_password,
    generate_reset_token,
    hash_reset_token,
)
from app.main import app
from app.models.schemas import UserModel, PasswordResetTokenModel
from app.services.email_service import EmailService, mask_email

# In-memory SQLite engine for tests with StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Pre-seed test user
    db.add(UserModel(
        id="TEST-USER-FORGOT-001",
        email="forgotuser@lawgic.ai",
        full_name="Sarah Connor",
        role="Chief Legal Officer",
        hashed_password=hash_password("OriginalPassword123!"),
        is_active=True,
    ))
    db.commit()
    db.close()

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


# --- Token Generator & Hashing Unit Tests ---

def test_token_generation_and_hashing():
    raw_token, token_hash = generate_reset_token()
    assert isinstance(raw_token, str)
    assert len(raw_token) >= 32
    assert isinstance(token_hash, str)
    assert len(token_hash) == 64  # SHA-256 hex digest length

    # Verify hashing the raw token deterministically returns the same hash
    assert hash_reset_token(raw_token) == token_hash
    assert hash_reset_token("different-token") != token_hash


# --- Forgot Password Endpoint (Truthful Dispatch & Verification) ---

def test_forgot_password_registered_user():
    with patch("app.services.email_service.EmailService.send_password_reset_email", return_value={"success": True, "delivery": "mock"}) as mock_send_email:
        res = client.post("/api/auth/forgot-password", json={
            "email": "forgotuser@lawgic.ai"
        })
        assert res.status_code == 200
        data = res.json()
        assert "dispatched" in data["message"].lower()

        # Check that email was dispatched
        mock_send_email.assert_called_once()
        call_email, call_token = mock_send_email.call_args[0]
        assert call_email == "forgotuser@lawgic.ai"
        assert len(call_token) >= 32

        # Check token stored in database with SHA-256 hash (never raw token)
        db = TestingSessionLocal()
        token_rec = db.query(PasswordResetTokenModel).filter(
            PasswordResetTokenModel.user_id == "TEST-USER-FORGOT-001"
        ).first()
        assert token_rec is not None
        assert token_rec.token_hash == hash_reset_token(call_token)
        assert token_rec.is_used is False
        assert token_rec.expires_at > datetime.utcnow()
        db.close()


def test_forgot_password_unregistered_user_rejected():
    with patch("app.services.email_service.EmailService.send_password_reset_email") as mock_send_email:
        res = client.post("/api/auth/forgot-password", json={
            "email": "nonexistent@lawgic.ai"
        })
        # Must return 404 so UI does NOT fake "Reset Link Dispatched"
        assert res.status_code == 404
        assert "no account is registered" in res.json()["detail"].lower()

        # Email service must NOT be called for non-existent users
        mock_send_email.assert_not_called()

        # Database must not have any tokens created
        db = TestingSessionLocal()
        tokens = db.query(PasswordResetTokenModel).all()
        assert len(tokens) == 0
        db.close()


def test_forgot_password_delivery_failure_raises_502():
    with patch("app.services.email_service.EmailService.send_password_reset_email", return_value={"success": False, "error": "SMTP server connection timed out"}):
        res = client.post("/api/auth/forgot-password", json={
            "email": "forgotuser@lawgic.ai"
        })
        assert res.status_code == 502
        assert "connection timed out" in res.json()["detail"].lower()


def test_forgot_password_invalidates_prior_tokens():
    with patch("app.services.email_service.EmailService.send_password_reset_email", return_value={"success": True}):
        client.post("/api/auth/forgot-password", json={"email": "forgotuser@lawgic.ai"})
        client.post("/api/auth/forgot-password", json={"email": "forgotuser@lawgic.ai"})

    db = TestingSessionLocal()
    tokens = db.query(PasswordResetTokenModel).filter(
        PasswordResetTokenModel.user_id == "TEST-USER-FORGOT-001"
    ).all()
    # There should be 2 tokens: the older marked used, the newest unused
    assert len(tokens) == 2
    used_tokens = [t for t in tokens if t.is_used]
    active_tokens = [t for t in tokens if not t.is_used]
    assert len(used_tokens) == 1
    assert len(active_tokens) == 1
    db.close()


# --- Verify Reset Token Endpoint ---

def test_verify_reset_token_valid():
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-VALID",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        is_used=False,
    ))
    db.commit()
    db.close()

    res = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert res.status_code == 200
    assert res.json()["valid"] is True


def test_verify_reset_token_invalid():
    res = client.get("/api/auth/verify-reset-token?token=invalid-gibberish-token")
    assert res.status_code == 400
    assert "Invalid or unrecognized" in res.json()["detail"]


def test_verify_reset_token_expired():
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-EXPIRED",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() - timedelta(minutes=5),  # 5 mins ago
        is_used=False,
    ))
    db.commit()
    db.close()

    res = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_verify_reset_token_already_used():
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-USED",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        is_used=True,  # Already used
    ))
    db.commit()
    db.close()

    res = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert res.status_code == 400
    assert "already been used" in res.json()["detail"].lower()


# --- Reset Password Endpoint ---

def test_reset_password_full_flow():
    # 1. Create token for user
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-FLOW",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        is_used=False,
    ))
    db.commit()
    db.close()

    # 2. Reset password to new secure password
    new_pass = "BrandNewSecurePassword2026!"
    reset_res = client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": new_pass,
    })
    assert reset_res.status_code == 200
    assert "successfully reset" in reset_res.json()["message"].lower()

    # 3. Verify old password fails login
    old_login = client.post("/api/auth/login", json={
        "email": "forgotuser@lawgic.ai",
        "password": "OriginalPassword123!",
    })
    assert old_login.status_code == 401

    # 4. Verify new password succeeds login
    new_login = client.post("/api/auth/login", json={
        "email": "forgotuser@lawgic.ai",
        "password": new_pass,
    })
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

    # 5. Verify token is marked as is_used in DB
    db = TestingSessionLocal()
    rec = db.query(PasswordResetTokenModel).filter(
        PasswordResetTokenModel.id == "PRT-TEST-FLOW"
    ).first()
    assert rec.is_used is True
    db.close()


def test_reset_password_token_reuse_rejected():
    # 1. Create valid token
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-REUSE",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        is_used=False,
    ))
    db.commit()
    db.close()

    # 2. First reset succeeds
    res1 = client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewValidPassword123!",
    })
    assert res1.status_code == 200

    # 3. Second reset with identical token MUST fail
    res2 = client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": "AnotherAttemptPassword123!",
    })
    assert res2.status_code == 400
    assert "already been used" in res2.json()["detail"].lower()


def test_reset_password_expired_token_rejected():
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-EXPIRED-RESET",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        is_used=False,
    ))
    db.commit()
    db.close()

    res = client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewAttemptPassword123!",
    })
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

    # Verify original password still intact
    db = TestingSessionLocal()
    user = db.query(UserModel).filter(UserModel.id == "TEST-USER-FORGOT-001").first()
    assert verify_password("OriginalPassword123!", user.hashed_password) is True
    db.close()


def test_reset_password_short_password_rejected():
    raw_token, token_hash = generate_reset_token()
    db = TestingSessionLocal()
    db.add(PasswordResetTokenModel(
        id="PRT-TEST-SHORT",
        user_id="TEST-USER-FORGOT-001",
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        is_used=False,
    ))
    db.commit()
    db.close()

    # Password less than 6 chars
    res = client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": "123",
    })
    assert res.status_code in (400, 422)
    detail = str(res.json()["detail"]).lower()
    assert "at least 6 characters" in detail or "greater than or equal to 6" in detail


# --- Production SMTP Delivery & Zero Server-Log Leakage Tests ---

def test_email_masking_utility():
    assert mask_email("counsel@lawgic.ai") == "c***l@lawgic.ai"
    assert mask_email("me@domain.com") == "m***@domain.com"
    assert mask_email("invalid") == "***"
    assert mask_email("") == "***"


def test_email_service_zero_log_leakage_of_token_and_url(caplog):
    """
    CRITICAL SECURITY TEST:
    Verifies that neither the raw secret token nor the reset URL is EVER logged to server logs.
    """
    secret_token = "SUPER_SECRET_RAW_TOKEN_99999_ENTROPY"
    to_email = "confidential.partner@lawgic.ai"

    with caplog.at_level(logging.DEBUG):
        with patch.dict(os.environ, {"SMTP_HOST": "", "RESEND_API_KEY": "", "BREVO_API_KEY": "", "SENDGRID_API_KEY": ""}):
            result = EmailService.send_password_reset_email(to_email, secret_token)

    assert result["success"] is False
    assert result["delivery"] == "unconfigured"
    # Verify the secret token is completely absent from all log records
    assert secret_token not in caplog.text
    assert "?token=" not in caplog.text
    # Verify the full recipient email is masked in logs
    assert "confidential.partner@lawgic.ai" not in caplog.text
    assert "c***r@lawgic.ai" in caplog.text


def test_email_service_smtp_delivery_starttls(caplog):
    """
    Verifies production STARTTLS delivery via smtplib.SMTP.
    """
    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=None)

    env_overrides = {
        "RESEND_API_KEY": "",
        "BREVO_API_KEY": "",
        "SENDGRID_API_KEY": "",
        "SMTP_HOST": "smtp.sendgrid.net",
        "SMTP_PORT": "587",
        "SMTP_USER": "apikey",
        "SMTP_PASSWORD": "SG.secret_key_12345",
        "SMTP_TLS": "true",
        "SMTP_SSL": "false",
        "FROM_EMAIL": "security@lawgic.ai",
        "FROM_NAME": "LAWGIC Security",
    }

    with patch.dict(os.environ, env_overrides):
        with patch("smtplib.SMTP", mock_smtp_class):
            with caplog.at_level(logging.INFO):
                result = EmailService.send_password_reset_email("attorney@firm.com", "valid_token_xyz")

    assert result["success"] is True
    assert result["delivery"] == "smtp"

    # Verify SMTP calls: constructed host/port, starttls, login, send_message
    mock_smtp_class.assert_called_once_with("smtp.sendgrid.net", 587, timeout=10)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("apikey", "SG.secret_key_12345")
    mock_smtp_instance.send_message.assert_called_once()

    # Verify message recipient and headers
    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert sent_msg["To"] == "attorney@firm.com"
    assert sent_msg["From"] == "LAWGIC Security <security@lawgic.ai>"
    assert "Password Reset Request" in sent_msg["Subject"]

    # Verify zero token leakage in log records
    assert "valid_token_xyz" not in caplog.text
    assert "?token=" not in caplog.text


def test_email_service_smtp_delivery_ssl():
    """
    Verifies production direct SSL delivery via smtplib.SMTP_SSL (e.g. port 465).
    """
    mock_ssl_instance = MagicMock()
    mock_ssl_class = MagicMock(return_value=mock_ssl_instance)
    mock_ssl_instance.__enter__ = MagicMock(return_value=mock_ssl_instance)
    mock_ssl_instance.__exit__ = MagicMock(return_value=None)

    env_overrides = {
        "RESEND_API_KEY": "",
        "BREVO_API_KEY": "",
        "SENDGRID_API_KEY": "",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "mailer@lawgic.ai",
        "SMTP_PASSWORD": "app_password_here",
        "SMTP_SSL": "true",
        "FROM_EMAIL": "mailer@lawgic.ai",
    }

    with patch.dict(os.environ, env_overrides):
        with patch("smtplib.SMTP_SSL", mock_ssl_class):
            result = EmailService.send_password_reset_email("clerk@court.gov", "token_ssl_123")

    assert result["success"] is True
    assert result["delivery"] == "smtp"
    mock_ssl_class.assert_called_once()
    mock_ssl_instance.login.assert_called_once_with("mailer@lawgic.ai", "app_password_here")
    mock_ssl_instance.send_message.assert_called_once()


def test_email_service_smtp_error_handling_without_crash():
    """
    Verifies that SMTP connection or authentication failures are caught and handled gracefully.
    """
    mock_smtp_class = MagicMock(side_effect=ConnectionRefusedError("SMTP server refused connection"))

    env_overrides = {
        "RESEND_API_KEY": "",
        "BREVO_API_KEY": "",
        "SENDGRID_API_KEY": "",
        "SMTP_HOST": "smtp.unreachable.net",
        "SMTP_PORT": "587",
    }

    with patch.dict(os.environ, env_overrides):
        with patch("smtplib.SMTP", mock_smtp_class):
            result = EmailService.send_password_reset_email("user@company.com", "token_err_123")

    assert result["success"] is False
    assert result["delivery"] == "smtp_failed"
    assert "ConnectionRefusedError" in result["error"] or "refused" in result["error"]


def test_email_service_production_frontend_url_resolution():
    """
    Verifies that FRONTEND_URL environment variable is correctly embedded in links.
    """
    custom_prod_url = "https://lawgic-phi.vercel.app"
    with patch.dict(os.environ, {"FRONTEND_URL": custom_prod_url}):
        assert EmailService.get_frontend_url() == custom_prod_url
        EmailService.send_password_reset_email("test@lawgic.ai", "my-test-token")
        assert EmailService.last_sent_email["reset_url"].startswith(f"{custom_prod_url}/?token=my-test-token")


# ─── Resend API Delivery Tests ────────────────────────────────────────────────

def test_email_service_resend_delivery(caplog):
    """
    Verifies outbound email dispatch via Resend HTTPS API using RESEND_API_KEY and FROM_EMAIL.
    """
    import urllib.request
    import json
    import io

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"id": "res_msg_test_abc123"}).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=None)

    env_overrides = {
        "RESEND_API_KEY": "re_test_key_xyz_789",
        "FROM_EMAIL": "onboarding@resend.dev",
        "FROM_NAME": "LAWGIC Security",
        "FRONTEND_URL": "http://localhost:3000",
        "SMTP_HOST": "",
    }

    with patch.dict(os.environ, env_overrides):
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            with caplog.at_level(logging.INFO):
                result = EmailService.send_password_reset_email("partner@lawfirm.com", "secret_token_resend_456")

    assert result["success"] is True
    assert result["delivery"] == "resend"
    assert result["id"] == "res_msg_test_abc123"

    mock_urlopen.assert_called_once()
    called_req = mock_urlopen.call_args[0][0]
    assert called_req.full_url == "https://api.resend.com/emails"
    assert called_req.headers["Authorization"] == "Bearer re_test_key_xyz_789"
    assert called_req.headers["Content-type"] == "application/json"

    sent_body = json.loads(called_req.data.decode("utf-8"))
    assert sent_body["from"] == "LAWGIC Security <onboarding@resend.dev>"
    assert sent_body["to"] == ["partner@lawfirm.com"]
    assert "Password Reset Request" in sent_body["subject"]
    assert "secret_token_resend_456" in sent_body["html"]
    assert "secret_token_resend_456" in sent_body["text"]

    # Verify zero token leakage in log records
    assert "secret_token_resend_456" not in caplog.text


def test_email_service_resend_api_error_handling(caplog):
    """
    Verifies that HTTP errors from Resend (e.g. invalid API key) are caught without crashing.
    """
    import urllib.request
    import urllib.error
    import io

    err_body = io.BytesIO(b'{"message": "API key is invalid", "name": "validation_error"}')
    http_error = urllib.error.HTTPError(
        url="https://api.resend.com/emails",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=err_body,
    )

    env_overrides = {
        "RESEND_API_KEY": "re_invalid_key",
        "FROM_EMAIL": "onboarding@resend.dev",
        "SMTP_HOST": "",
    }

    with patch.dict(os.environ, env_overrides):
        with patch("urllib.request.urlopen", side_effect=http_error):
            result = EmailService.send_password_reset_email("user@lawgic.ai", "token_err_999")

    assert result["success"] is False
    assert result["delivery"] == "resend_failed"
    assert "API key is invalid" in result["error"] or "401" in result["error"]


def test_complete_forgot_password_reset_login_flow():
    """
    End-to-End Verification:
    Forgot password -> receive email -> click link -> reset password -> single-use check -> login.
    """
    custom_frontend = "http://localhost:3000"
    user_email = "forgotuser@lawgic.ai"
    old_password = "OriginalPassword123!"
    new_password = "BrandNewSecurePassword2026!"

    with patch.dict(os.environ, {"FRONTEND_URL": custom_frontend}):
        # 1. User submits forgot-password
        with patch("app.services.email_service.EmailService.send_password_reset_email") as mock_email:
            mock_email.return_value = {"success": True, "delivery": "mock"}
            resp_forgot = client.post("/api/auth/forgot-password", json={"email": user_email})
            assert resp_forgot.status_code == 200
            assert "dispatched" in resp_forgot.json()["message"].lower()

            # 2. Receive email and extract token from reset link
            mock_email.assert_called_once()
            call_email, raw_token = mock_email.call_args[0]
            assert call_email == user_email
            assert len(raw_token) >= 32

        # 3. Simulate clicking link with various formats (clean, trailing slash, hash)
        # Normal click
        resp_verify = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
        assert resp_verify.status_code == 200
        assert resp_verify.json()["valid"] is True

        # Click with trailing slash
        resp_verify_slash = client.get(f"/api/auth/verify-reset-token?token={raw_token}/")
        assert resp_verify_slash.status_code == 200
        assert resp_verify_slash.json()["valid"] is True

        # Token is still valid (not single-use burned merely by verifying)
        resp_verify_again = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
        assert resp_verify_again.status_code == 200

        # 4. Reset password using the token
        resp_reset = client.post("/api/auth/reset-password", json={
            "token": raw_token,
            "new_password": new_password,
        })
        assert resp_reset.status_code == 200
        assert "successfully reset" in resp_reset.json()["message"].lower()

        # 5. Token is now single-use burned; subsequent attempts must fail
        resp_verify_burned = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
        assert resp_verify_burned.status_code == 400
        assert "already been used" in resp_verify_burned.json()["detail"].lower()

        resp_reset_burned = client.post("/api/auth/reset-password", json={
            "token": raw_token,
            "new_password": "YetAnotherPassword999!",
        })
        assert resp_reset_burned.status_code == 400
        assert "already been used" in resp_reset_burned.json()["detail"].lower()

        # 6. Old password no longer works
        resp_login_old = client.post("/api/auth/login", json={
            "email": user_email,
            "password": old_password,
        })
        assert resp_login_old.status_code == 401

        # 7. Login with new password succeeds and returns JWT access token
        resp_login_new = client.post("/api/auth/login", json={
            "email": user_email,
            "password": new_password,
        })
        assert resp_login_new.status_code == 200
        token_data = resp_login_new.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["user"]["email"] == user_email


