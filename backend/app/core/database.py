"""
PostgreSQL / AWS RDS Database Connectivity Module.
Provides connection lifecycle management and DDL table initializations using psycopg (v3).
"""

import logging
from contextlib import contextmanager
from typing import Generator, Dict, Any, Optional

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when connecting or querying PostgreSQL / RDS fails."""
    pass


class DatabaseNotConfiguredError(Exception):
    """Raised when a database operation is requested but no DB configuration is provided."""
    pass


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """
    Context manager yielding an active psycopg connection with dictionary row factory.
    Commits on successful block completion, rolls back on exception, and closes connection.
    Raises DatabaseConnectionError if connection to RDS/PostgreSQL fails.
    """
    if not settings.is_db_configured():
        raise DatabaseNotConfiguredError("No PostgreSQL / RDS connection configuration found in environment.")

    dsn = settings.get_database_dsn()
    try:
        conn = psycopg.connect(dsn, row_factory=dict_row)
    except psycopg.Error as e:
        logger.error("Failed to connect to PostgreSQL/RDS database: %s", str(e))
        raise DatabaseConnectionError(f"PostgreSQL/RDS database connection error: {str(e)}") from e

    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Database transaction rolled back due to error: %s", str(e))
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Initializes PostgreSQL / RDS schema tables and indexes if they do not exist.
    Tables start empty with zero auto-seeded records.
    All financial tables include user_id for proper data isolation.
    """
    if not settings.is_db_configured():
        logger.info("Database configuration not provided; skipping PostgreSQL table initialization.")
        return

    ddl = """
    -- Users table (auth identity)
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(64) PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        username VARCHAR(64) UNIQUE,
        name VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        monthly_income NUMERIC(14, 2) DEFAULT 0.0,
        monthly_expenses NUMERIC(14, 2) DEFAULT 0.0,
        current_savings NUMERIC(14, 2) DEFAULT 0.0,
        health_score INTEGER DEFAULT 50,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

    -- OTP verification
    CREATE TABLE IF NOT EXISTS email_otps (
        id VARCHAR(64) PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        otp_code VARCHAR(16) NOT NULL,
        purpose VARCHAR(32) NOT NULL DEFAULT 'auth',
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        is_verified BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_email_otps_email ON email_otps(email);
    CREATE INDEX IF NOT EXISTS idx_email_otps_code ON email_otps(email, otp_code);

    -- Financial profile per user (detailed breakdown)
    CREATE TABLE IF NOT EXISTS user_profiles (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL DEFAULT 'User',
        monthly_income NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        essential_expenses NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        discretionary_expenses NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        current_savings NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        monthly_investments NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        active_emis NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        active_loans NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        other_recurring_expenses NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

    -- Financial goals (scoped per user)
    CREATE TABLE IF NOT EXISTS goals (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        target_amount NUMERIC(14, 2) NOT NULL,
        current_savings_allocated NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        target_months INTEGER,
        target_date DATE,
        category VARCHAR(128),
        priority VARCHAR(32),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_goals_user_id ON goals(user_id);

    -- Manual transactions (scoped per user)
    CREATE TABLE IF NOT EXISTS transactions (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        type VARCHAR(32) NOT NULL,
        amount NUMERIC(14, 2) NOT NULL,
        category VARCHAR(128) NOT NULL,
        transaction_date DATE NOT NULL,
        is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
        recurring_frequency VARCHAR(32) NOT NULL DEFAULT 'none',
        description TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
    CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
    CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
    CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);

    -- Bank statement summaries (one row per upload)
    CREATE TABLE IF NOT EXISTS statement_summaries (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        filename VARCHAR(512) NOT NULL,
        total_credits NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        total_debits NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        net_cashflow NUMERIC(14, 2) NOT NULL DEFAULT 0.0,
        transaction_count INTEGER NOT NULL DEFAULT 0,
        date_range_start VARCHAR(64),
        date_range_end VARCHAR(64),
        essential_spending NUMERIC(14, 2) DEFAULT 0.0,
        discretionary_spending NUMERIC(14, 2) DEFAULT 0.0,
        recurring_spending NUMERIC(14, 2) DEFAULT 0.0,
        observations JSONB DEFAULT '[]'::jsonb,
        category_breakdown JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_statement_summaries_user_id ON statement_summaries(user_id);
    CREATE INDEX IF NOT EXISTS idx_statement_summaries_created_at ON statement_summaries(user_id, created_at DESC);

    -- Statement transactions (parsed from uploaded bank statements)
    CREATE TABLE IF NOT EXISTS statement_transactions (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        statement_id VARCHAR(64),
        date VARCHAR(64) NOT NULL,
        description VARCHAR(512) NOT NULL,
        amount NUMERIC(14, 2) NOT NULL,
        type VARCHAR(16) NOT NULL,
        category VARCHAR(128) NOT NULL DEFAULT 'Other',
        is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
        is_essential BOOLEAN NOT NULL DEFAULT FALSE,
        source VARCHAR(16) NOT NULL DEFAULT 'text',
        confidence NUMERIC(4, 2) NOT NULL DEFAULT 0.95,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_statement_transactions_user_id ON statement_transactions(user_id);
    CREATE INDEX IF NOT EXISTS idx_statement_transactions_statement_id ON statement_transactions(statement_id);
    """

    logger.info("Initializing PostgreSQL schema tables on RDS/PostgreSQL...")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Safe migrations for existing installations (run BEFORE the main DDL to ensure columns exist for indexing)
            # Add user_id to goals if missing
            cur.execute("""
                ALTER TABLE goals ADD COLUMN IF NOT EXISTS user_id VARCHAR(64);
            """)
            # Clean out orphan goal rows (no user_id) — start fresh per user decision
            cur.execute("DELETE FROM goals WHERE user_id IS NULL;")

            # Add user_id to transactions if missing
            cur.execute("""
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS user_id VARCHAR(64);
            """)

            # Add username to users if missing (safe migration)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(64);")

            # Add source and confidence to statement_transactions
            cur.execute("""
                ALTER TABLE statement_transactions 
                ADD COLUMN IF NOT EXISTS source VARCHAR(16) DEFAULT 'text',
                ADD COLUMN IF NOT EXISTS confidence NUMERIC(4, 2) DEFAULT 0.95;
            """)

            # Execute main DDL for tables and indexes
            cur.execute(ddl)

    logger.info("PostgreSQL schema tables verified and ready.")


def check_db_health() -> Dict[str, Any]:
    """Checks database connectivity status and returns diagnostic health info."""
    if not settings.is_db_configured():
        return {
            "mode": "in-memory",
            "connected": False,
            "details": "No database credentials configured; using in-memory store"
        }

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 as ping;")
                res = cur.fetchone()
                if res and res.get("ping") == 1:
                    return {
                        "mode": "postgresql-rds",
                        "connected": True,
                        "details": "Successfully connected to PostgreSQL/RDS database"
                    }
        return {
            "mode": "postgresql-rds",
            "connected": False,
            "details": "Unexpected ping response from database"
        }
    except Exception as e:
        return {
            "mode": "postgresql-rds",
            "connected": False,
            "error": str(e)
        }
