"""SQLAlchemy models for FutureDecoded — separate DB from am bots."""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class StoryRecord(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000))
    source = Column(String(100))
    category = Column(String(50))
    trend_score = Column(Float, default=0.0)
    viral_probability = Column(Float, default=0.0)
    competition = Column(Float, default=0.0)
    search_growth = Column(String(20), default="0%")
    recommended_format = Column(String(20), default="both")
    priority = Column(String(20), default="medium")
    fact_checked = Column(Boolean, default=False)
    content_hash = Column(String(64), unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class StorySourceRecord(Base):
    __tablename__ = "story_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, nullable=False)
    source_name = Column(String(100))
    source_url = Column(String(1000))
    verified = Column(Boolean, default=False)


class UploadHistoryRecord(Base):
    __tablename__ = "upload_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer)
    video_id = Column(String(50))
    format_type = Column(String(20))
    title = Column(String(200))
    content_hash = Column(String(64), unique=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)


class AnalyticsRecord(Base):
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(50))
    views = Column(Integer, default=0)
    watch_time_minutes = Column(Float, default=0.0)
    ctr = Column(Float, default=0.0)
    retention = Column(Float, default=0.0)
    subscribers_gained = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)


_engine = None
_SessionLocal = None


def init_database(database_url: str) -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        from pathlib import Path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal


def get_session() -> Session:
    if _SessionLocal is None:
        from futuredecoded.config.settings import get_settings
        init_database(get_settings().database_url)
    return _SessionLocal()
