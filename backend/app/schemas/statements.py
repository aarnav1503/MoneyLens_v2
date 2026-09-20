"""
Bank Statement Intelligence Schemas.
Handles PDF/CSV statement uploads, consent flags, extracted transactions, and discrepancy reports.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class StatementUploadConsent(BaseModel):
    save_raw: bool = Field(..., description="Whether Money Lens is permitted to securely save the raw statement file")


class StatementTransactionItem(BaseModel):
    id: Optional[str] = None
    date: str
    description: str
    amount: float
    type: str = Field(..., description="'credit' or 'debit'")
    category: str = Field(default="Other")
    is_recurring: bool = False
    is_essential: bool = False
    source: str = Field(default="text", description="'text' or 'ocr'")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class PendingObservation(BaseModel):
    type: str  # salary_detected, emi_detected, investment_detected, recurring_detected
    field: str  # profile field to update
    amount: float
    description: str
    confidence: float
    current_value: float  # existing profile value for comparison


class StatementAnalysisSummary(BaseModel):
    statement_id: str
    filename: str
    save_raw: bool
    total_credits: float
    total_debits: float
    net_cashflow: float
    transaction_count: int
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    category_breakdown: Dict[str, float] = Field(default_factory=dict)
    essential_spending: float = 0.0
    discretionary_spending: float = 0.0
    recurring_spending: float = 0.0
    frequent_merchants: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    profile_discrepancies: List[Dict[str, Any]] = Field(default_factory=list)
    extraction_source: str = "text"
    detected_salary: Optional[float] = None
    detected_emis: List[Dict[str, Any]] = Field(default_factory=list)
    detected_investments: List[Dict[str, Any]] = Field(default_factory=list)
    detected_recurring: List[Dict[str, Any]] = Field(default_factory=list)
    pending_observations: List[PendingObservation] = Field(default_factory=list)
