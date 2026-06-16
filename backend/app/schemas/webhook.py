from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from uuid import UUID
from datetime import datetime
from ..models.webhook import WebhookEventType, WebhookDeliveryStatus


class WebhookReceive(BaseModel):
    """Payload received at the merchant's webhook endpoint."""
    event_id: str
    event_type: str
    payload: Dict[str, Any]
    created_at: str


class WebhookEventResponse(BaseModel):
    id: UUID
    event_id: str
    event_type: WebhookEventType
    payment_id: Optional[UUID]
    order_id: Optional[UUID]
    refund_id: Optional[UUID]
    payload: str
    signature: str
    delivery_status: WebhookDeliveryStatus
    delivery_url: str
    attempt_count: int
    max_attempts: int
    next_retry_at: Optional[datetime]
    last_attempted_at: Optional[datetime]
    delivered_at: Optional[datetime]
    response_code: Optional[int]
    is_duplicate: bool
    hmac_verified: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookListResponse(BaseModel):
    total: int
    events: list[WebhookEventResponse]


class WebhookVerifyRequest(BaseModel):
    payload: str = Field(..., description="Raw JSON payload string")
    signature: str = Field(..., description="X-Razorpay-Signature header value")


class WebhookVerifyResponse(BaseModel):
    is_valid: bool
    message: str
