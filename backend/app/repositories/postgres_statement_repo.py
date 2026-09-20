"""
PostgreSQL Statement Repository.
Stores statement metadata and parsed transactions in PostgreSQL.
All data is scoped per user_id.
Falls back to in-memory only when DB is not configured.
"""

import uuid
import json
from typing import Optional, List, Dict, Any
from app.core.database import get_db_connection, DatabaseConnectionError, DatabaseNotConfiguredError
from app.core.config import settings
from app.schemas.statements import StatementAnalysisSummary, StatementTransactionItem

# Module-level shared in-memory fallback stores (used when DB is not configured)
_SHARED_STATEMENTS: Dict[str, List[Dict[str, Any]]] = {}
_SHARED_TRANSACTIONS: Dict[str, List[Dict[str, Any]]] = {}


class PostgresStatementRepository:
    """Repository for statement uploads and transaction extraction — DB-backed."""

    def __init__(self):
        self._in_memory_statements = _SHARED_STATEMENTS
        self._in_memory_txs = _SHARED_TRANSACTIONS

    def save_statement_summary(
        self,
        user_id: str,
        summary: StatementAnalysisSummary,
        transactions: List[StatementTransactionItem],
        filename: str = "uploaded_statement"
    ) -> Optional[str]:
        """Persist statement summary and transactions to DB. Returns statement_id."""
        statement_id = f"stmt_{uuid.uuid4().hex[:12]}"
        summary_dict = summary.model_dump()
        tx_dicts = [t.model_dump() for t in transactions]

        if settings.is_db_configured():
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        # Insert statement summary
                        cur.execute("""
                        INSERT INTO statement_summaries (
                            id, user_id, filename, total_credits, total_debits, net_cashflow,
                            transaction_count, date_range_start, date_range_end,
                            essential_spending, discretionary_spending, recurring_spending,
                            observations, category_breakdown
                        ) VALUES (
                            %(id)s, %(user_id)s, %(filename)s, %(total_credits)s, %(total_debits)s,
                            %(net_cashflow)s, %(transaction_count)s, %(date_range_start)s,
                            %(date_range_end)s, %(essential_spending)s, %(discretionary_spending)s,
                            %(recurring_spending)s, %(observations)s::jsonb, %(category_breakdown)s::jsonb
                        )
                        ON CONFLICT DO NOTHING;
                        """, {
                            "id": statement_id,
                            "user_id": user_id,
                            "filename": filename,
                            "total_credits": float(summary_dict.get("total_credits", 0.0)),
                            "total_debits": float(summary_dict.get("total_debits", 0.0)),
                            "net_cashflow": float(summary_dict.get("net_cashflow", 0.0)),
                            "transaction_count": int(summary_dict.get("transaction_count", 0)),
                            "date_range_start": summary_dict.get("date_range_start"),
                            "date_range_end": summary_dict.get("date_range_end"),
                            "essential_spending": float(summary_dict.get("essential_spending", 0.0)),
                            "discretionary_spending": float(summary_dict.get("discretionary_spending", 0.0)),
                            "recurring_spending": float(summary_dict.get("recurring_spending", 0.0)),
                            "observations": json.dumps(summary_dict.get("observations", [])),
                            "category_breakdown": json.dumps(summary_dict.get("category_breakdown", {})),
                        })

                        # Insert individual transactions in batch
                        for tx in tx_dicts:
                            tx_id = tx.get("id") or f"tx_{uuid.uuid4().hex[:12]}"
                            cur.execute("""
                            INSERT INTO statement_transactions (
                                id, user_id, statement_id, date, description, amount,
                                type, category, is_recurring, is_essential, source, confidence
                            ) VALUES (
                                %(id)s, %(user_id)s, %(statement_id)s, %(date)s, %(description)s,
                                %(amount)s, %(type)s, %(category)s, %(is_recurring)s, %(is_essential)s,
                                %(source)s, %(confidence)s
                            )
                            ON CONFLICT (id) DO NOTHING;
                            """, {
                                "id": tx_id,
                                "user_id": user_id,
                                "statement_id": statement_id,
                                "date": str(tx.get("date", "")),
                                "description": str(tx.get("description", "")),
                                "amount": float(tx.get("amount", 0.0)),
                                "type": str(tx.get("type", "debit")),
                                "category": str(tx.get("category", "Other")),
                                "is_recurring": bool(tx.get("is_recurring", False)),
                                "is_essential": bool(tx.get("is_essential", False)),
                                "source": str(tx.get("source", "text")),
                                "confidence": float(tx.get("confidence", 0.95)),
                            })
            except (DatabaseConnectionError, DatabaseNotConfiguredError) as e:
                import logging
                logging.getLogger(__name__).warning("DB unavailable for statement save, using memory: %s", e)
                # Fall through to in-memory

        # Always write to in-memory cache for same-request consistency
        if user_id not in self._in_memory_statements:
            self._in_memory_statements[user_id] = []
        if user_id not in self._in_memory_txs:
            self._in_memory_txs[user_id] = []

        self._in_memory_statements[user_id].append(summary_dict)
        self._in_memory_txs[user_id].extend(tx_dicts)

        return statement_id

    def get_user_statements(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all statement summaries for user."""
        if settings.is_db_configured():
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                        SELECT id, filename, total_credits, total_debits, net_cashflow,
                               transaction_count, date_range_start, date_range_end,
                               essential_spending, discretionary_spending, recurring_spending,
                               observations, category_breakdown, created_at
                        FROM statement_summaries
                        WHERE user_id = %(user_id)s
                        ORDER BY created_at DESC;
                        """, {"user_id": user_id})
                        return [dict(r) for r in cur.fetchall()]
            except (DatabaseConnectionError, DatabaseNotConfiguredError):
                pass
        return self._in_memory_statements.get(user_id, [])

    def get_latest_statement(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get most recent statement summary for user."""
        stmts = self.get_user_statements(user_id)
        return stmts[0] if stmts else None

    def get_user_transactions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all transactions extracted from statements for user."""
        if settings.is_db_configured():
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                        SELECT id, statement_id, date, description, amount, type,
                               category, is_recurring, is_essential, source, confidence, created_at
                        FROM statement_transactions
                        WHERE user_id = %(user_id)s
                        ORDER BY created_at DESC;
                        """, {"user_id": user_id})
                        return [dict(r) for r in cur.fetchall()]
            except (DatabaseConnectionError, DatabaseNotConfiguredError):
                pass
        return self._in_memory_txs.get(user_id, [])
