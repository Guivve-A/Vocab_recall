"""
Tests for SQLAlchemy models – folder nesting, cascade deletes, card defaults.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from db.models import Base, Folder, Deck, Card, ReviewLog


@pytest.fixture
def session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class TestFolderNesting:
    def test_create_root_folder(self, session):
        f = Folder(name="Curso A1")
        session.add(f)
        session.commit()
        assert f.id is not None
        assert f.parent_id is None

    def test_nested_folders(self, session):
        parent = Folder(name="Curso A1")
        session.add(parent)
        session.flush()

        child = Folder(name="Capítulo 1", parent_id=parent.id)
        session.add(child)
        session.commit()

        assert child.parent_id == parent.id

    def test_cascade_delete_folder(self, session):
        parent = Folder(name="Root")
        session.add(parent)
        session.flush()

        deck = Deck(name="Vocab", folder_id=parent.id)
        session.add(deck)
        session.flush()

        card = Card(deck_id=deck.id, front="Haus", back="house")
        session.add(card)
        session.commit()

        session.delete(parent)
        session.commit()

        assert session.query(Deck).count() == 0
        assert session.query(Card).count() == 0


class TestCardDefaults:
    def test_sm2_defaults(self, session):
        f = Folder(name="F")
        session.add(f)
        session.flush()
        d = Deck(name="D", folder_id=f.id)
        session.add(d)
        session.flush()
        c = Card(deck_id=d.id, front="Hund", back="dog")
        session.add(c)
        session.commit()

        assert c.easiness == 2.5
        assert c.interval == 0
        assert c.repetitions == 0
        assert c.next_review is not None

    def test_review_log_creation(self, session):
        f = Folder(name="F")
        session.add(f)
        session.flush()
        d = Deck(name="D", folder_id=f.id)
        session.add(d)
        session.flush()
        c = Card(deck_id=d.id, front="Katze", back="cat")
        session.add(c)
        session.flush()

        log = ReviewLog(card_id=c.id, quality=4, easiness_after=2.6, interval_after=1)
        session.add(log)
        session.commit()

        assert log.id is not None
        assert log.card_id == c.id
