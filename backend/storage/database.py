import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import declarative_base

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_DB_PATH = os.path.join(_DB_DIR, "engine.db")

Base = declarative_base()

_engine = None
SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        os.makedirs(_DB_DIR, exist_ok=True)
        db_url = f"sqlite:///{os.path.abspath(_DB_PATH)}"
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def _get_session_factory():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return SessionLocal


def init_db():
    from backend.storage import models  # noqa: F401 — import to register all models
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialised at {_DB_PATH}")

    # Migrate: add domain column to researched_topics if missing
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        cols = [c["name"] for c in inspector.get_columns("researched_topics")]
        if "domain" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE researched_topics ADD COLUMN domain VARCHAR(256)"))
            logger.info("Migration: added 'domain' column to researched_topics")
    except Exception:
        pass  # table may not exist yet on first run

    # Seed budget rows from config
    try:
        from backend.utils.config_loader import get as cfg_get
        from backend.storage.models import Budget
        session_factory = _get_session_factory()
        with session_factory() as session:
            _seed_budget(session, cfg_get)
    except Exception as e:
        logger.warning(f"Budget seeding skipped: {e}")


def _seed_budget(session, cfg_get):
    from backend.storage.models import Budget
    defaults = {
        "likes": cfg_get("daily_budget.likes", 30),
        "comments": cfg_get("daily_budget.comments", 12),
        "connections": cfg_get("daily_budget.connections", 15),
        "profile_visits": cfg_get("daily_budget.profile_visits", 50),
        "inmails": cfg_get("daily_budget.inmails", 5),
        "posts_published": cfg_get("daily_budget.posts_published", 5),
        "follows": cfg_get("daily_budget.follows", 20),
        "endorsements": cfg_get("daily_budget.endorsements", 10),
        "feed_scans": cfg_get("daily_budget.feed_scans", 0),
    }
    for action_type, limit in defaults.items():
        existing = session.query(Budget).filter_by(action_type=action_type).first()
        if not existing:
            session.add(Budget(action_type=action_type, limit_per_day=limit, count_today=0))
    session.commit()


@contextmanager
def get_db() -> Session:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    from backend.utils.config_loader import load_config
    load_config()
    init_db()
    print("Database initialised successfully")
