"""
Bank Statement API Routes.
Provides endpoints for statement uploads with privacy consent, processing summaries, and derived analytics.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from app.schemas.statements import StatementAnalysisSummary, StatementTransactionItem
from app.services.statement_service import StatementService
from app.schemas.profile import FinancialProfileResponse
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/statements", tags=["Statements"])
statement_service = StatementService()
profile_service = ProfileService()


class ObservationConfirmRequest(BaseModel):
    observation_type: str
    field: str
    value: float
    user_id: str



@router.post("/upload", response_model=StatementAnalysisSummary)
async def upload_statement(
    file: UploadFile = File(...),
    save_raw: bool = Form(default=False),
    user_id: str = Form(..., description="Authenticated user ID"),
):
    """
    Upload and process a bank statement (CSV or PDF).
    Adheres strictly to the user's `save_raw` privacy choice.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    summary, _ = statement_service.process_statement(
        user_id=user_id,
        filename=file.filename or "statement.csv",
        content_bytes=content,
        save_raw=save_raw,
    )
    return summary


@router.get("/history", response_model=List[dict])
def get_user_statements(user_id: str = Query(..., description="Authenticated user ID")):
    """Get list of previously processed statement summaries."""
    return statement_service.statement_repo.get_user_statements(user_id)


@router.get("/transactions", response_model=List[dict])
def get_statement_transactions(user_id: str = Query(..., description="Authenticated user ID")):
    """Get all categorized transactions extracted from statements."""
    return statement_service.statement_repo.get_user_transactions(user_id)


@router.post("/confirm-observation", response_model=FinancialProfileResponse)
def confirm_statement_observation(request: ObservationConfirmRequest):
    """Confirm a detected statement observation and update the user's profile."""
    updates = {request.field: request.value}
    
    # If the observation is emi_detected and we want to update active_emis, 
    # we just pass it in the updates dict.
    from app.schemas.profile import FinancialProfileUpdate
    
    prof_update = FinancialProfileUpdate(**updates)
    return profile_service.update_profile(request.user_id, prof_update)
