from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import event

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs = dict(
    pool_pre_ping=True,
    echo=settings.DEBUG,
)
if not _is_sqlite:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 40
    _engine_kwargs["pool_timeout"] = 30
else:
    # Use NullPool for SQLite so background threads and async routes never exhaust QueuePool
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency: yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables if they don't exist."""
    from .models import order, payment, webhook, refund, idempotency  # noqa: F401
    Base.metadata.create_all(bind=engine)
