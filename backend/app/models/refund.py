import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    REFUNDED = "refunded"
    FAILED = "failed"


class RefundType(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refund_ref = Column(String(50), unique=True, nullable=False, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    refund_type = Column(SAEnum(RefundType), nullable=False)
    status = Column(SAEnum(RefundStatus), nullable=False, default=RefundStatus.PENDING)
    reason = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    gateway_refund_id = Column(String(100), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order = relationship("Order", back_populates="refunds")

    __table_args__ = (
        Index("idx_refunds_order_id", "order_id"),
        Index("idx_refunds_payment_id", "payment_id"),
        Index("idx_refunds_status", "status"),
    )

    def __repr__(self):
        return f"<Refund {self.refund_ref} status={self.status} amount={self.amount}>"
