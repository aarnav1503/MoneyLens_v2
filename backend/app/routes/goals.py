"""
Goals API Routes.
All endpoints require user_id and are scoped to the authenticated user.
"""

from typing import List, Optional
from fastapi import APIRouter, status, HTTPException, Body, Query
from app.schemas.goals import (
    GoalCalculationRequest,
    GoalCalculationResponse,
    GoalAnalysisResponse,
    SavedGoalAnalysisRequest,
    SavedGoalAnalysisResponse,
    ReverseGoalRequest,
    ReverseGoalResponse,
    ReverseGoalAnalysisResponse,
    GoalCreateRequest,
    GoalResponse
)
from app.services.goal_service import goal_service
from app.services.ai_insight_service import ai_insight_service, AIInsightServiceError

router = APIRouter(prefix="/goals", tags=["Goal Engine"])


@router.post(
    "",
    response_model=GoalCalculationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate financial goal feasibility"
)
def calculate_goal_feasibility_endpoint(payload: GoalCalculationRequest):
    """Calculate whether a financial target is reachable."""
    return goal_service.calculate_forward_goal(payload)


@router.post(
    "/analyze",
    response_model=GoalAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate financial goal feasibility with AI insight interpretation"
)
def calculate_and_analyze_goal_endpoint(payload: GoalCalculationRequest):
    try:
        return ai_insight_service.analyze_goal(
            req=payload,
            title=payload.title,
            context_note=payload.context_note
        )
    except AIInsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during goal AI analysis: {str(exc)}"
        )


@router.post(
    "/reverse",
    response_model=ReverseGoalResponse,
    status_code=status.HTTP_200_OK,
    summary="Reverse goal engineering"
)
def calculate_reverse_goal_endpoint(payload: ReverseGoalRequest):
    return goal_service.calculate_reverse_goal_engine(payload)


@router.post(
    "/reverse/analyze",
    response_model=ReverseGoalAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Reverse goal engineering with AI insight interpretation"
)
def calculate_and_analyze_reverse_goal_endpoint(payload: ReverseGoalRequest):
    try:
        return ai_insight_service.analyze_reverse_goal(
            req=payload,
            context_note=payload.context_note
        )
    except AIInsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during reverse goal AI analysis: {str(exc)}"
        )


@router.get(
    "/saved",
    response_model=List[GoalResponse],
    summary="List all saved goals for the authenticated user"
)
def list_saved_goals(user_id: str = Query(..., description="Authenticated user ID")):
    """List goals for this user only — never returns another user's goals."""
    return goal_service.get_saved_goals(user_id)


@router.post(
    "/save",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a financial goal for the authenticated user"
)
def save_goal(payload: GoalCreateRequest, user_id: str = Query(..., description="Authenticated user ID")):
    """Save a new goal. Backend persists to DB and returns the created record."""
    return goal_service.save_goal(user_id, payload)


@router.post(
    "/saved/{goal_id}/analyze",
    response_model=SavedGoalAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a saved goal with deterministic calculation and AI insight"
)
def evaluate_saved_goal_endpoint(
    goal_id: str,
    user_id: str = Query(..., description="Authenticated user ID"),
    payload: Optional[SavedGoalAnalysisRequest] = Body(default=None)
):
    req_data = payload or SavedGoalAnalysisRequest()
    # Verify the goal belongs to this user
    goal = goal_service.get_goal_by_id(user_id, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found for this user")
    try:
        return ai_insight_service.analyze_saved_goal(
            goal_id=goal_id,
            monthly_income=req_data.monthly_income,
            monthly_expenses=req_data.monthly_expenses,
            existing_emi=req_data.existing_emi,
            expected_annual_return_pct=req_data.expected_annual_return_pct,
            context_note=req_data.context_note
        )
    except AIInsightServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during saved goal AI evaluation: {str(exc)}"
        )


@router.delete(
    "/saved/{goal_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a saved goal (scoped to user)"
)
def delete_saved_goal(
    goal_id: str,
    user_id: str = Query(..., description="Authenticated user ID")
):
    success = goal_service.delete_goal(user_id, goal_id)
    return {
        "success": True,
        "message": f"Goal {goal_id} deleted." if success else f"Goal {goal_id} was not found.",
        "deleted": success
    }
