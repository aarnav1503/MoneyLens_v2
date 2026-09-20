"""
PostgreSQL Transaction Repository.
Provides CRUD operations and summary aggregations using PostgreSQL / AWS RDS and psycopg (v3).
Maintains exact interface parity with InMemoryTransactionRepository without auto-seeding data.
"""

import uuid
from typing import List, Optional, Dict, Union
from collections import defaultdict
from app.core.database import get_db_connection
from app.schemas.transactions import (
    TransactionCreate,
    TransactionResponse,
    TransactionType,
    TransactionSummaryResponse,
    CategorySpending,
    RecurringSummary,
)


class PostgresTransactionRepository:
    """PostgreSQL / RDS implementation of the Transaction Repository."""

    def create(self, user_id: Union[str, TransactionCreate] = "default", data: Optional[TransactionCreate] = None) -> TransactionResponse:
        if isinstance(user_id, TransactionCreate):
            data = user_id
            user_id = "default"

        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        query = """
        INSERT INTO transactions (
            id, user_id, title, type, amount, category, transaction_date,
            is_recurring, recurring_frequency, description
        ) VALUES (
            %(id)s, %(user_id)s, %(title)s, %(type)s, %(amount)s, %(category)s,
            %(transaction_date)s, %(is_recurring)s, %(recurring_frequency)s, %(description)s
        )
        RETURNING id, title, type, amount, category, transaction_date, is_recurring, recurring_frequency, description;
        """
        params = {
            "id": txn_id,
            "user_id": user_id,
            "title": data.title,
            "type": data.type.value if hasattr(data.type, "value") else str(data.type),
            "amount": float(data.amount),
            "category": data.category.value if hasattr(data.category, "value") else str(data.category),
            "transaction_date": data.transaction_date,
            "is_recurring": data.is_recurring,
            "recurring_frequency": data.recurring_frequency.value if hasattr(data.recurring_frequency, "value") else str(data.recurring_frequency),
            "description": data.description,
        }
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return TransactionResponse(**row)

    def get_all(
        self,
        user_id: str = "default",
        transaction_type: Optional[TransactionType] = None,
        category: Optional[str] = None,
        is_recurring: Optional[bool] = None
    ) -> List[TransactionResponse]:
        query = """
        SELECT id, title, type, amount, category, transaction_date, is_recurring, recurring_frequency, description
        FROM transactions
        WHERE user_id = %(user_id)s
        """
        conditions = []
        params: Dict[str, object] = {"user_id": user_id}

        if transaction_type:
            conditions.append("type = %(type)s")
            params["type"] = transaction_type.value if hasattr(transaction_type, "value") else str(transaction_type)
        if category:
            conditions.append("LOWER(category) = LOWER(%(category)s)")
            params["category"] = category
        if is_recurring is not None:
            conditions.append("is_recurring = %(is_recurring)s")
            params["is_recurring"] = is_recurring

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += " ORDER BY transaction_date DESC, created_at DESC;"

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [TransactionResponse(**r) for r in rows]

    def get_by_id(self, user_id_or_txn_id: str, txn_id: Optional[str] = None) -> Optional[TransactionResponse]:
        if txn_id is None:
            txn_id = user_id_or_txn_id
            user_id = "default"
        else:
            user_id = user_id_or_txn_id

        query = """
        SELECT id, title, type, amount, category, transaction_date, is_recurring, recurring_frequency, description
        FROM transactions
        WHERE id = %(id)s AND user_id = %(user_id)s;
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"id": txn_id, "user_id": user_id})
                row = cur.fetchone()
                if row:
                    return TransactionResponse(**row)
                return None

    def delete(self, user_id_or_txn_id: str, txn_id: Optional[str] = None) -> bool:
        if txn_id is None:
            txn_id = user_id_or_txn_id
            user_id = "default"
        else:
            user_id = user_id_or_txn_id

        query = "DELETE FROM transactions WHERE id = %(id)s AND user_id = %(user_id)s RETURNING id;"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"id": txn_id, "user_id": user_id})
                deleted = cur.fetchone()
                return deleted is not None

    def get_summary(self, user_id: str = "default") -> TransactionSummaryResponse:
        query = """
        SELECT id, title, type, amount, category, transaction_date, is_recurring, recurring_frequency, description
        FROM transactions
        WHERE user_id = %(user_id)s;
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"user_id": user_id})
                records = cur.fetchall()

        total_income = 0.0
        total_expenses = 0.0
        recurring_income = 0.0
        recurring_expenses = 0.0
        recurring_count = 0

        category_totals: Dict[str, float] = defaultdict(float)
        category_counts: Dict[str, int] = defaultdict(int)

        for record in records:
            amount = float(record["amount"])
            rec_type = record["type"]
            is_rec = bool(record["is_recurring"])
            cat = str(record["category"])

            if rec_type == TransactionType.INCOME.value or rec_type == "income":
                total_income += amount
                if is_rec:
                    recurring_income += amount
                    recurring_count += 1
            elif rec_type == TransactionType.EXPENSE.value or rec_type == "expense":
                total_expenses += amount
                category_totals[cat] += amount
                category_counts[cat] += 1
                if is_rec:
                    recurring_expenses += amount
                    recurring_count += 1

        net_savings = total_income - total_expenses
        savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

        category_breakdown: List[CategorySpending] = []
        for cat, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            pct = (total / total_expenses * 100) if total_expenses > 0 else 0.0
            category_breakdown.append(CategorySpending(
                category=cat,
                total_amount=round(total, 2),
                percentage_of_total_expense=round(pct, 2),
                transaction_count=category_counts[cat]
            ))

        return TransactionSummaryResponse(
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            net_savings=round(net_savings, 2),
            savings_rate_pct=round(savings_rate, 2),
            monthly_estimated_income=round(total_income, 2),
            monthly_estimated_expenses=round(total_expenses, 2),
            monthly_estimated_savings=round(net_savings, 2),
            category_wise_spending=category_breakdown,
            recurring_summary=RecurringSummary(
                total_recurring_income=round(recurring_income, 2),
                total_recurring_expenses=round(recurring_expenses, 2),
                recurring_items_count=recurring_count
            ),
            total_transactions=len(records)
        )
