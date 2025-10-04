"""
Database configuration and base models
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment
# Use postgresql+psycopg driver (psycopg3) instead of default psycopg2
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sales_agent:dev_password_change_in_production@localhost:5433/sales_agent_db")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",  # Environment-controlled SQL logging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10"))
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

def get_db():
    """
    Dependency function for FastAPI to get database sessions
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
