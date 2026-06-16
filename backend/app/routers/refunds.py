"""Refunds Router — POST /refunds, GET /refunds"""
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.order import Order, OrderStatus
from ..models.payment import Payment, PaymentStatus
from ..models.refund import Refund, RefundStatus, RefundType
from ..schemas.refund import RefundCreate, RefundResponse, RefundListResponse
from ..services.webhook_dispatcher import dispatch_refund_webhook
from ..models.webhook import WebhookEventType

router = APIRouter(prefix="/refunds", tags=["Refunds"])
logger = logging.getLogger(__name__)


def _generate_refund_ref() -> str:
    return f"rfnd_{uuid.uuid4().hex[:10]}"


@router.post(
    "/",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a refund",
    description="""
    Initiates a full or partial refund on a captured payment.
    - If `amount` is omitted or equals payment amount → full refund
    - If `amount` < payment amount → partial refund
    - A webhook event is dispatched upon refund creation
    """,
)
async def create_refund(
    refund_data: RefundCreate,
    db: Session = Depends(get_db),
):
    # Fetch payment
    payment = db.query(Payment).filter(Payment.payment_ref == refund_data.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment '{refund_data.payment_id}' not found")

    if payment.status != PaymentStatus.CAPTURED:
        raise HTTPException(
            status_code=400,
            detail=f"Payment is not in 'captured' state (current: {payment.status.value}). Cannot refund.",
        )

    # Fetch order
    order = db.query(Order).filter(Order.id == payment.order_id).first()

    # Validate refund amount
    refund_amount = refund_data.amount or payment.amount
    if refund_amount > payment.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount ({refund_amount}) exceeds payment amount ({payment.amount})",
        )

    # Check existing refunds
    existing_refunds_total = sum(
        r.amount for r in db.query(Refund).filter(
            Refund.payment_id == payment.id,
            Refund.status == RefundStatus.REFUNDED,
        ).all()
    )
    if existing_refunds_total + refund_amount > payment.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Total refunds would exceed payment amount. Already refunded: {existing_refunds_total}",
        )

    refund_type = RefundType.FULL if refund_amount == payment.amount else RefundType.PARTIAL

    # Create refund
    refund = Refund(
        refund_ref=_generate_refund_ref(),
        order_id=payment.order_id,
        payment_id=payment.id,
        amount=refund_amount,
        currency=payment.currency,
        refund_type=refund_type,
        status=RefundStatus.REFUNDED,
        reason=refund_data.reason,
        notes=refund_data.notes,
        gateway_refund_id=f"grf_{uuid.uuid4().hex[:12]}",
        processed_at=datetime.utcnow(),
    )
    db.add(refund)

    # Update payment and order status
    payment.status = PaymentStatus.REFUNDED
    total_refunded = existing_refunds_total + refund_amount
    if total_refunded >= payment.amount:
        order.status = OrderStatus.REFUNDED
    else:
        order.status = OrderStatus.PARTIALLY_REFUNDED

    db.commit()
    db.refresh(refund)

    # Dispatch webhook events
    dispatch_refund_webhook(
        db=db, refund=refund, payment=payment,
        event_type=WebhookEventType.REFUND_CREATED,
    )
    dispatch_refund_webhook(
        db=db, refund=refund, payment=payment,
        event_type=WebhookEventType.REFUND_PROCESSED,
    )

    logger.info(f"Refund {refund.refund_ref} ({refund_type.value}) of {refund_amount} {refund.currency} processed")
    return refund


@router.get(
    "/",
    response_model=RefundListResponse,
    summary="List all refunds",
)
async def list_refunds(
    payment_ref: Optional[str] = None,
    status: Optional[RefundStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Refund)
    if payment_ref:
        payment = db.query(Payment).filter(Payment.payment_ref == payment_ref).first()
        if payment:
            query = query.filter(Refund.payment_id == payment.id)
    if status:
        query = query.filter(Refund.status == status)

    total = query.count()
    refunds = query.order_by(Refund.created_at.desc()).offset(offset).limit(limit).all()
    return RefundListResponse(total=total, refunds=refunds)


@router.get(
    "/{refund_ref}",
    response_model=RefundResponse,
    summary="Get refund by reference ID",
)
async def get_refund(refund_ref: str, db: Session = Depends(get_db)):
    refund = db.query(Refund).filter(Refund.refund_ref == refund_ref).first()
    if not refund:
        raise HTTPException(status_code=404, detail=f"Refund '{refund_ref}' not found")
    return refund
