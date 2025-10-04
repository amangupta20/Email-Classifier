"""
Database package initialization for the Email Classifier application.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

# Create the declarative base
Base = declarative_base()

# Export the base and all models
__all__ = ["Base", "engine", "SessionLocal", "get_db"]

# Database engine will be initialized in the main application
engine = None
SessionLocal = None


def init_database(database_url: str) -> None:
    """
    Initialize the database engine and session.
    
    Args:
        database_url: The database connection URL
    """
    global engine, SessionLocal
    
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL logging
        future=True,  # Use SQLAlchemy 2.0 style
    )
    
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
    )


def get_db() -> AsyncGenerator:
    """
    Dependency function to get a database session.
    
    Yields:
        Database session
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """
    Create all database tables.
    """
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """
    Drop all database tables.
    """
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    Base.metadata.drop_all(bind=engine)