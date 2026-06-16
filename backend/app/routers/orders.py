"""Orders Router — POST /orders, GET /orders, GET /orders/{order_ref}"""
import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models.order import Order, OrderStatus
from ..schemas.order import OrderCreate, OrderResponse, OrderListResponse
from ..services.idempotency import (
    check_idempotency, acquire_idempotency_lock,
    complete_idempotency, IdempotencyReplay, IdempotencyConflict
)

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = logging.getLogger(__name__)


def _generate_order_ref() -> str:
    return f"ord_{uuid.uuid4().hex[:12]}"


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    description="Creates a new payment order. Supports idempotency via `Idempotency-Key` header.",
)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    # ── Idempotency Check ──────────────────────────────────────────────────
    idem_key_record = None
    if idempotency_key:
        try:
            check_idempotency(db, idempotency_key, "/orders", order_data.model_dump())
        except IdempotencyReplay as e:
            logger.info(f"Idempotency replay for key: {idempotency_key}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content=json.loads(e.response_body),
                headers={"X-Idempotency-Replayed": "true"},
            )
        except IdempotencyConflict as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        idem_key_record = acquire_idempotency_lock(db, idempotency_key, "/orders", order_data.model_dump())

    # ── Create Order ───────────────────────────────────────────────────────
    order = Order(
        order_ref=_generate_order_ref(),
        merchant_id=order_data.merchant_id,
        customer_id=order_data.customer_id,
        customer_email=order_data.customer_email,
        amount=order_data.amount,
        currency=order_data.currency,
        description=order_data.description,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    response = OrderResponse.model_validate(order)
    logger.info(f"Order created: {order.order_ref} | amount={order.amount} {order.currency}")

    # ── Cache idempotent response ──────────────────────────────────────────
    if idem_key_record:
        complete_idempotency(db, idem_key_record, 201, response.model_dump_json())

    return response


@router.get(
    "/",
    response_model=OrderListResponse,
    summary="List all orders",
)
async def list_orders(
    merchant_id: Optional[str] = None,
    status: Optional[OrderStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Order)
    if merchant_id:
        query = query.filter(Order.merchant_id == merchant_id)
    if status:
        query = query.filter(Order.status == status)

    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    return OrderListResponse(total=total, orders=orders)


@router.get(
    "/{order_ref}",
    response_model=OrderResponse,
    summary="Get order by reference ID",
)
async def get_order(order_ref: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_ref == order_ref).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_ref}' not found")
    return order
