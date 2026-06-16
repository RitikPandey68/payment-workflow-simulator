import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"


class FailureReason(str, enum.Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    NETWORK_TIMEOUT = "network_timeout"
    INVALID_CVV = "invalid_cvv"
    EXPIRED_CARD = "expired_card"
    FRAUD_DETECTED = "fraud_detected"
    NONE = "none"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_ref = Column(String(50), unique=True, nullable=False, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(SAEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    method = Column(SAEnum(PaymentMethod), nullable=False, default=PaymentMethod.CARD)
    failure_reason = Column(SAEnum(FailureReason), nullable=True, default=FailureReason.NONE)
    gateway_transaction_id = Column(String(100), nullable=True)
    card_last_four = Column(String(4), nullable=True)
    card_network = Column(String(20), nullable=True)
    attempts = Column(Integer, default=1)
    processing_time_ms = Column(Integer, nullable=True)  # simulated processing time
    raw_response = Column(Text, nullable=True)  # JSON string of gateway response
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order = relationship("Order", back_populates="payments")
    webhook_events = relationship("WebhookEvent", back_populates="payment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_payments_order_id", "order_id"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Payment {self.payment_ref} status={self.status} amount={self.amount}>"
