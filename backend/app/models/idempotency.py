import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from ..database import Base


class IdempotencyKey(Base):
    """
    Stores idempotency keys to prevent duplicate request processing.
    When a request with the same key arrives, the cached response is returned.
    """
    __tablename__ = "idempotency_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), unique=True, nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)       # which endpoint this key belongs to
    request_hash = Column(String(64), nullable=False)    # SHA-256 of the request body
    response_status = Column(String(10), nullable=True)  # HTTP status code cached
    response_body = Column(Text, nullable=True)          # Cached JSON response
    is_processed = Column(Boolean, default=False)
    lock_acquired_at = Column(DateTime, nullable=True)   # for in-flight detection
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)         # TTL for key expiry

    __table_args__ = (
        Index("idx_idempotency_key_endpoint", "key", "endpoint"),
    )

    def __repr__(self):
        return f"<IdempotencyKey key={self.key} processed={self.is_processed}>"
