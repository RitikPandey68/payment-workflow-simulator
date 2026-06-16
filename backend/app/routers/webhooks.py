"""Webhooks Router — POST /webhooks/receive, GET /webhooks, POST /webhooks/verify"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.webhook import WebhookEvent, WebhookDeliveryStatus
from ..schemas.webhook import (
    WebhookReceive, WebhookEventResponse, WebhookListResponse,
    WebhookVerifyRequest, WebhookVerifyResponse
)
from ..services.webhook_dispatcher import verify_webhook_signature
from ..services.retry_engine import get_retry_stats

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)


@router.post(
    "/receive",
    status_code=status.HTTP_200_OK,
    summary="Merchant webhook endpoint (simulated)",
    description="""
    Simulates the merchant-side webhook receiver.
    Verifies HMAC-SHA256 signature and logs the event.
    This is the endpoint that Razorpay (or any gateway) would call.
    """,
)
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: Optional[str] = Header(None),
):
    raw_body = await request.body()
    payload_str = raw_body.decode("utf-8")

    # Verify HMAC signature
    hmac_valid = False
    if x_razorpay_signature:
        hmac_valid = verify_webhook_signature(payload_str, x_razorpay_signature)
        if not hmac_valid:
            logger.warning("HMAC signature mismatch on received webhook!")
            # In production: reject. For simulation: log and continue
            return {
                "status": "rejected",
                "reason": "HMAC signature mismatch",
                "hmac_valid": False,
            }

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(f"Webhook received: event={payload.get('event')} id={payload.get('event_id')}")
    return {
        "status": "ok",
        "event": payload.get("event"),
        "event_id": payload.get("event_id"),
        "hmac_valid": hmac_valid,
    }


@router.get(
    "/",
    response_model=WebhookListResponse,
    summary="List all webhook events",
)
async def list_webhooks(
    delivery_status: Optional[WebhookDeliveryStatus] = None,
    event_type: Optional[str] = None,
    duplicates_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(WebhookEvent)
    if delivery_status:
        query = query.filter(WebhookEvent.delivery_status == delivery_status)
    if event_type:
        query = query.filter(WebhookEvent.event_type == event_type)
    if duplicates_only:
        query = query.filter(WebhookEvent.is_duplicate == True)  # noqa: E712

    total = query.count()
    events = query.order_by(WebhookEvent.created_at.desc()).offset(offset).limit(limit).all()
    return WebhookListResponse(total=total, events=events)


@router.get(
    "/stats",
    summary="Get webhook retry statistics",
)
async def webhook_stats(db: Session = Depends(get_db)):
    return get_retry_stats(db)


@router.post(
    "/verify",
    response_model=WebhookVerifyResponse,
    summary="Verify a webhook HMAC signature",
    description="Allows merchants to test if their HMAC verification logic is correct.",
)
async def verify_webhook(body: WebhookVerifyRequest):
    is_valid = verify_webhook_signature(body.payload, body.signature)
    return WebhookVerifyResponse(
        is_valid=is_valid,
        message="Signature is valid ✓" if is_valid else "Signature mismatch ✗ — check your webhook secret",
    )


@router.get(
    "/{event_id}",
    response_model=WebhookEventResponse,
    summary="Get webhook event by ID",
)
async def get_webhook_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Webhook event '{event_id}' not found")
    return event
