import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    generate_reset_token,
    hash_reset_token,
)
from app.models.schemas import (
    UserModel,
    PasswordResetTokenModel,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    GenericAuthMessageResponse,
)
from app.services.email_service import EmailService

router = APIRouter(prefix="/auth", tags=["Authentication"])


class DemoUserItem(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    description: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid email address is required.")
    
    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters.")

    existing = db.query(UserModel).filter(UserModel.email == email_clean).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists.")

    new_user = UserModel(
        id=f"USER-{uuid.uuid4().hex[:8].upper()}",
        email=email_clean,
        full_name=req.full_name.strip() or "Legal Practitioner",
        role=req.role.strip() if req.role else "Senior Legal Counsel",
        hashed_password=hash_password(req.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": new_user.id, "email": new_user.email, "role": new_user.role})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate an existing user and return a JWT access token."""
    email_clean = req.email.strip().lower()
    user = db.query(UserModel).filter(UserModel.email == email_clean).first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is deactivated.")

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserModel = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


@router.get("/demo-users", response_model=List[DemoUserItem])
def get_demo_users():
    """Return pre-configured demo user accounts for rapid testing and review."""
    return [
        DemoUserItem(
            email="admin@lawgic.ai",
            password="password123",
            full_name="Dr. Eleanor Vance",
            role="Chief Legal Officer & General Counsel",
            description="Full administrative access to contract analysis, deterministic engine rules, and simulations.",
        ),
        DemoUserItem(
            email="counsel@lawgic.ai",
            password="password123",
            full_name="Marcus Sterling",
            role="Senior Commercial Legal Counsel",
            description="Standard legal workflow access for clause extraction, rule auditing, and financial risk reviews.",
        ),
    ]


# ---------------------------------------------------------------------------
# Password Recovery Endpoints
# ---------------------------------------------------------------------------

@router.post("/forgot-password", response_model=GenericAuthMessageResponse)
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Initiates the secure password reset flow.
    Verifies that real email delivery succeeds before confirming dispatch.
    """
    email_clean = req.email.strip().lower()
    user = db.query(UserModel).filter(UserModel.email == email_clean).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account is registered with the email address '{email_clean}'. Please verify your email or create a new account.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user account is deactivated. Please contact support.",
        )

    # Invalidate any existing unused tokens for this user
    db.query(PasswordResetTokenModel).filter(
        PasswordResetTokenModel.user_id == user.id,
        PasswordResetTokenModel.is_used == False,
    ).update({"is_used": True})

    # Generate a secure 256-bit token & hash
    raw_token, token_hash = generate_reset_token()
    expire_minutes = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "15"))
    expires_at = datetime.utcnow() + timedelta(minutes=expire_minutes)

    token_rec = PasswordResetTokenModel(
        id=f"PRT-{uuid.uuid4().hex[:8].upper()}",
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_used=False,
        created_at=datetime.utcnow(),
    )
    db.add(token_rec)
    db.commit()

    # Deliver real email via EmailService
    delivery = EmailService.send_password_reset_email(user.email, raw_token)

    if not delivery.get("success"):
        # If email delivery fails, remove the token and return an actionable HTTP 502/503 error
        db.delete(token_rec)
        db.commit()
        error_detail = delivery.get("error", "Email service delivery failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email delivery failed: {error_detail}",
        )

    return GenericAuthMessageResponse(
        message=f"Password reset instructions have been dispatched to {user.email}. Please check your inbox."
    )


@router.get("/verify-reset-token")
def verify_reset_token_endpoint(token: str, db: Session = Depends(get_db)):
    """
    Checks whether a password reset token is valid, unexpired, and unused.
    """
    clean_token = (token or "").strip().rstrip("/")
    if not clean_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is required.")

    token_hash = hash_reset_token(clean_token)
    token_rec = db.query(PasswordResetTokenModel).filter(PasswordResetTokenModel.token_hash == token_hash).first()

    if not token_rec:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unrecognized password reset token.")

    if token_rec.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset token has already been used.")

    if datetime.utcnow() > token_rec.expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset token has expired. Please request a new one.")

    return {"valid": True, "message": "Token is valid."}


@router.post("/reset-password", response_model=GenericAuthMessageResponse)
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Resets the user's password using a valid, unused, and unexpired token.
    Hashes the new password using PBKDF2 and invalidates the token.
    """
    clean_token = (req.token or "").strip().rstrip("/")
    if not clean_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is required.")

    if len(req.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters.",
        )

    token_hash = hash_reset_token(clean_token)
    token_rec = db.query(PasswordResetTokenModel).filter(PasswordResetTokenModel.token_hash == token_hash).first()

    if not token_rec:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unrecognized password reset token.")

    if token_rec.is_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset token has already been used.")

    if datetime.utcnow() > token_rec.expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset token has expired. Please request a new one.")

    user = db.query(UserModel).filter(UserModel.id == token_rec.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account associated with this token was not found.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User account is deactivated.")

    # Hash new password securely and mark token as used
    user.hashed_password = hash_password(req.new_password)
    token_rec.is_used = True

    # Invalidate any other active reset tokens for this user
    db.query(PasswordResetTokenModel).filter(
        PasswordResetTokenModel.user_id == user.id,
        PasswordResetTokenModel.id != token_rec.id,
    ).update({"is_used": True})

    db.commit()

    return GenericAuthMessageResponse(
        message="Your password has been successfully reset. You may now sign in with your new password."
    )


@router.post("/change-password", response_model=GenericAuthMessageResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Allows an authenticated user to update their password.
    Requires verification of the current password and enforces minimum security rules.
    """
    # 1. Verify current password
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    # 2. Validate new password length
    if len(req.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters.",
        )

    # 3. Ensure new password is not identical to current
    if req.current_password == req.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password.",
        )

    # 4. Hash and save new password
    current_user.hashed_password = hash_password(req.new_password)

    # 5. Revoke any active password reset tokens
    db.query(PasswordResetTokenModel).filter(
        PasswordResetTokenModel.user_id == current_user.id,
        PasswordResetTokenModel.is_used == False,
    ).update({"is_used": True})

    db.commit()

    return GenericAuthMessageResponse(
        message="Your password has been successfully updated."
    )

