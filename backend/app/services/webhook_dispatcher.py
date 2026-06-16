"""
Webhook Dispatcher Service
Handles HMAC-SHA256 signing, simulated delivery, duplicate detection,
and the retry queue for failed deliveries — replicating Razorpay's
webhook system behaviour.
"""
import uuid
import json
import hmac
import hashlib
import random
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models.payment import Payment
from ..models.refund import Refund
from ..models.order import Order
from ..models.webhook import WebhookEvent, WebhookEventType, WebhookDeliveryStatus
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _generate_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:16]}"


def _sign_payload(payload: str, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature exactly like Razorpay:
      signature = HMAC-SHA256(payload, webhook_secret)
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(payload: str, signature: str, secret: str | None = None) -> bool:
    """
    Verify an incoming webhook signature.
    This is what merchants should implement on their end.
    """
    secret = secret or settings.WEBHOOK_SECRET
    expected = _sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


def _build_payment_payload(payment: Payment, order: Order, event_type: WebhookEventType) -> dict:
    return {
        "event": event_type.value,
        "payload": {
            "payment": {
                "entity": {
                    "id": payment.payment_ref,
                    "order_id": order.order_ref,
                    "amount": int(payment.amount * 100),  # paise like Razorpay
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "method": payment.method.value,
                    "card_last_four": payment.card_last_four,
                    "card_network": payment.card_network,
                    "failure_reason": payment.failure_reason.value if payment.failure_reason else None,
                    "gateway_transaction_id": payment.gateway_transaction_id,
                    "created_at": int(payment.created_at.timestamp()),
                }
            },
            "order": {
                "entity": {
                    "id": order.order_ref,
                    "merchant_id": order.merchant_id,
                    "amount": int(order.amount * 100),
                    "currency": order.currency,
                    "status": order.status.value,
                    "customer_id": order.customer_id,
                    "customer_email": order.customer_email,
                }
            }
        }
    }


def _build_refund_payload(refund: Refund, payment: Payment, event_type: WebhookEventType) -> dict:
    return {
        "event": event_type.value,
        "payload": {
            "refund": {
                "entity": {
                    "id": refund.refund_ref,
                    "payment_id": payment.payment_ref,
                    "amount": int(refund.amount * 100),
                    "currency": refund.currency,
                    "status": refund.status.value,
                    "type": refund.refund_type.value,
                    "reason": refund.reason,
                    "created_at": int(refund.created_at.timestamp()),
                }
            }
        }
    }


def dispatch_payment_webhook(
    db: Session,
    payment: Payment,
    order: Order,
    event_type: WebhookEventType,
    force_hmac_mismatch: bool = False,
) -> WebhookEvent:
    """
    Dispatch a webhook event for a payment.
    - Signs payload with HMAC-SHA256
    - Simulates delivery with configurable failure rate
    - Records delivery attempt in DB
    """
    event_id = _generate_event_id()

    # Check for duplicate event (same payment + event type)
    existing = db.query(WebhookEvent).filter(
        WebhookEvent.payment_id == payment.id,
        WebhookEvent.event_type == event_type,
        WebhookEvent.is_duplicate == False,  # noqa: E712
    ).first()
    is_duplicate = existing is not None

    payload_dict = _build_payment_payload(payment, order, event_type)
    payload_dict["event_id"] = event_id
    payload_dict["created_at"] = datetime.utcnow().isoformat()
    payload_str = json.dumps(payload_dict, sort_keys=True)

    # Sign with correct or intentionally wrong secret for HMAC mismatch simulation
    sign_secret = "WRONG_SECRET_FOR_TESTING" if force_hmac_mismatch else settings.WEBHOOK_SECRET
    signature = _sign_payload(payload_str, sign_secret)

    # Simulate delivery
    delivery_failed = random.random() < settings.WEBHOOK_DELIVERY_FAILURE_RATE
    delivery_status = WebhookDeliveryStatus.FAILED if delivery_failed else WebhookDeliveryStatus.DELIVERED
    response_code = random.choice([500, 502, 503, 408]) if delivery_failed else 200
    next_retry_at = datetime.utcnow() + timedelta(seconds=settings.RETRY_BASE_DELAY) if delivery_failed else None
    delivered_at = datetime.utcnow() if not delivery_failed else None

    webhook_event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payment_id=payment.id,
        order_id=order.id,
        payload=payload_str,
        signature=signature,
        delivery_status=WebhookDeliveryStatus.RETRYING if delivery_failed else WebhookDeliveryStatus.DELIVERED,
        delivery_url=settings.WEBHOOK_ENDPOINT_URL,
        attempt_count=1,
        max_attempts=settings.MAX_RETRY_ATTEMPTS,
        next_retry_at=next_retry_at,
        last_attempted_at=datetime.utcnow(),
        delivered_at=delivered_at,
        response_code=response_code,
        response_body='{"status": "ok"}' if not delivery_failed else '{"error": "Internal Server Error"}',
        is_duplicate=is_duplicate,
        hmac_verified=not force_hmac_mismatch,
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)

    log_msg = f"Webhook {event_id} ({event_type.value}): {'DELIVERED' if not delivery_failed else 'FAILED → queued for retry'}"
    if is_duplicate:
        log_msg += " [DUPLICATE EVENT]"
    logger.info(log_msg)

    return webhook_event


def dispatch_refund_webhook(
    db: Session,
    refund: Refund,
    payment: Payment,
    event_type: WebhookEventType,
) -> WebhookEvent:
    """Dispatch a webhook event for a refund."""
    event_id = _generate_event_id()
    payload_dict = _build_refund_payload(refund, payment, event_type)
    payload_dict["event_id"] = event_id
    payload_dict["created_at"] = datetime.utcnow().isoformat()
    payload_str = json.dumps(payload_dict, sort_keys=True)
    signature = _sign_payload(payload_str, settings.WEBHOOK_SECRET)

    delivery_failed = random.random() < settings.WEBHOOK_DELIVERY_FAILURE_RATE
    delivered_at = datetime.utcnow() if not delivery_failed else None
    next_retry_at = datetime.utcnow() + timedelta(seconds=settings.RETRY_BASE_DELAY) if delivery_failed else None

    webhook_event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payment_id=payment.id,
        order_id=refund.order_id,
        refund_id=refund.id,
        payload=payload_str,
        signature=signature,
        delivery_status=WebhookDeliveryStatus.RETRYING if delivery_failed else WebhookDeliveryStatus.DELIVERED,
        delivery_url=settings.WEBHOOK_ENDPOINT_URL,
        attempt_count=1,
        max_attempts=settings.MAX_RETRY_ATTEMPTS,
        next_retry_at=next_retry_at,
        last_attempted_at=datetime.utcnow(),
        delivered_at=delivered_at,
        response_code=200 if not delivery_failed else 500,
        is_duplicate=False,
        hmac_verified=True,
    )
    db.add(webhook_event)
    db.commit()
    db.refresh(webhook_event)
    return webhook_event
