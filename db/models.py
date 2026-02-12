"""
VocabRecall – SQLAlchemy ORM Models
====================================
Defines the data schema: Folders (nested), Decks, Cards (with SM-2 fields),
and ReviewLogs.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ---------------------------------------------------------------------------
# Folder – hierarchical organisation  (self-referential)
# ---------------------------------------------------------------------------
class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    children = relationship(
        "Folder",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="select",
        passive_deletes=True,
        single_parent=True,
        foreign_keys=[parent_id],
    )
    parent = relationship(
        "Folder",
        back_populates="children",
        remote_side=[id],
        foreign_keys=[parent_id],
    )
    decks = relationship(
        "Deck", back_populates="folder", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_folder_name_parent"),
    )

    def __repr__(self) -> str:
        return f"<Folder id={self.id} name={self.name!r} parent_id={self.parent_id}>"


# ---------------------------------------------------------------------------
# Deck – a collection of flashcards
# ---------------------------------------------------------------------------
class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False)
    source_filename = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    folder = relationship("Folder", back_populates="decks")
    cards = relationship(
        "Card", back_populates="deck", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Deck id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Card – a single flashcard with SM-2 scheduling metadata
# ---------------------------------------------------------------------------
class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deck_id = Column(Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)

    # Content
    front = Column(Text, nullable=False)          # German word / phrase
    back = Column(Text, nullable=False, default="")  # Translation / definition
    article = Column(String(10), nullable=True)    # der / die / das
    word_type = Column(String(50), nullable=True)  # NOUN, VERB, ADJ …
    example_sentence = Column(Text, nullable=True)

    # SM-2 scheduling fields
    easiness = Column(Float, nullable=False, default=2.5)
    interval = Column(Integer, nullable=False, default=0)       # days
    repetitions = Column(Integer, nullable=False, default=0)
    next_review = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    deck = relationship("Deck", back_populates="cards")
    review_logs = relationship(
        "ReviewLog", back_populates="card", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id} front={self.front!r} next_review={self.next_review}>"


# ---------------------------------------------------------------------------
# ReviewLog – audit trail for every review action
# ---------------------------------------------------------------------------
class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False)
    reviewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    quality = Column(Integer, nullable=False)  # 0-5 (SM-2 scale)
    easiness_after = Column(Float, nullable=True)
    interval_after = Column(Integer, nullable=True)

    # Relationship
    card = relationship("Card", back_populates="review_logs")

    def __repr__(self) -> str:
        return f"<ReviewLog card_id={self.card_id} q={self.quality} at={self.reviewed_at}>"
