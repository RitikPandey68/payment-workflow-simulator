from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from ..models.payment import PaymentStatus, PaymentMethod, FailureReason


class PaymentProcess(BaseModel):
    order_id: str = Field(..., example="ord_abc123")
    method: PaymentMethod = Field(default=PaymentMethod.CARD, example="card")
    card_number: Optional[str] = Field(None, example="4111111111111111")
    card_expiry: Optional[str] = Field(None, example="12/26")
    card_cvv: Optional[str] = Field(None, example="123")
    upi_id: Optional[str] = Field(None, example="customer@paytm")
    simulate_failure: Optional[FailureReason] = Field(
        None,
        description="Force a specific failure scenario for testing",
        example="card_declined"
    )


class PaymentResponse(BaseModel):
    id: UUID
    payment_ref: str
    order_id: UUID
    amount: float
    currency: str
    status: PaymentStatus
    method: PaymentMethod
    failure_reason: Optional[FailureReason]
    gateway_transaction_id: Optional[str]
    card_last_four: Optional[str]
    card_network: Optional[str]
    attempts: int
    processing_time_ms: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    total: int
    payments: list[PaymentResponse]
