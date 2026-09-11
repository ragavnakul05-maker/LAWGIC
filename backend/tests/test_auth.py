import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.main import app
from app.models.schemas import UserModel

# In-memory SQLite engine for tests with StaticPool to retain tables across connections
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
        id="TEST-USER-001",
        email="testuser@lawgic.ai",
        full_name="Sarah Connor",
        role="Chief Legal Officer",
        hashed_password=hash_password("correctpassword"),
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


def test_password_hashing_and_verification():
    raw_password = "SecurePassword2026!"
    hashed = hash_password(raw_password)
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_generation_and_decoding():
    payload = {"sub": "USER-123", "email": "clerk@court.gov", "role": "Magistrate"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "USER-123"
    assert decoded["email"] == "clerk@court.gov"


def test_jwt_expired_token():
    payload = {"sub": "USER-123"}
    # Token that expired 5 seconds ago
    token = create_access_token(payload, expires_delta=timedelta(seconds=-5))
    decoded = decode_access_token(token)
    assert decoded is None


def test_login_success():
    res = client.post("/api/auth/login", json={
        "email": "testuser@lawgic.ai",
        "password": "correctpassword",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "testuser@lawgic.ai"
    assert data["user"]["role"] == "Chief Legal Officer"


def test_login_failure_wrong_password():
    res = client.post("/api/auth/login", json={
        "email": "testuser@lawgic.ai",
        "password": "wrongpassword123",
    })
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_register_new_user():
    res = client.post("/api/auth/register", json={
        "email": "newcounsel@lawgic.ai",
        "password": "mypassword123",
        "full_name": "Alexander Hamilton",
        "role": "Compliance Director",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "newcounsel@lawgic.ai"
    assert data["user"]["full_name"] == "Alexander Hamilton"
    assert data["user"]["role"] == "Compliance Director"


def test_register_duplicate_email():
    res = client.post("/api/auth/register", json={
        "email": "testuser@lawgic.ai",
        "password": "anotherpassword",
        "full_name": "Imposter",
    })
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"]


def test_get_me_authenticated():
    # 1. Login to get token
    login_res = client.post("/api/auth/login", json={
        "email": "testuser@lawgic.ai",
        "password": "correctpassword",
    })
    token = login_res.json()["access_token"]

    # 2. Call /api/auth/me with Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "testuser@lawgic.ai"
    assert me_data["full_name"] == "Sarah Connor"


def test_demo_users_endpoint():
    res = client.get("/api/auth/demo-users")
    assert res.status_code == 200
    demos = res.json()
    assert len(demos) >= 2
    emails = [d["email"] for d in demos]
    assert "admin@lawgic.ai" in emails
    assert "counsel@lawgic.ai" in emails
