"""Admin Router — Dashboard stats, simulation controls, data reset"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.order import Order, OrderStatus
from ..models.payment import Payment, PaymentStatus, PaymentMethod, FailureReason
from ..models.webhook import WebhookEvent, WebhookDeliveryStatus
from ..models.refund import Refund, RefundStatus
from ..models.idempotency import IdempotencyKey
from ..services.retry_engine import retry_failed_webhooks

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)


@router.get(
    "/stats",
    summary="Dashboard statistics",
    description="Returns aggregated statistics for the dashboard.",
)
async def get_stats(db: Session = Depends(get_db)):
    # Orders
    total_orders = db.query(Order).count()
    orders_by_status = {
        s.value: db.query(Order).filter(Order.status == s).count()
        for s in OrderStatus
    }

    # Payments
    total_payments = db.query(Payment).count()
    payments_by_status = {
        s.value: db.query(Payment).filter(Payment.status == s).count()
        for s in PaymentStatus
    }
    total_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.CAPTURED
    ).scalar() or 0

    # Failure breakdown
    failure_breakdown = {}
    for reason in FailureReason:
        if reason != FailureReason.NONE:
            count = db.query(Payment).filter(Payment.failure_reason == reason).count()
            if count > 0:
                failure_breakdown[reason.value] = count

    # Webhooks
    total_webhooks = db.query(WebhookEvent).count()
    webhooks_by_status = {
        s.value: db.query(WebhookEvent).filter(WebhookEvent.delivery_status == s).count()
        for s in WebhookDeliveryStatus
    }
    duplicate_webhooks = db.query(WebhookEvent).filter(WebhookEvent.is_duplicate == True).count()  # noqa: E712

    # Refunds
    total_refunds = db.query(Refund).count()
    total_refunded_amount = db.query(func.sum(Refund.amount)).filter(
        Refund.status == RefundStatus.REFUNDED
    ).scalar() or 0

    # Idempotency
    total_idempotency_keys = db.query(IdempotencyKey).count()
    processed_keys = db.query(IdempotencyKey).filter(IdempotencyKey.is_processed == True).count()  # noqa: E712

    # Payment methods breakdown
    methods_breakdown = {}
    for method in PaymentMethod:
        count = db.query(Payment).filter(Payment.method == method).count()
        if count > 0:
            methods_breakdown[method.value] = count

    # Recent activity (last 24h)
    yesterday = datetime.utcnow() - timedelta(hours=24)
    recent_orders = db.query(Order).filter(Order.created_at >= yesterday).count()
    recent_payments = db.query(Payment).filter(Payment.created_at >= yesterday).count()

    return {
        "summary": {
            "total_orders": total_orders,
            "total_payments": total_payments,
            "total_revenue": round(total_revenue, 2),
            "total_refunds": total_refunds,
            "total_refunded_amount": round(total_refunded_amount, 2),
            "success_rate": round(
                payments_by_status.get("captured", 0) / total_payments * 100, 2
            ) if total_payments > 0 else 0.0,
        },
        "orders": {"total": total_orders, "by_status": orders_by_status, "recent_24h": recent_orders},
        "payments": {
            "total": total_payments,
            "by_status": payments_by_status,
            "by_method": methods_breakdown,
            "failure_breakdown": failure_breakdown,
            "recent_24h": recent_payments,
        },
        "webhooks": {
            "total": total_webhooks,
            "by_status": webhooks_by_status,
            "duplicates_detected": duplicate_webhooks,
        },
        "idempotency": {
            "total_keys": total_idempotency_keys,
            "processed": processed_keys,
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.post(
    "/retry-webhooks",
    summary="Manually trigger webhook retry processing",
)
async def trigger_retry():
    """Manually trigger the retry engine (useful for testing)."""
    retry_failed_webhooks()
    return {"status": "ok", "message": "Retry engine triggered"}


@router.delete(
    "/reset",
    summary="Reset all data (for testing)",
    description="⚠️ Deletes ALL records from the database. Use only in development/testing.",
)
async def reset_data(db: Session = Depends(get_db)):
    db.query(WebhookEvent).delete()
    db.query(Refund).delete()
    db.query(Payment).delete()
    db.query(Order).delete()
    db.query(IdempotencyKey).delete()
    db.commit()
    logger.warning("All data reset via admin endpoint")
    return {"status": "ok", "message": "All data has been reset"}


@router.get(
    "/scenarios",
    summary="List available failure scenarios",
)
async def list_scenarios():
    """Returns all available failure scenarios for testing."""
    return {
        "payment_failure_scenarios": [
            {"code": r.value, "description": r.value.replace("_", " ").title()}
            for r in FailureReason
            if r != FailureReason.NONE
        ],
        "webhook_pitfalls": [
            {"name": "HMAC Mismatch", "description": "Webhook signed with wrong secret — test signature verification"},
            {"name": "Duplicate Events", "description": "Same event delivered twice — test idempotent processing"},
            {"name": "Retry Exhaustion", "description": "Max retries reached — event marked EXHAUSTED"},
            {"name": "In-flight Idempotency", "description": "Same request in parallel — 409 Conflict returned"},
        ],
        "how_to_simulate": {
            "force_payment_failure": "Set simulate_failure field in POST /payments/process",
            "force_hmac_mismatch": "Add ?force_hmac_mismatch=true to POST /payments/process",
            "duplicate_webhook": "Process same payment twice",
            "idempotency_replay": "Send same request twice with identical Idempotency-Key header",
        }
    }
