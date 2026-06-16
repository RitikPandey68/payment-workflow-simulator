"""
Payment Processor Service
Simulates a real payment gateway with configurable failure scenarios,
multiple payment methods, and realistic processing behaviour.
"""
import random
import time
import uuid
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.order import Order, OrderStatus
from ..models.payment import Payment, PaymentStatus, PaymentMethod, FailureReason
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Simulated card networks
CARD_NETWORKS = {
    "4": "Visa",
    "5": "Mastercard",
    "3": "Amex",
    "6": "RuPay",
}

# Weighted failure scenarios for random failures
FAILURE_SCENARIOS = [
    (FailureReason.INSUFFICIENT_FUNDS, 0.35),
    (FailureReason.CARD_DECLINED, 0.25),
    (FailureReason.NETWORK_TIMEOUT, 0.20),
    (FailureReason.INVALID_CVV, 0.10),
    (FailureReason.EXPIRED_CARD, 0.07),
    (FailureReason.FRAUD_DETECTED, 0.03),
]


def _pick_random_failure() -> FailureReason:
    """Pick a weighted random failure reason."""
    scenarios, weights = zip(*FAILURE_SCENARIOS)
    return random.choices(scenarios, weights=weights, k=1)[0]


def _get_card_network(card_number: str | None) -> str:
    if not card_number:
        return "Unknown"
    first_digit = card_number[0] if card_number else "4"
    return CARD_NETWORKS.get(first_digit, "Unknown")


def _simulate_processing_time() -> int:
    """Simulate gateway processing time in milliseconds (150ms–2500ms)."""
    return random.randint(150, 2500)


def _generate_gateway_txn_id() -> str:
    return f"gtxn_{uuid.uuid4().hex[:16].upper()}"


def _generate_payment_ref() -> str:
    return f"pay_{uuid.uuid4().hex[:12]}"


def process_payment(
    db: Session,
    order: Order,
    method: PaymentMethod,
    card_number: str | None = None,
    card_expiry: str | None = None,
    card_cvv: str | None = None,
    upi_id: str | None = None,
    simulate_failure: FailureReason | None = None,
) -> Payment:
    """
    Core payment processing function.
    Simulates a real payment gateway:
      - Random failure injection
      - Processing time simulation
      - Card network detection
      - Gateway transaction ID generation
    """
    processing_start = time.time()

    # Determine success or failure
    should_fail = simulate_failure is not None or random.random() < settings.PAYMENT_FAILURE_RATE
    failure_reason = simulate_failure if simulate_failure else (_pick_random_failure() if should_fail else FailureReason.NONE)

    # Simulate processing delay
    processing_time_ms = _simulate_processing_time()
    # time.sleep(processing_time_ms / 1000)  # Uncomment to add real delay

    card_last_four = card_number[-4:] if card_number and len(card_number) >= 4 else None
    card_network = _get_card_network(card_number) if method == PaymentMethod.CARD else None

    payment_status = PaymentStatus.FAILED if should_fail else PaymentStatus.CAPTURED
    gateway_txn_id = _generate_gateway_txn_id() if not should_fail else None

    # Build raw gateway response
    raw_response = {
        "gateway": "SimulatorPay",
        "transaction_id": gateway_txn_id,
        "status": "success" if not should_fail else "failed",
        "failure_code": failure_reason.value if should_fail else None,
        "processing_time_ms": processing_time_ms,
        "timestamp": datetime.utcnow().isoformat(),
        "risk_score": round(random.uniform(0.1, 0.9), 3),
    }

    payment = Payment(
        payment_ref=_generate_payment_ref(),
        order_id=order.id,
        amount=order.amount,
        currency=order.currency,
        status=payment_status,
        method=method,
        failure_reason=failure_reason if should_fail else FailureReason.NONE,
        gateway_transaction_id=gateway_txn_id,
        card_last_four=card_last_four,
        card_network=card_network,
        attempts=1,
        processing_time_ms=processing_time_ms,
        raw_response=json.dumps(raw_response),
    )
    db.add(payment)

    # Update order status
    if not should_fail:
        order.status = OrderStatus.COMPLETED
        logger.info(f"Payment {payment.payment_ref} CAPTURED for order {order.order_ref}")
    else:
        order.status = OrderStatus.FAILED
        logger.warning(
            f"Payment {payment.payment_ref} FAILED for order {order.order_ref}: {failure_reason.value}"
        )

    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(payment)
    return payment
