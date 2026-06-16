"""Payments Router — POST /payments/process, GET /payments"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.order import Order, OrderStatus
from ..models.payment import Payment, PaymentMethod, FailureReason
from ..schemas.payment import PaymentProcess, PaymentResponse, PaymentListResponse
from ..services.payment_processor import process_payment
from ..services.webhook_dispatcher import dispatch_payment_webhook
from ..models.webhook import WebhookEventType

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = logging.getLogger(__name__)


@router.post(
    "/process",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process a payment for an order",
    description="""
    Processes a payment for the given order. Supports:
    - Multiple payment methods (card, UPI, netbanking, wallet)
    - Forced failure simulation via `simulate_failure` field
    - Automatic webhook dispatch after processing
    - Random failure injection (configurable rate via env)
    """,
)
async def process_payment_endpoint(
    payment_data: PaymentProcess,
    force_hmac_mismatch: bool = False,
    db: Session = Depends(get_db),
):
    # Fetch order by order_ref
    order = db.query(Order).filter(Order.order_ref == payment_data.order_id).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Order '{payment_data.order_id}' not found",
        )

    # Validate order state
    if order.status == OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Order '{order.order_ref}' is already completed",
        )
    if order.status == OrderStatus.REFUNDED:
        raise HTTPException(
            status_code=400,
            detail=f"Order '{order.order_ref}' has been refunded",
        )

    # Update order to processing
    order.status = OrderStatus.PROCESSING
    db.commit()

    # ── Process Payment ────────────────────────────────────────────────────
    payment = process_payment(
        db=db,
        order=order,
        method=payment_data.method,
        card_number=payment_data.card_number,
        card_expiry=payment_data.card_expiry,
        card_cvv=payment_data.card_cvv,
        upi_id=payment_data.upi_id,
        simulate_failure=payment_data.simulate_failure,
    )

    # ── Dispatch Webhook ───────────────────────────────────────────────────
    event_type = (
        WebhookEventType.PAYMENT_CAPTURED
        if payment.status.value == "captured"
        else WebhookEventType.PAYMENT_FAILED
    )
    dispatch_payment_webhook(
        db=db,
        payment=payment,
        order=order,
        event_type=event_type,
        force_hmac_mismatch=force_hmac_mismatch,
    )

    # Also fire order.paid if payment succeeded
    if event_type == WebhookEventType.PAYMENT_CAPTURED:
        dispatch_payment_webhook(
            db=db,
            payment=payment,
            order=order,
            event_type=WebhookEventType.ORDER_PAID,
        )

    return payment


@router.get(
    "/",
    response_model=PaymentListResponse,
    summary="List all payments",
)
async def list_payments(
    order_ref: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Payment)
    if order_ref:
        order = db.query(Order).filter(Order.order_ref == order_ref).first()
        if order:
            query = query.filter(Payment.order_id == order.id)

    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(offset).limit(limit).all()
    return PaymentListResponse(total=total, payments=payments)


@router.get(
    "/{payment_ref}",
    response_model=PaymentResponse,
    summary="Get payment by reference ID",
)
async def get_payment(payment_ref: str, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.payment_ref == payment_ref).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment '{payment_ref}' not found")
    return payment
