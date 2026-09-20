"""
Goal Service.
Handles forward goal calculation, reverse goal engineering,
and in-memory goal tracking.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import date
from app.utils.calculations import (
    calculate_monthly_surplus,
    calculate_goal_feasibility,
    calculate_reverse_goal
)
from app.schemas.goals import (
    GoalCreateRequest,
    GoalResponse,
    GoalCalculationRequest,
    GoalCalculationResponse,
    ReverseGoalRequest,
    ReverseGoalResponse
)


# InMemoryGoalRepository removed — all goal storage goes through PostgresGoalRepository.
# For in-memory fallback, PostgresGoalRepository uses _SHARED_GOALS module-level dict.


from app.repositories.postgres_goal_repo import PostgresGoalRepository


class GoalService:
    """Goal evaluation and calculation engine with full user isolation."""

    def __init__(self):
        self.repository = PostgresGoalRepository()

    def get_saved_goals(self, user_id: str) -> List[GoalResponse]:
        return self.repository.get_all(user_id)

    def save_goal(self, user_id: str, req: GoalCreateRequest) -> GoalResponse:
        return self.repository.create(user_id, req)

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        return self.repository.delete(user_id, goal_id)

    def get_goal_by_id(self, user_id: str, goal_id: str) -> Optional[GoalResponse]:
        return self.repository.get_by_id(user_id, goal_id)

    @staticmethod
    def calculate_forward_goal(req: GoalCalculationRequest) -> GoalCalculationResponse:
        months = req.target_months or 12
        if req.target_date and not req.target_months:
            # Approximate months from date
            today = date.today()
            months = max(1, (req.target_date.year - today.year) * 12 + (req.target_date.month - today.month))

        calc = calculate_goal_feasibility(
            target_amount=req.target_amount,
            current_savings_allocated=req.current_savings_allocated,
            target_months=months,
            monthly_income=req.monthly_income,
            monthly_expenses=req.monthly_expenses,
            existing_emi=req.existing_emi,
            expected_annual_return_pct=req.expected_annual_return_pct
        )

        return GoalCalculationResponse(**calc)

    @staticmethod
    def calculate_reverse_goal_engine(req: ReverseGoalRequest) -> ReverseGoalResponse:
        income = req.current_monthly_income or 0.0
        expenses = req.current_monthly_expenses or 0.0
        emi = req.existing_emi or 0.0
        
        current_surplus = calculate_monthly_surplus(income, expenses, emi)
        
        calc = calculate_reverse_goal(
            target_amount=req.target_amount,
            target_months=req.target_months,
            current_monthly_surplus=current_surplus,
            expected_annual_return_pct=req.expected_annual_return_pct
        )

        req_monthly = calc["levers"]["required_monthly_saving"]
        gap = calc["levers"]["additional_monthly_needed"]

        # Actionable levers: trade-off options for the user
        expense_cut_pct_needed = round((gap / expenses * 100), 2) if expenses > 0 and gap > 0 else 0.0
        income_boost_pct_needed = round((gap / income * 100), 2) if income > 0 and gap > 0 else 0.0

        actionable_levers = {
            "required_monthly_saving": req_monthly,
            "current_surplus": current_surplus,
            "additional_monthly_needed": gap,
            "suggested_expense_cut_amount": gap if gap > 0 else 0.0,
            "suggested_expense_reduction_pct": min(100.0, expense_cut_pct_needed),
            "suggested_income_increase_pct": round(income_boost_pct_needed, 2),
            "suggested_extended_timeline_months": calc["levers"]["alternative_timeline_at_current_surplus_months"]
        }

        return ReverseGoalResponse(
            target_amount=calc["target_amount"],
            target_months=calc["target_months"],
            required_monthly_saving=req_monthly,
            current_monthly_surplus=current_surplus,
            additional_monthly_needed=gap,
            is_currently_sufficient=calc["levers"]["is_currently_sufficient"],
            alternative_timeline_at_current_surplus_months=calc["levers"]["alternative_timeline_at_current_surplus_months"],
            actionable_levers=actionable_levers,
            assumptions=calc["assumptions"]
        )


goal_service = GoalService()
