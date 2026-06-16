"""Pytest tests for Webhooks API and HMAC verification."""
import pytest
import json
import hmac
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import get_settings

settings = get_settings()
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


def _sign(payload: str, secret: str = None) -> str:
    secret = secret or settings.WEBHOOK_SECRET
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def test_receive_webhook_valid_signature():
    payload = json.dumps({"event": "payment.captured", "event_id": "evt_test_001"})
    sig = _sign(payload)
    response = client.post(
        "/api/v1/webhooks/receive",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["hmac_valid"] is True


def test_receive_webhook_invalid_signature():
    payload = json.dumps({"event": "payment.captured", "event_id": "evt_test_002"})
    bad_sig = _sign(payload, secret="WRONG_SECRET")
    response = client.post(
        "/api/v1/webhooks/receive",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": bad_sig,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["hmac_valid"] is False


def test_verify_signature_endpoint_valid():
    payload_str = '{"event":"payment.captured","amount":100}'
    sig = _sign(payload_str)
    response = client.post("/api/v1/webhooks/verify", json={
        "payload": payload_str,
        "signature": sig,
    })
    assert response.status_code == 200
    assert response.json()["is_valid"] is True


def test_verify_signature_endpoint_invalid():
    response = client.post("/api/v1/webhooks/verify", json={
        "payload": '{"event":"payment.captured"}',
        "signature": "deadbeef" * 8,
    })
    assert response.status_code == 200
    assert response.json()["is_valid"] is False


def test_webhook_stats():
    response = client.get("/api/v1/webhooks/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "delivered" in data
    assert "delivery_rate" in data


def test_list_webhooks():
    response = client.get("/api/v1/webhooks/")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "events" in data
