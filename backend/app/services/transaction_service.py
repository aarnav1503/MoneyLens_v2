"""
Transaction Service.
Handles in-memory transaction repository, CRUD operations, aggregations,
and category-wise spending computations.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import date
from collections import defaultdict
from app.schemas.transactions import (
    TransactionCreate,
    TransactionResponse,
    TransactionType,
    RecurringFrequency,
    TransactionSummaryResponse,
    CategorySpending,
    RecurringSummary,
)


class InMemoryTransactionRepository:
    """
    In-memory transaction store.
    Designed with a clean interface so MySQL / SQLAlchemy can be substituted in production.
    """

    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._seed_sample_data()

    def _seed_sample_data(self):
        """No demo data. Users start with an empty transaction store."""
        pass

    def create(self, data: TransactionCreate) -> TransactionResponse:
        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        record = {
            "id": txn_id,
            **data.model_dump()
        }
        self._storage[txn_id] = record
        return TransactionResponse(**record)

    def get_all(
        self,
        transaction_type: Optional[TransactionType] = None,
        category: Optional[str] = None,
        is_recurring: Optional[bool] = None
    ) -> List[TransactionResponse]:
        results = []
        for record in self._storage.values():
            if transaction_type and record["type"] != transaction_type:
                continue
            if category and record["category"].lower() != category.lower():
                continue
            if is_recurring is not None and record["is_recurring"] != is_recurring:
                continue
            results.append(TransactionResponse(**record))
        # Sort descending by date
        results.sort(key=lambda x: x.transaction_date, reverse=True)
        return results

    def get_by_id(self, txn_id: str) -> Optional[TransactionResponse]:
        record = self._storage.get(txn_id)
        if record:
            return TransactionResponse(**record)
        return None

    def delete(self, txn_id: str) -> bool:
        if txn_id in self._storage:
            del self._storage[txn_id]
            return True
        return False

    def get_summary(self) -> TransactionSummaryResponse:
        total_income = 0.0
        total_expenses = 0.0
        recurring_income = 0.0
        recurring_expenses = 0.0
        recurring_count = 0
        
        category_totals: Dict[str, float] = defaultdict(float)
        category_counts: Dict[str, int] = defaultdict(int)

        for record in self._storage.values():
            amount = float(record["amount"])
            if record["type"] == TransactionType.INCOME:
                total_income += amount
                if record["is_recurring"]:
                    recurring_income += amount
                    recurring_count += 1
            elif record["type"] == TransactionType.EXPENSE:
                total_expenses += amount
                cat = record["category"]
                category_totals[cat] += amount
                category_counts[cat] += 1
                if record["is_recurring"]:
                    recurring_expenses += amount
                    recurring_count += 1

        net_savings = total_income - total_expenses
        savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0

        # Build category breakdowns
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
            total_transactions=len(self._storage)
        )


from app.core.config import settings
from app.repositories.postgres_transaction_repo import PostgresTransactionRepository


class TransactionRepositoryProxy:
    """
    Repository interface proxy.
    Directs operations to PostgresTransactionRepository when database configuration is present.
    Uses InMemoryTransactionRepository when no database configuration is provided (local dev/testing).
    If database configuration is present but connection fails, PostgresTransactionRepository surfaces the error directly.
    """

    def __init__(self):
        self._in_memory = InMemoryTransactionRepository()
        self._postgres = PostgresTransactionRepository()

    @property
    def active_repo(self):
        if settings.is_db_configured():
            return self._postgres
        return self._in_memory

    def create(self, data: TransactionCreate) -> TransactionResponse:
        return self.active_repo.create(data)

    def get_all(
        self,
        transaction_type: Optional[TransactionType] = None,
        category: Optional[str] = None,
        is_recurring: Optional[bool] = None
    ) -> List[TransactionResponse]:
        return self.active_repo.get_all(transaction_type, category, is_recurring)

    def get_by_id(self, txn_id: str) -> Optional[TransactionResponse]:
        return self.active_repo.get_by_id(txn_id)

    def delete(self, txn_id: str) -> bool:
        return self.active_repo.delete(txn_id)

    def get_summary(self) -> TransactionSummaryResponse:
        return self.active_repo.get_summary()


# Singleton instance for repository
transaction_repository = TransactionRepositoryProxy()

