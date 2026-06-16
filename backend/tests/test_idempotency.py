"""Pytest tests for Idempotency — duplicate detection and replay."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

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

ORDER_PAYLOAD = {
    "merchant_id": "merchant_idem",
    "customer_id": "cust_idem_001",
    "customer_email": "idem@example.com",
    "amount": 750.00,
    "currency": "INR",
    "description": "Idempotency Test",
}


def test_idempotency_first_request_creates_order():
    headers = {"Idempotency-Key": "idem-test-key-alpha"}
    r = client.post("/api/v1/orders/", json=ORDER_PAYLOAD, headers=headers)
    assert r.status_code == 201
    assert r.json()["order_ref"].startswith("ord_")
    assert "X-Idempotency-Replayed" not in r.headers


def test_idempotency_second_request_replays():
    headers = {"Idempotency-Key": "idem-test-key-beta"}
    r1 = client.post("/api/v1/orders/", json=ORDER_PAYLOAD, headers=headers)
    assert r1.status_code == 201
    original_ref = r1.json()["order_ref"]

    r2 = client.post("/api/v1/orders/", json=ORDER_PAYLOAD, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["order_ref"] == original_ref
    assert r2.headers.get("X-Idempotency-Replayed") == "true"


def test_different_idempotency_keys_create_separate_orders():
    r1 = client.post("/api/v1/orders/", json=ORDER_PAYLOAD, headers={"Idempotency-Key": "key-gamma-1"})
    r2 = client.post("/api/v1/orders/", json=ORDER_PAYLOAD, headers={"Idempotency-Key": "key-gamma-2"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["order_ref"] != r2.json()["order_ref"]


def test_no_idempotency_key_always_creates():
    r1 = client.post("/api/v1/orders/", json=ORDER_PAYLOAD)
    r2 = client.post("/api/v1/orders/", json=ORDER_PAYLOAD)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["order_ref"] != r2.json()["order_ref"]
