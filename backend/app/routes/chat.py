"""
Financial Chatbot API Routes.
Dedicated context-grounded financial chatbot with pending action extraction
and natural language confirmation handling.
"""

from fastapi import APIRouter, HTTPException, Query
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])
chat_service = ChatService()


@router.post("/message", response_model=ChatMessageResponse)
def send_chat_message(request: ChatMessageRequest):
    """Send a message to the financial chatbot and receive a grounded response with detected actions."""
    user_id = request.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Authenticated user ID is required")
    return chat_service.handle_chat_message(
        message=request.message,
        user_id=user_id,
        session_id=request.session_id,
        include_statement_insights=request.include_statement_insights,
    )


@router.post("/confirm-action", response_model=ConfirmActionResponse)
def confirm_detected_action(request: ConfirmActionRequest):
    """Execute a confirmed natural language profile update or goal creation."""
    return chat_service.confirm_action(request)
