"""Database connection, engine management, and schema initialization."""

import logging
from contextlib import contextmanager
from typing import Optional, Generator
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import DATABASE_URL, DEFAULT_SQLITE_URL, BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_ENGINE: Optional[Engine] = None
_ACTIVE_DB_TYPE: str = "unknown"


def get_engine(force_sqlite: bool = False) -> Engine:
    """Returns a resilient SQLAlchemy engine.
    
    Attempts PostgreSQL connection first (if configured and reachable);
    falls back smoothly to SQLite for zero-friction local execution.
    """
    global _ENGINE, _ACTIVE_DB_TYPE
    if _ENGINE is not None and not force_sqlite:
        return _ENGINE

    if not force_sqlite and "postgresql" in DATABASE_URL:
        try:
            logger.info("Attempting PostgreSQL connection...")
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Successfully connected to PostgreSQL.")
            _ENGINE = engine
            _ACTIVE_DB_TYPE = "postgresql"
            return _ENGINE
        except Exception as e:
            logger.warning("PostgreSQL connection failed (%s). Falling back to SQLite.", e)

    logger.info("Initializing SQLite database engine at %s", DEFAULT_SQLITE_URL)
    _ENGINE = create_engine(DEFAULT_SQLITE_URL, connect_args={"check_same_thread": False})
    _ACTIVE_DB_TYPE = "sqlite"
    return _ENGINE


def get_active_db_type() -> str:
    """Returns the type of active database ('postgresql' or 'sqlite')."""
    global _ACTIVE_DB_TYPE
    if _ENGINE is None:
        get_engine()
    return _ACTIVE_DB_TYPE


@contextmanager
def get_db_connection() -> Generator:
    """Context manager for obtaining a database connection with auto-commit."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def init_database(engine: Optional[Engine] = None) -> None:
    """Executes the DDL schema script to initialize all dimensional and fact tables."""
    if engine is None:
        engine = get_engine()
    
    schema_path = BASE_DIR / "src" / "database" / "schema.sql"
    logger.info("Initializing database schema from %s...", schema_path)
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Split and execute statements (handling SQLite vs Postgres differences)
    with engine.begin() as conn:
        for raw_stmt in schema_sql.split(";"):
            stmt = raw_stmt.strip()
            if stmt:
                conn.execute(text(stmt))
                
    logger.info("Database schema initialized successfully. Active engine: %s", get_active_db_type())


def execute_query(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Executes a SQL SELECT query and returns the results as a Pandas DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, params=params)
