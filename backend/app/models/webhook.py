import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum as SAEnum, Text, ForeignKey, Integer, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base


class WebhookEventType(str, enum.Enum):
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_FAILED = "payment.failed"
    REFUND_CREATED = "refund.created"
    REFUND_PROCESSED = "refund.processed"
    ORDER_PAID = "order.paid"
    ORDER_FAILED = "order.failed"


class WebhookDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    EXHAUSTED = "exhausted"  # max retries reached


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(50), unique=True, nullable=False, index=True)  # idempotency for events
    event_type = Column(SAEnum(WebhookEventType), nullable=False)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    refund_id = Column(UUID(as_uuid=True), ForeignKey("refunds.id"), nullable=True)

    payload = Column(Text, nullable=False)         # JSON payload sent to merchant
    signature = Column(String(256), nullable=False) # HMAC-SHA256 signature
    delivery_status = Column(SAEnum(WebhookDeliveryStatus), nullable=False, default=WebhookDeliveryStatus.PENDING)
    delivery_url = Column(String(512), nullable=False)

    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    next_retry_at = Column(DateTime, nullable=True)
    last_attempted_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    response_code = Column(Integer, nullable=True)   # HTTP status from merchant endpoint
    response_body = Column(Text, nullable=True)
    is_duplicate = Column(Boolean, default=False)    # flag if this was a duplicate event
    hmac_verified = Column(Boolean, nullable=True)   # whether merchant verified HMAC

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payment = relationship("Payment", back_populates="webhook_events")

    __table_args__ = (
        Index("idx_webhook_events_payment_id", "payment_id"),
        Index("idx_webhook_events_delivery_status", "delivery_status"),
        Index("idx_webhook_events_next_retry", "next_retry_at"),
    )

    def __repr__(self):
        return f"<WebhookEvent {self.event_id} type={self.event_type} status={self.delivery_status}>"
