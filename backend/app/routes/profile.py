"""
Financial Profile API Routes.
Provides endpoints to fetch and update the user's detailed financial profile and check for statement discrepancies.
"""

from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List
from app.schemas.profile import FinancialProfileResponse, FinancialProfileUpdate, DiscrepancyComparison
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profile"])
profile_service = ProfileService()


@router.get("", response_model=FinancialProfileResponse)
def get_user_profile(user_id: str = Query(..., description="Authenticated user ID")):
    """Get the current user's financial profile."""
    prof = profile_service.get_profile(user_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof


@router.put("", response_model=FinancialProfileResponse)
@router.patch("", response_model=FinancialProfileResponse)
def update_user_profile(updates: FinancialProfileUpdate, user_id: str = Query(..., description="Authenticated user ID")):
    """Update the current user's financial profile."""
    return profile_service.update_profile(user_id, updates)


@router.get("/discrepancies", response_model=List[DiscrepancyComparison])
def get_profile_discrepancies(user_id: str = Query(..., description="Authenticated user ID")):
    """Check for discrepancies between reported profile expenses and statement debits."""
    return profile_service.check_discrepancies(user_id)
