import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, migrate_db
from app.core.security import hash_password
from app.main import app
from app.models.schemas import UserModel, ContractModel, ClauseModel, RuleModel, LegalIR

# In-memory SQLite engine for tests with StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_multi_user_db():
    Base.metadata.create_all(bind=test_engine)
    migrate_db(bind_engine=test_engine)
    db = TestingSessionLocal()

    # Pre-seed demo user with a demo contract
    demo_user = UserModel(
        id="USER-DEMO-001",
        email="admin@lawgic.ai",
        full_name="Dr. Eleanor Vance",
        role="Chief Legal Officer",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db.add(demo_user)

    demo_contract = ContractModel(
        id="DEMO-CONTRACT-001",
        user_id="USER-DEMO-001",
        title="ABC Tech Master Supplier Agreement",
        filename="ABC_Tech_Supplier_Agreement.pdf",
        file_type="PDF",
        file_path="uploads/demo.pdf",
        page_count=3,
        status="ANALYZED",
    )
    db.add(demo_contract)
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


def register_and_get_token(email: str, password: str, name: str) -> tuple[str, str]:
    """Registers a user and returns (user_id, bearer_token)."""
    res = client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "full_name": name,
    })
    assert res.status_code in (200, 201), f"Registration failed: {res.text}"
    data = res.json()
    return data["user"]["id"], data["access_token"]


def create_sample_text_file(content: str) -> io.BytesIO:
    bio = io.BytesIO(content.encode("utf-8"))
    return bio


def test_multi_user_contract_upload_and_list_isolation():
    """
    Test that User A and User B only see their own uploaded contracts,
    and neither user sees the other's contract or unowned demo contracts.
    """
    user_a_id, token_a = register_and_get_token("user_a@lawgic.ai", "passA123!", "Alice Attorney")
    user_b_id, token_b = register_and_get_token("user_b@lawgic.ai", "passB123!", "Bob Barrister")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Contract A text
    contract_a_content = (
        "MASTER SERVICES AGREEMENT\n"
        "Section 1.1 Late Payment Interest\n"
        "Payments past 30 days incur 1.5% interest per month up to 15%.\n"
    )
    # Contract B text
    contract_b_content = (
        "SUPPLY AGREEMENT\n"
        "Section 2.1 Delivery Delay Penalty\n"
        "Delay beyond 10 days incurs 2% penalty per week up to 10% maximum.\n"
    )

    # 1. User A uploads Contract A
    res_upload_a = client.post(
        "/api/contracts/upload",
        files={"file": ("Contract_Alice.txt", create_sample_text_file(contract_a_content), "text/plain")},
        headers=headers_a,
    )
    assert res_upload_a.status_code == 200, f"Upload A failed: {res_upload_a.text}"
    contract_a_id = res_upload_a.json()["contract_id"]

    # 2. User B uploads Contract B
    res_upload_b = client.post(
        "/api/contracts/upload",
        files={"file": ("Contract_Bob.txt", create_sample_text_file(contract_b_content), "text/plain")},
        headers=headers_b,
    )
    assert res_upload_b.status_code == 200, f"Upload B failed: {res_upload_b.text}"
    contract_b_id = res_upload_b.json()["contract_id"]

    # 3. User A lists contracts -> ONLY Contract A
    list_a = client.get("/api/contracts", headers=headers_a).json()
    contract_ids_a = [c["id"] for c in list_a]
    assert contract_a_id in contract_ids_a
    assert contract_b_id not in contract_ids_a
    assert "DEMO-CONTRACT-001" not in contract_ids_a
    assert len(list_a) == 1

    # 4. User B lists contracts -> ONLY Contract B
    list_b = client.get("/api/contracts", headers=headers_b).json()
    contract_ids_b = [c["id"] for c in list_b]
    assert contract_b_id in contract_ids_b
    assert contract_a_id not in contract_ids_b
    assert "DEMO-CONTRACT-001" not in contract_ids_b
    assert len(list_b) == 1

    # 5. User A tries to GET Contract B by ID -> 404 Not Found
    detail_b_as_a = client.get(f"/api/contracts/{contract_b_id}", headers=headers_a)
    assert detail_b_as_a.status_code == 404

    # 6. User B tries to GET Contract A by ID -> 404 Not Found
    detail_a_as_b = client.get(f"/api/contracts/{contract_a_id}", headers=headers_b)
    assert detail_a_as_b.status_code == 404

    # 7. User A can access own Contract A
    detail_a_as_a = client.get(f"/api/contracts/{contract_a_id}", headers=headers_a)
    assert detail_a_as_a.status_code == 200
    assert detail_a_as_a.json()["id"] == contract_a_id

    # 8. User B can access own Contract B
    detail_b_as_b = client.get(f"/api/contracts/{contract_b_id}", headers=headers_b)
    assert detail_b_as_b.status_code == 200
    assert detail_b_as_b.json()["id"] == contract_b_id


