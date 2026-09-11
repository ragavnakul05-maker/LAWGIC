import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.schemas import (
    UserModel,
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
)

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
