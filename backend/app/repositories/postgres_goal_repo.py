"""
PostgreSQL Goal Repository.
Provides CRUD operations for financial goals using PostgreSQL / AWS RDS.
ALL queries are scoped to user_id — goals are never shared across users.
"""

import uuid
from typing import List, Optional, Union
from app.core.database import get_db_connection, DatabaseConnectionError, DatabaseNotConfiguredError
from app.core.config import settings
from app.schemas.goals import GoalCreateRequest, GoalResponse

# Module-level in-memory store keyed by user_id (list of goal dicts per user).
# Used when DB is not configured or unavailable.
_SHARED_GOALS: dict = {}  # { user_id: { goal_id: dict } }


class PostgresGoalRepository:
    """PostgreSQL / RDS implementation of the Goal Repository, scoped per user."""

    def create(self, user_id: Union[str, GoalCreateRequest] = "default", data: Optional[GoalCreateRequest] = None) -> GoalResponse:
        if isinstance(user_id, GoalCreateRequest):
            data = user_id
            user_id = "default"

        goal_id = f"goal_{uuid.uuid4().hex[:12]}"

        if settings.is_db_configured():
            query = """
            INSERT INTO goals (
                id, user_id, title, target_amount, current_savings_allocated,
                target_months, target_date, category, priority
            ) VALUES (
                %(id)s, %(user_id)s, %(title)s, %(target_amount)s, %(current_savings_allocated)s,
                %(target_months)s, %(target_date)s, %(category)s, %(priority)s
            )
            RETURNING id, user_id, title, target_amount, current_savings_allocated,
                      target_months, target_date, category, priority;
            """
            params = {
                "id": goal_id,
                "user_id": user_id,
                "title": data.title,
                "target_amount": float(data.target_amount),
                "current_savings_allocated": float(data.current_savings_allocated),
                "target_months": data.target_months,
                "target_date": data.target_date,
                "category": data.category,
                "priority": data.priority,
            }
            # Do NOT catch exceptions — surface DB failures to caller
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    row = cur.fetchone()
                    result = GoalResponse(**row)
                    # Sync to in-memory cache
                    _SHARED_GOALS.setdefault(user_id, {})[goal_id] = row
                    return result

        # In-memory fallback (no DB configured)
        record = {
            "id": goal_id,
            "user_id": user_id,
            **data.model_dump()
        }
        _SHARED_GOALS.setdefault(user_id, {})[goal_id] = record
        return GoalResponse(**record)

    def get_all(self, user_id: str = "default") -> List[GoalResponse]:
        if settings.is_db_configured():
            query = """
            SELECT id, user_id, title, target_amount, current_savings_allocated,
                   target_months, target_date, category, priority
            FROM goals
            WHERE user_id = %(user_id)s
            ORDER BY created_at DESC;
            """
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, {"user_id": user_id})
                        rows = cur.fetchall()
                        return [GoalResponse(**r) for r in rows]
            except (DatabaseConnectionError, DatabaseNotConfiguredError):
                # Fall through to memory if DB temporarily unavailable
                pass

        user_goals = _SHARED_GOALS.get(user_id, {})
        return [GoalResponse(**r) for r in user_goals.values()]

    def get_by_id(self, user_id_or_goal_id: str, goal_id: Optional[str] = None) -> Optional[GoalResponse]:
        if goal_id is None:
            goal_id = user_id_or_goal_id
            user_id = "default"
        else:
            user_id = user_id_or_goal_id

        if settings.is_db_configured():
            query = """
            SELECT id, user_id, title, target_amount, current_savings_allocated,
                   target_months, target_date, category, priority
            FROM goals
            WHERE id = %(id)s AND user_id = %(user_id)s;
            """
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, {"id": goal_id, "user_id": user_id})
                        row = cur.fetchone()
                        if row:
                            return GoalResponse(**row)
                        return None
            except (DatabaseConnectionError, DatabaseNotConfiguredError):
                pass

        record = _SHARED_GOALS.get(user_id, {}).get(goal_id)
        return GoalResponse(**record) if record else None

    def delete(self, user_id_or_goal_id: str, goal_id: Optional[str] = None) -> bool:
        if goal_id is None:
            goal_id = user_id_or_goal_id
            user_id = "default"
        else:
            user_id = user_id_or_goal_id

        if settings.is_db_configured():
            query = "DELETE FROM goals WHERE id = %(id)s AND user_id = %(user_id)s RETURNING id;"
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(query, {"id": goal_id, "user_id": user_id})
                        deleted = cur.fetchone()
                        if deleted:
                            _SHARED_GOALS.get(user_id, {}).pop(goal_id, None)
                            return True
                        return False
            except (DatabaseConnectionError, DatabaseNotConfiguredError):
                pass

        user_goals = _SHARED_GOALS.get(user_id, {})
        if goal_id in user_goals:
            del user_goals[goal_id]
            return True
        return False
