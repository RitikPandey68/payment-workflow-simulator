"""Pytest tests for Orders API."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# ── Test Database ──────────────────────────────────────────────────────────────
# Import models to register them with SQLAlchemy Base
from app.models import Order, Payment, WebhookEvent, Refund, IdempotencyKey
from sqlalchemy.pool import StaticPool

SQLALCHEMY_TEST_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


client = TestClient(app)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_create_order_success():
    response = client.post("/api/v1/orders/", json={
        "merchant_id": "merchant_test",
        "customer_id": "cust_001",
        "customer_email": "test@example.com",
        "amount": 1999.00,
        "currency": "INR",
        "description": "Test Order",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["merchant_id"] == "merchant_test"
    assert data["amount"] == 1999.00
    assert data["status"] == "pending"
    assert data["order_ref"].startswith("ord_")


def test_create_order_invalid_amount():
    response = client.post("/api/v1/orders/", json={
        "merchant_id": "merchant_test",
        "customer_id": "cust_001",
        "customer_email": "test@example.com",
        "amount": -100,
        "currency": "INR",
    })
    assert response.status_code == 422


def test_idempotency_replay():
    payload = {
        "merchant_id": "merchant_test",
        "customer_id": "cust_002",
        "customer_email": "idem@example.com",
        "amount": 500.00,
        "currency": "INR",
    }
    headers = {"Idempotency-Key": "test-idem-key-001"}

    # First request
    r1 = client.post("/api/v1/orders/", json=payload, headers=headers)
    assert r1.status_code == 201
    order_ref_1 = r1.json()["order_ref"]

    # Second request with same key — should replay
    r2 = client.post("/api/v1/orders/", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r2.headers.get("X-Idempotency-Replayed") == "true"
    assert r2.json()["order_ref"] == order_ref_1


def test_get_order_not_found():
    response = client.get("/api/v1/orders/ord_doesnotexist")
    assert response.status_code == 404


def test_list_orders():
    for i in range(3):
        client.post("/api/v1/orders/", json={
            "merchant_id": "merchant_list_test",
            "customer_id": f"cust_{i}",
            "customer_email": f"test{i}@example.com",
            "amount": 100 * (i + 1),
            "currency": "INR",
        })

    response = client.get("/api/v1/orders/?merchant_id=merchant_list_test")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["orders"]) == 3
