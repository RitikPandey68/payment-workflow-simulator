"""
Payment Workflow Simulator — FastAPI Application Entry Point
============================================================
Simulates a complete payment gateway integration including:
 - Order lifecycle management
 - Payment processing with failure simulation
 - HMAC-signed webhook delivery & retry engine
 - Idempotency enforcement
 - Refund handling
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
import os

from .config import get_settings
from .database import create_tables
from .routers import orders_router, payments_router, webhooks_router, refunds_router, admin_router
from .services.retry_engine import retry_failed_webhooks

settings = get_settings()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Background Scheduler ───────────────────────────────────────────────────────
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    logger.info("🚀 Payment Workflow Simulator starting up...")
    create_tables()
    logger.info("✅ Database tables created/verified")

    # Schedule retry engine every 10 seconds
    scheduler.add_job(
        retry_failed_webhooks,
        "interval",
        seconds=10,
        id="webhook_retry_engine",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("✅ Webhook retry engine started (every 10s)")

    yield

    scheduler.shutdown(wait=False)
    logger.info("👋 Payment Workflow Simulator shutting down")


# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Payment Workflow Simulator",
    description="""
## 💳 Payment Workflow Simulator — Transaction & Webhook Engine

A production-grade simulation of a payment gateway (Razorpay-style) demonstrating:

### Features
- **Order Lifecycle**: Create → Process → Complete/Fail → Refund
- **Payment Processing**: Multi-method (Card, UPI, Netbanking, Wallet) with realistic failure injection
- **Webhook Engine**: HMAC-SHA256 signed events with exponential backoff retry
- **Idempotency**: Prevent duplicate charges with idempotency key enforcement
- **Failure Scenarios**: Insufficient funds, card declined, network timeout, HMAC mismatch, duplicate events

### Real-World Pitfalls Simulated
| Pitfall | Simulation |
|---------|-----------|
| Idempotency failures | Duplicate requests with same `Idempotency-Key` |
| Duplicate webhook events | Same event fired twice |
| HMAC signature mismatch | `?force_hmac_mismatch=true` on payment |
| Retry exhaustion | Max 5 retries with exponential backoff |
| Race conditions | In-flight idempotency lock (409 Conflict) |

### Webhook Retry Schedule
```
Attempt 1: immediate
Attempt 2: ~1s
Attempt 3: ~2s
Attempt 4: ~4s
Attempt 5: ~8s → EXHAUSTED
```
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(orders_router, prefix=API_PREFIX)
app.include_router(payments_router, prefix=API_PREFIX)
app.include_router(webhooks_router, prefix=API_PREFIX)
app.include_router(refunds_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)

# ── Static Frontend ────────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
