"""
Unit and Mock Tests for PostgreSQL / AWS RDS Database Layer.
Tests connection management, DSN generation, DDL execution, error surfacing on connection failure,
and PostgresTransactionRepository / PostgresGoalRepository operations using mocks.
"""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest
import psycopg

from app.core.config import Settings
from app.core.database import (
    get_db_connection,
    init_db,
    check_db_health,
    DatabaseConnectionError,
    DatabaseNotConfiguredError,
)
from app.repositories.postgres_transaction_repo import PostgresTransactionRepository
from app.repositories.postgres_goal_repo import PostgresGoalRepository
from app.services.transaction_service import TransactionRepositoryProxy
from app.schemas.transactions import (
    TransactionCreate,
    TransactionType,
    RecurringFrequency,
)
from app.schemas.goals import GoalCreateRequest


# ------------------ DSN Configuration Tests ------------------

def test_dsn_generation_from_individual_fields():
    """Verify DSN generation from host, user, password, port, dbname with default require SSL."""
    s = Settings(
        DB_HOST="mydb.rds.amazonaws.com",
        DB_PORT=5432,
        DB_NAME="moneylens_prod",
        DB_USER="dbadmin",
        DB_PASSWORD="secretpassword",
        DB_SSLMODE="require",
    )
    assert s.is_db_configured() is True
    dsn = s.get_database_dsn()
    assert dsn == "postgresql://dbadmin:secretpassword@mydb.rds.amazonaws.com:5432/moneylens_prod?sslmode=require"


def test_dsn_generation_from_database_url_appends_ssl():
    """Verify DATABASE_URL appends sslmode=require if not present."""
    s = Settings(
        DATABASE_URL="postgresql://user:pass@localhost:5432/testdb",
        DB_SSLMODE="require"
    )
    assert s.is_db_configured() is True
    dsn = s.get_database_dsn()
    assert "sslmode=require" in dsn


def test_dsn_generation_unconfigured():
    """Verify unconfigured settings return None and is_db_configured is False."""
    s = Settings(
        DATABASE_URL=None,
        DB_HOST=None,
        DB_USER=None
    )
    assert s.is_db_configured() is False
    assert s.get_database_dsn() is None


# ------------------ Connection & Lifespan Tests ------------------

def test_get_db_connection_unconfigured_raises_error():
    """Verify get_db_connection raises DatabaseNotConfiguredError if no DB settings exist."""
    with patch.object(Settings, "is_db_configured", return_value=False):
        with pytest.raises(DatabaseNotConfiguredError):
            with get_db_connection():
                pass


def test_get_db_connection_surfaces_connection_failure():
    """Verify database connection errors are clearly surfaced when RDS is unreachable (no silent fallback)."""
    with patch.object(Settings, "is_db_configured", return_value=True), \
         patch.object(Settings, "get_database_dsn", return_value="postgresql://fake@localhost:5432/db?sslmode=require"), \
         patch("psycopg.connect", side_effect=psycopg.OperationalError("could not connect to server: Connection refused")):
        
        with pytest.raises(DatabaseConnectionError) as exc_info:
            with get_db_connection():
                pass
        
        assert "Connection refused" in str(exc_info.value) or "PostgreSQL/RDS database connection error" in str(exc_info.value)


def test_get_db_connection_success_commits_and_closes():
    """Verify successful get_db_connection commits transaction and closes connection."""
    mock_conn = MagicMock()
    with patch.object(Settings, "is_db_configured", return_value=True), \
         patch.object(Settings, "get_database_dsn", return_value="postgresql://dummy"), \
         patch("psycopg.connect", return_value=mock_conn):
        
        with get_db_connection() as conn:
            assert conn == mock_conn

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


