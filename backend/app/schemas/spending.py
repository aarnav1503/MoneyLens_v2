"""
Spending Insights Schemas.
12 Standard Categories:
Food, Restaurants, Food Delivery, Shopping, Transport, Entertainment,
Subscriptions, Utilities, Healthcare, Education, Travel, Other.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


STANDARD_SPENDING_CATEGORIES = [
    "Food",
    "Restaurants",
    "Food Delivery",
    "Shopping",
    "Transport",
    "Entertainment",
    "Subscriptions",
    "Utilities",
    "Healthcare",
    "Education",
    "Travel",
    "Investments",
    "EMI/Loan",
    "Other",
]


class CategorySpendingItem(BaseModel):
    category: str
    total_amount: float
    percentage_of_total: float
    transaction_count: int
    is_essential: bool
    is_recurring: bool
    period_change_pct: Optional[float] = None


class SpendingObservation(BaseModel):
    type: str  # 'spending_trend', 'recurring', 'frequent_small', 'weekend_pattern', 'cashflow_risk', 'positive'
    title: str
    summary: str
    evidence: str
    relevant_metrics: Dict[str, Any] = Field(default_factory=dict)
    implication: str
    possible_action: str


class SpendingInsightsResponse(BaseModel):
    total_spending: float
    essential_total: float
    discretionary_total: float
    essential_pct: float
    discretionary_pct: float
    recurring_total: float
    weekend_spending: float
    weekday_spending: float
    weekend_pct: float
    frequent_small_purchases_total: float
    frequent_small_purchases_count: int
    categories: List[CategorySpendingItem]
    monthly_trends: List[Dict[str, Any]] = Field(default_factory=list)
    repeated_merchants: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[SpendingObservation] = Field(default_factory=list)
