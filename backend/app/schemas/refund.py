from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from ..models.refund import RefundStatus, RefundType


class RefundCreate(BaseModel):
    payment_id: str = Field(..., example="pay_abc123")
    amount: Optional[float] = Field(
        None,
        description="Amount to refund. If not specified, full refund is processed.",
        example=999.00
    )
    reason: Optional[str] = Field(None, max_length=255, example="Customer request")
    notes: Optional[str] = Field(None, max_length=1000)


class RefundResponse(BaseModel):
    id: UUID
    refund_ref: str
    order_id: UUID
    payment_id: UUID
    amount: float
    currency: str
    refund_type: RefundType
    status: RefundStatus
    reason: Optional[str]
    notes: Optional[str]
    gateway_refund_id: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class RefundListResponse(BaseModel):
    total: int
    refunds: list[RefundResponse]
