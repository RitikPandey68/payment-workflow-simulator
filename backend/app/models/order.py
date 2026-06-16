import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..database import Base


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_ref = Column(String(50), unique=True, nullable=False, index=True)
    merchant_id = Column(String(100), nullable=False, index=True)
    customer_id = Column(String(100), nullable=False)
    customer_email = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON string for extra metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_orders_merchant_status", "merchant_id", "status"),
        Index("idx_orders_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Order {self.order_ref} status={self.status} amount={self.amount} {self.currency}>"
