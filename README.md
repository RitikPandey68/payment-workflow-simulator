# 💳 Payment Workflow Simulator — Transaction & Webhook Engine

A production-grade, full-stack simulation of a payment gateway (resembling Razorpay/Stripe architecture) designed to help developers understand, build, and test payment flows. It exposes orders, payments, webhooks, and refunds, while offering failure injection controls to simulate real-world integration pitfalls like **idempotency failures, duplicate events, signature mismatches, and retry exhaustion**.

---

## 🏗️ Architecture Overview

```
                        ┌───────────────────────────────────────────┐
                        │             Frontend Dashboard            │
                        │   Dashboard · simulator · Transactions    │
                        │    Webhooks · Reversals · Pitfalls       │
                        └─────────────────────┬─────────────────────┘
                                              │
                                              │ HTTP / REST API
                                              ▼
                        ┌───────────────────────────────────────────┐
                        │              FastAPI Backend              │
                        │   /orders  /payments  /webhooks  /refunds │
                        │  Idempotency Middleware · HMAC Signing    │
                        │    APScheduler Webhook Retry Daemon       │
                        └─────────────────────┬─────────────────────┘
                                              │
                                              │ SQLAlchemy ORM
                                              ▼
                        ┌───────────────────────────────────────────┐
                        │            PostgreSQL Database            │
                        │   orders · payments · webhook_events      │
                        │     refunds · idempotency_keys            │
                        └───────────────────────────────────────────┘
```

---

## 🌟 Key Features

1. **Order Lifecycle Engine**: Complete state machine mapping `pending → processing → completed/failed`.
2. **Idempotency Key Enforcement**: Protects against double-charging during network timeout retries using unique `Idempotency-Key` headers.
3. **Robust Webhook Dispatcher**: Generates signed JSON event payloads (Razorpay style) with `X-Razorpay-Signature` HMAC-SHA256 headers.
4. **Exponential Backoff Retry Engine**: Automatically queues failed webhook deliveries for retry (1s → 2s → 4s → 8s → 16s) using APScheduler background job runner.
5. **Refunds Engine**: Allows full or partial reversals of captured payments, triggering `refund.created` and `refund.processed` webhook notifications.
6. **Telemetry & Visuals**: Beautiful dark-mode dashboard styled using modern glassmorphic CSS, rendering live charts via Chart.js and feeding real-time websocket-like events via polling.
7. **Pitfalls Lab**: Simulated scenarios demonstrating integration vulnerabilities (Signature Verification, Double Charges, Duplicate Delivery) and interactive step-by-step resolution.

---

## 🛠️ Technology Stack

* **Backend**: FastAPI, SQLAlchemy ORM, Pydantic v2, APScheduler, PostgreSQL / SQLite
* **Frontend**: HTML5, Vanilla CSS3 (custom variables, glassmorphic theme), JavaScript (ES6+), Chart.js
* **Containerization**: Docker, Docker Compose
* **Testing**: Pytest, Pytest-Asyncio

---

## 🚀 Getting Started

### Method 1: Using Docker Compose (Recommended)

To spin up the PostgreSQL database, FastAPI backend, and frontend dashboard in a single command:

1. Clone or download the repository.
2. In the root directory, run:
   ```bash
   docker-compose up --build
   ```
3. Open your browser and navigate to:
   * **Dashboard UI**: `http://localhost:8000/`
   * **Interactive OpenAPI docs**: `http://localhost:8000/docs`

---

### Method 2: Manual Local Setup

#### Prerequisites
* Python 3.10+
* PostgreSQL running locally (or SQLite fallback)

#### Step 1: Clone & Configure Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment template and configure your database settings:
   ```bash
   copy .env.example .env
   ```

#### Step 2: Run Backend
```bash
python -m uvicorn app.main:app --reload --port 8000
```

#### Step 3: Run Frontend
Open `frontend/index.html` directly in your browser, or access it through the FastAPI server at `http://localhost:8000/`.

---

## 🧪 Running Tests

The test suite runs against an isolated, lightning-fast in-memory SQLite database utilizing SQLAlchemy's `StaticPool` to verify idempotency replays, payment declines, signature matching, and database persistence.

```bash
cd backend
.venv\Scripts\python.exe -m pytest -v
```

---

## 🔐 HMAC Signature Verification (For Merchants)

To prevent attackers from forging fake success payloads, merchants must verify the `X-Razorpay-Signature` (or custom gateway signature) header using the shared secret.

### Python Verification Example
```python
import hmac
import hashlib

def verify_webhook_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    expected_signature = hmac.new(
        key=secret.encode('utf-8'),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)
```

### Node.js Verification Example
```javascript
const crypto = require('crypto');

function verifySignature(payloadString, signatureHeader, secret) {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payloadString)
    .digest('hex');
    
  return crypto.timingSafeEqual(
    Buffer.from(expectedSignature),
    Buffer.from(signatureHeader)
  );
}
```

---

## 📑 API Reference

### 1. Orders
* `POST /api/v1/orders` - Create a pending order. Accept `Idempotency-Key` header.
* `GET /api/v1/orders` - List/filter orders.
* `GET /api/v1/orders/{order_ref}` - Retrieve specific order details.

### 2. Payments
* `POST /api/v1/payments/process` - Charge an order. Supports failure simulation (`simulate_failure` body param) and signature tampering (`?force_hmac_mismatch=true`).
* `GET /api/v1/payments` - List payment entries.

### 3. Webhooks
* `GET /api/v1/webhooks` - Fetch webhook delivery log.
* `GET /api/v1/webhooks/stats` - Fetch delivery and retry telemetry.
* `POST /api/v1/webhooks/verify` - Help merchants test signature matching validation.

### 4. Reversals / Refunds
* `POST /api/v1/refunds` - Process partial/full refund. Updates order status atomically.
* `GET /api/v1/refunds` - List all refunds.

### 5. Administration
* `DELETE /api/v1/admin/reset` - Clear database table contents (great for clean scenarios).
* `POST /api/v1/admin/retry-webhooks` - Manually trigger the background retry engine runner.