def test_cross_user_execution_and_simulation_blocked():
    """
    Test that User A cannot execute rules or run simulations on User B's contract,
    and vice versa.
    """
    _, token_a = register_and_get_token("alice@lawgic.ai", "passA123!", "Alice")
    _, token_b = register_and_get_token("bob@lawgic.ai", "passB123!", "Bob")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    contract_content = "Section 1.1 Late fee: 1.5% per month after 30 days.\n"
    res = client.post(
        "/api/contracts/upload",
        files={"file": ("AliceContract.txt", create_sample_text_file(contract_content), "text/plain")},
        headers=headers_a,
    )
    contract_a_id = res.json()["contract_id"]

    # Bob tries to execute rules on Alice's contract -> 404
    exec_res = client.post(
        "/api/rules/execute",
        json={"contract_id": contract_a_id, "variables": {"payment_delay_days": 45}},
        headers=headers_b,
    )
    assert exec_res.status_code == 404

    # Bob tries to run simulation on Alice's contract -> 404
    sim_res = client.post(
        "/api/simulations/run",
        json={
            "contract_id": contract_a_id,
            "baseline_variables": {"payment_delay_days": 10},
            "scenarios": [{"scenario_name": "Test", "variable_overrides": {"payment_delay_days": 40}}],
        },
        headers=headers_b,
    )
    assert sim_res.status_code == 404

    # Alice can successfully execute rules on her own contract
    alice_exec = client.post(
        "/api/rules/execute",
        json={"contract_id": contract_a_id, "variables": {"payment_delay_days": 45, "invoice_amount": 50000}},
        headers=headers_a,
    )
    assert alice_exec.status_code == 200
    exec_id = alice_exec.json()["execution_id"]

    # Bob cannot view Alice's execution audit trail
    bob_trail = client.get(f"/api/audit/executions/{exec_id}", headers=headers_b)
    assert bob_trail.status_code == 404

    # Alice CAN view her own execution audit trail
    alice_trail = client.get(f"/api/audit/executions/{exec_id}", headers=headers_a)
    assert alice_trail.status_code == 200
    assert alice_trail.json()["execution_id"] == exec_id


def test_dashboard_metrics_data_isolation():
    """
    Test that dashboard metrics are completely isolated per user.
    """
    _, token_a = register_and_get_token("user_metric_a@lawgic.ai", "pass1234", "User MA")
    _, token_b = register_and_get_token("user_metric_b@lawgic.ai", "pass1234", "User MB")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Initially both users should see 0 contracts on dashboard
    dash_a = client.get("/api/dashboard/summary", headers=headers_a).json()
    assert dash_a["metrics"]["total_contracts"] == 0
    assert len(dash_a["recent_contracts"]) == 0

    dash_b = client.get("/api/dashboard/summary", headers=headers_b).json()
    assert dash_b["metrics"]["total_contracts"] == 0

    # User A uploads a contract
    content = "Section 1.1 Late fee: 1.5% per month after 30 days.\n"
    client.post(
        "/api/contracts/upload",
        files={"file": ("TestDoc.txt", create_sample_text_file(content), "text/plain")},
        headers=headers_a,
    )

    # Now User A has 1 contract, User B still has 0
    dash_a_after = client.get("/api/dashboard/summary", headers=headers_a).json()
    assert dash_a_after["metrics"]["total_contracts"] == 1
    assert len(dash_a_after["recent_contracts"]) == 1

    dash_b_after = client.get("/api/dashboard/summary", headers=headers_b).json()
    assert dash_b_after["metrics"]["total_contracts"] == 0
    assert len(dash_b_after["recent_contracts"]) == 0
