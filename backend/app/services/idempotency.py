"""
Idempotency Service
Prevents duplicate request processing by checking and storing idempotency keys.
Implements the idempotency pattern:
  1. Check if key exists and is processed → return cached response
  2. If in-flight (not processed) → return 409 Conflict
  3. If new → process request, cache response
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models.idempotency import IdempotencyKey

logger = logging.getLogger(__name__)

KEY_TTL_HOURS = 24  # Idempotency keys expire after 24 hours


def _hash_request(body: dict | str) -> str:
    """SHA-256 hash of the request body for integrity check."""
    if isinstance(body, dict):
        body = json.dumps(body, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


class IdempotencyConflict(Exception):
    """Raised when an idempotency key is currently being processed."""
    pass


class IdempotencyReplay(Exception):
    """Raised when an idempotency key has already been processed — carry cached response."""
    def __init__(self, status_code: int, response_body: str):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__("Replaying idempotent response")


def check_idempotency(
    db: Session,
    key: str,
    endpoint: str,
    request_body: dict | str,
) -> None:
    """
    Check idempotency key before processing a request.

    Raises:
      IdempotencyReplay: if the request was already processed
      IdempotencyConflict: if the request is currently being processed
    """
    request_hash = _hash_request(request_body)

    existing = db.query(IdempotencyKey).filter(
        IdempotencyKey.key == key,
        IdempotencyKey.endpoint == endpoint,
    ).first()

    if existing:
        # Check TTL
        if existing.expires_at and existing.expires_at < datetime.utcnow():
            # Key expired — treat as new
            db.delete(existing)
            db.commit()
            logger.info(f"Idempotency key {key} expired, treating as new request")
        elif existing.is_processed:
            logger.info(f"Replaying idempotent response for key {key}")
            raise IdempotencyReplay(
                status_code=int(existing.response_status or 200),
                response_body=existing.response_body or "{}",
            )
        elif existing.lock_acquired_at:
            # In-flight check: if lock is more than 30s old, assume stale and clear
            stale_threshold = datetime.utcnow() - timedelta(seconds=30)
            if existing.lock_acquired_at < stale_threshold:
                existing.lock_acquired_at = datetime.utcnow()
                db.commit()
            else:
                raise IdempotencyConflict(
                    f"Request with idempotency key '{key}' is currently being processed"
                )


def acquire_idempotency_lock(
    db: Session,
    key: str,
    endpoint: str,
    request_body: dict | str,
) -> IdempotencyKey:
    """Acquire lock on an idempotency key before processing."""
    request_hash = _hash_request(request_body)

    # Clean up expired keys first
    db.query(IdempotencyKey).filter(
        IdempotencyKey.expires_at < datetime.utcnow()
    ).delete(synchronize_session=False)

    idem_key = IdempotencyKey(
        key=key,
        endpoint=endpoint,
        request_hash=request_hash,
        is_processed=False,
        lock_acquired_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=KEY_TTL_HOURS),
    )
    db.add(idem_key)
    db.commit()
    db.refresh(idem_key)
    return idem_key


def complete_idempotency(
    db: Session,
    idem_key: IdempotencyKey,
    response_status: int,
    response_body: str,
) -> None:
    """Mark an idempotency key as processed and cache the response."""
    idem_key.is_processed = True
    idem_key.response_status = str(response_status)
    idem_key.response_body = response_body
    idem_key.lock_acquired_at = None
    db.commit()
    logger.debug(f"Idempotency key {idem_key.key} marked as processed")
