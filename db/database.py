"""
VocabRecall – Database initialisation & session management
============================================================
Creates the SQLite database file next to the application and provides
a session factory for the rest of the app.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from db.models import Base

# ---------------------------------------------------------------------------
# Resolve a user-data directory that survives packaging with PyInstaller.
# ---------------------------------------------------------------------------

def _app_data_dir() -> Path:
    """Return a stable directory for the SQLite file."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent
    data_dir = base / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


DB_PATH = _app_data_dir() / "vocabrecall.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key enforcement for every SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Return a new SQLAlchemy session."""
    return SessionLocal()
