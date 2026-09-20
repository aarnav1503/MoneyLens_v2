"""
Financial Radar API Routes.
Provides rule-based anomaly detection, health scoring, and cash-flow warnings.
"""

from typing import Optional, Union, Any, Dict
from fastapi import APIRouter, status, HTTPException, Query
from app.schemas.radar import (
    FinancialRadarResponse,
    FinancialRadarAnalysisResponse,
    RadarProfileRequest
)
from app.services.radar_service import radar_service
from app.services.ai_insight_service import ai_insight_service, AIInsightServiceError

router = APIRouter(prefix="/radar", tags=["Financial Radar"])


@router.get(
    "",
    response_model=FinancialRadarResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Financial Radar health and alerts"
)
def get_financial_radar(user_id: Optional[str] = Query(None, description="Authenticated user ID")):
    """
    Evaluates rule-based radar signals based on current user transactions:
    - Recurring fixed obligations burden
    - Unusually high expense anomalies
    - Emergency fund / low balance runway
    - Cash flow deficit / tight margin alerts
    - Deterministic 0-100 Financial Health Score
    """
    return radar_service.evaluate_radar(user_id=user_id)


@router.post(
    "/analyze",
    response_model=Union[FinancialRadarAnalysisResponse, FinancialRadarResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Financial Radar with custom profile (and optional AI insight)"
)
def analyze_financial_radar_custom(
    payload: RadarProfileRequest,
    include_ai: bool = Query(default=False, description="When true, attaches structured AI insights")
):
    """
    Run rule-based radar checks against a custom or hypothetical financial profile.
    Default behavior returns deterministic FinancialRadarResponse.
    When include_ai=True, returns { calculation: FinancialRadarResponse, ai_insight: AnalyzeResponse }.
    """
    if include_ai:
        try:
            return ai_insight_service.analyze_radar(
                profile=payload,
                context_note=payload.context_note
            )
        except AIInsightServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during radar AI analysis: {str(exc)}"
            )

    return radar_service.evaluate_radar(profile=payload)


@router.post(
    "/analyze/insights",
    response_model=FinancialRadarAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Financial Radar with custom profile and AI insight interpretation"
)
def analyze_financial_radar_with_ai(payload: RadarProfileRequest):
    """
    Evaluates rule-based financial radar signals on a custom profile,
    dispatches adapted signals (excluding trigger_rule) to the independent AI service,
    and returns both deterministic radar output and AI insights.
    """
    try:
        return ai_insight_service.analyze_radar(
            profile=payload,
            context_note=payload.context_note
        )
    except AIInsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during radar AI analysis: {str(exc)}"
        )

