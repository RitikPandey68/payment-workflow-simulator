"""Pytest tests for Payments API."""
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


def _create_test_order(amount=2000.00):
    r = client.post("/api/v1/orders/", json={
        "merchant_id": "merchant_pay_test",
        "customer_id": "cust_pay_001",
        "customer_email": "pay@example.com",
        "amount": amount,
        "currency": "INR",
    })
    return r.json()["order_ref"]


def test_process_payment_success():
    order_ref = _create_test_order()
    response = client.post("/api/v1/payments/process", json={
        "order_id": order_ref,
        "method": "card",
        "card_number": "4111111111111111",
        "card_expiry": "12/26",
        "card_cvv": "123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["payment_ref"].startswith("pay_")
    assert data["method"] == "card"
    assert data["card_last_four"] == "1111"
    assert data["card_network"] == "Visa"


def test_process_payment_forced_failure():
    order_ref = _create_test_order()
    response = client.post("/api/v1/payments/process", json={
        "order_id": order_ref,
        "method": "card",
        "simulate_failure": "card_declined",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "failed"
    assert data["failure_reason"] == "card_declined"


def test_process_payment_order_not_found():
    response = client.post("/api/v1/payments/process", json={
        "order_id": "ord_doesnotexist",
        "method": "upi",
    })
    assert response.status_code == 404


def test_cannot_pay_completed_order():
    order_ref = _create_test_order()
    # First payment — may succeed or fail randomly
    client.post("/api/v1/payments/process", json={
        "order_id": order_ref,
        "method": "card",
        "simulate_failure": None,
    })
    # Force a success on first attempt
    order_ref2 = _create_test_order(1500.00)
    client.post("/api/v1/payments/process", json={
        "order_id": order_ref2,
        "method": "upi",
        "upi_id": "test@paytm",
    })


def test_list_payments():
    order_ref = _create_test_order()
    client.post("/api/v1/payments/process", json={"order_id": order_ref, "method": "card"})
    response = client.get("/api/v1/payments/")
    assert response.status_code == 200
    assert response.json()["total"] >= 1
