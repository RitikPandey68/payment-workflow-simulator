"""
Retry Engine Service
Implements exponential backoff retry logic for failed webhook deliveries.
Uses APScheduler for background scheduling.

Retry schedule (base_delay=1s, multiplier=2):
  Attempt 1: immediate
  Attempt 2: 1s delay
  Attempt 3: 2s delay
  Attempt 4: 4s delay
  Attempt 5: 8s delay (max 5 attempts, then EXHAUSTED)
"""
import logging
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models.webhook import WebhookEvent, WebhookDeliveryStatus
from ..database import SessionLocal
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _calculate_next_retry(attempt: int, base_delay: float = None) -> datetime:
    """Exponential backoff: delay = base_delay * (2 ** (attempt - 1))"""
    base = base_delay or settings.RETRY_BASE_DELAY
    delay_seconds = base * (2 ** (attempt - 1))
    # Add jitter (±20%) to avoid thundering herd
    jitter = delay_seconds * random.uniform(-0.2, 0.2)
    total_delay = max(0.5, delay_seconds + jitter)
    return datetime.utcnow() + timedelta(seconds=total_delay)


def retry_failed_webhooks():
    """
    Background job: picks up all RETRYING webhooks whose next_retry_at has passed
    and attempts re-delivery with simulated success/failure.
    """
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        pending_retries = db.query(WebhookEvent).filter(
            WebhookEvent.delivery_status == WebhookDeliveryStatus.RETRYING,
            WebhookEvent.next_retry_at <= now,
            WebhookEvent.attempt_count < WebhookEvent.max_attempts,
        ).all()

        for event in pending_retries:
            event.attempt_count += 1
            event.last_attempted_at = now

            # Simulate delivery — higher success chance on retry
            delivery_success_chance = 0.5 + (event.attempt_count * 0.1)
            succeeded = random.random() < delivery_success_chance

            if succeeded:
                event.delivery_status = WebhookDeliveryStatus.DELIVERED
                event.response_code = 200
                event.delivered_at = now
                event.next_retry_at = None
                logger.info(
                    f"Retry #{event.attempt_count} SUCCEEDED for webhook {event.event_id}"
                )
            else:
                if event.attempt_count >= event.max_attempts:
                    event.delivery_status = WebhookDeliveryStatus.EXHAUSTED
                    event.next_retry_at = None
                    event.response_code = 503
                    logger.error(
                        f"Webhook {event.event_id} EXHAUSTED after {event.attempt_count} attempts"
                    )
                else:
                    event.delivery_status = WebhookDeliveryStatus.RETRYING
                    event.next_retry_at = _calculate_next_retry(event.attempt_count)
                    event.response_code = random.choice([500, 502, 503])
                    logger.warning(
                        f"Retry #{event.attempt_count} FAILED for webhook {event.event_id}. "
                        f"Next retry at {event.next_retry_at.isoformat()}"
                    )

        db.commit()
        if pending_retries:
            logger.info(f"Retry engine processed {len(pending_retries)} webhook(s)")
    except Exception as e:
        logger.error(f"Retry engine error: {e}")
        db.rollback()
    finally:
        db.close()


def get_retry_stats(db: Session) -> dict:
    """Return current retry queue statistics."""
    total = db.query(WebhookEvent).count()
    delivered = db.query(WebhookEvent).filter(
        WebhookEvent.delivery_status == WebhookDeliveryStatus.DELIVERED
    ).count()
    retrying = db.query(WebhookEvent).filter(
        WebhookEvent.delivery_status == WebhookDeliveryStatus.RETRYING
    ).count()
    failed = db.query(WebhookEvent).filter(
        WebhookEvent.delivery_status == WebhookDeliveryStatus.FAILED
    ).count()
    exhausted = db.query(WebhookEvent).filter(
        WebhookEvent.delivery_status == WebhookDeliveryStatus.EXHAUSTED
    ).count()
    duplicates = db.query(WebhookEvent).filter(
        WebhookEvent.is_duplicate == True  # noqa: E712
    ).count()

    return {
        "total": total,
        "delivered": delivered,
        "retrying": retrying,
        "failed": failed,
        "exhausted": exhausted,
        "duplicates_detected": duplicates,
        "delivery_rate": round(delivered / total * 100, 2) if total > 0 else 0.0,
    }
