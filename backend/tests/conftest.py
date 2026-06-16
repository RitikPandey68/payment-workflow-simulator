# conftest.py — shared pytest fixtures
import pytest


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_dbs():
    """Clean up test database files after the test session."""
    yield
    import os
    for db_file in [
        "test_payment.db",
        "test_payment_pay.db",
        "test_webhook.db",
        "test_idempotency.db",
    ]:
        if os.path.exists(db_file):
            os.remove(db_file)
