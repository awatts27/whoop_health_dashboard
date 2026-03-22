"""
SQLAlchemy engine and session factory.
DATABASE_URL is read from environment variables.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        database_url = os.environ["DATABASE_URL"]
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    """FastAPI dependency: yields a database session."""
    SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