def test_init_db_executes_ddl_when_configured():
    """Verify init_db executes DDL statements on PostgreSQL."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch.object(Settings, "is_db_configured", return_value=True), \
         patch("app.core.database.get_db_connection", return_value=MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock())):
        
        init_db()
        assert mock_cur.execute.called
        all_sql = " ".join(call[0][0] for call in mock_cur.execute.call_args_list)
        assert "CREATE TABLE IF NOT EXISTS transactions" in all_sql
        assert "CREATE TABLE IF NOT EXISTS goals" in all_sql


def test_check_db_health():
    """Verify health check returns diagnostic info for both in-memory and PostgreSQL modes."""
    # 1. Unconfigured
    with patch.object(Settings, "is_db_configured", return_value=False):
        health = check_db_health()
        assert health["mode"] == "in-memory"
        assert health["connected"] is False

    # 2. Configured & connected
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = {"ping": 1}
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch.object(Settings, "is_db_configured", return_value=True), \
         patch("app.core.database.get_db_connection", return_value=MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock())):
        health = check_db_health()
        assert health["mode"] == "postgresql-rds"
        assert health["connected"] is True


# ------------------ PostgresTransactionRepository Tests ------------------

def test_postgres_transaction_repo_create():
    """Verify PostgresTransactionRepository.create inserts row and returns TransactionResponse."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    fake_row = {
        "id": "txn_mock123",
        "title": "Client Invoice",
        "type": "income",
        "amount": 50000.0,
        "category": "Salary",
        "transaction_date": date(2026, 9, 15),
        "is_recurring": False,
        "recurring_frequency": "none",
        "description": "Consulting"
    }
    mock_cur.fetchone.return_value = fake_row
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    repo = PostgresTransactionRepository()
    with patch("app.repositories.postgres_transaction_repo.get_db_connection", return_value=MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock())):
        result = repo.create("user_test", TransactionCreate(
            title="Client Invoice",
            type=TransactionType.INCOME,
            amount=50000.0,
            category="Salary",
            transaction_date=date(2026, 9, 15),
            is_recurring=False,
            recurring_frequency=RecurringFrequency.NONE,
            description="Consulting"
        ))

        assert result.id == "txn_mock123"
        assert result.amount == 50000.0
        assert mock_cur.execute.called


def test_postgres_transaction_repo_get_all_and_summary():
    """Verify PostgresTransactionRepository.get_all and get_summary calculate metrics accurately."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    sample_rows = [
        {
            "id": "txn_1",
            "title": "Salary",
            "type": "income",
            "amount": 80000.0,
            "category": "Salary",
            "transaction_date": date(2026, 9, 1),
            "is_recurring": True,
            "recurring_frequency": "monthly",
            "description": "Income"
        },
        {
            "id": "txn_2",
            "title": "Rent",
            "type": "expense",
            "amount": 20000.0,
            "category": "Rent",
            "transaction_date": date(2026, 9, 2),
            "is_recurring": True,
            "recurring_frequency": "monthly",
            "description": "Expense"
        }
    ]
    mock_cur.fetchall.return_value = sample_rows
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    repo = PostgresTransactionRepository()
    with patch("app.repositories.postgres_transaction_repo.get_db_connection", return_value=MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock())):
        all_txns = repo.get_all("user_test")
        assert len(all_txns) == 2

        summary = repo.get_summary("user_test")
        assert summary.total_income == 80000.0
        assert summary.total_expenses == 20000.0
        assert summary.net_savings == 60000.0
        assert summary.savings_rate_pct == 75.0
        assert summary.recurring_summary.total_recurring_income == 80000.0
        assert summary.recurring_summary.total_recurring_expenses == 20000.0
        assert summary.recurring_summary.recurring_items_count == 2


# ------------------ PostgresGoalRepository Tests ------------------

def test_postgres_goal_repo_create_and_delete():
    """Verify PostgresGoalRepository CRUD operations."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    fake_goal = {
        "id": "goal_mock123",
        "user_id": "user_test",
        "title": "New Car",
        "target_amount": 600000.0,
        "current_savings_allocated": 50000.0,
        "target_months": 24,
        "target_date": date(2028, 9, 1),
        "category": "Vehicle",
        "priority": "medium"
    }
    mock_cur.fetchone.return_value = fake_goal
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    repo = PostgresGoalRepository()
    with patch.object(Settings, "is_db_configured", return_value=True), \
         patch("app.repositories.postgres_goal_repo.get_db_connection", return_value=MagicMock(__enter__=MagicMock(return_value=mock_conn), __exit__=MagicMock())):
        created = repo.create("user_test", GoalCreateRequest(
            title="New Car",
            target_amount=600000.0,
            current_savings_allocated=50000.0,
            target_months=24,
            target_date=date(2028, 9, 1),
            category="Vehicle",
            priority="medium"
        ))
        assert created.id == "goal_mock123"
        assert created.target_amount == 600000.0

        # Test delete
        deleted = repo.delete("user_test", "goal_mock123")
        assert deleted is True


# ------------------ Proxy Selection & Explicit Failure Tests ------------------

def test_transaction_repository_proxy_selection():
    """Verify TransactionRepositoryProxy delegates based on configuration state."""
    proxy = TransactionRepositoryProxy()

    # When unconfigured -> uses in-memory
    with patch.object(Settings, "is_db_configured", return_value=False):
        assert proxy.active_repo == proxy._in_memory
        proxy.create("user_test", TransactionCreate(
            title="Test Txn",
            type=TransactionType.INCOME,
            amount=5000.0,
            category="Salary",
            is_recurring=False
        ))
        txns = proxy.get_all("user_test")
        assert len(txns) == 1

    # When configured -> uses Postgres repo
    with patch.object(Settings, "is_db_configured", return_value=True):
        assert proxy.active_repo == proxy._postgres
