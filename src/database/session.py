"""
Database session management.
Supports PostgreSQL (production / Docker) and SQLite (lightweight standalone local dev).
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base

# Database URL from environment (default to sqlite in project root)
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    db_path = Path(__file__).resolve().parent.parent.parent / "forecasting.db"
    DATABASE_URL = f"sqlite:///{db_path}"

# SQLite specific connect args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables in the database if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI route handlers."""
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
