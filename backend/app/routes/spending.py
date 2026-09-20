"""
Spending Insights API Routes.
Provides granular categorization across 12 standard categories, essential vs discretionary breakdowns,
weekend trends, and evidence-based observations.
"""

from fastapi import APIRouter, Query
from typing import Optional
from app.schemas.spending import SpendingInsightsResponse
from app.services.spending_service import SpendingService

router = APIRouter(prefix="/spending", tags=["Spending"])
spending_service = SpendingService()


@router.get("/insights", response_model=SpendingInsightsResponse)
def get_spending_insights(user_id: str = Query(..., description="Authenticated user ID")):
    """Get categorized spending insights and observations."""
    return spending_service.get_spending_insights(user_id)
