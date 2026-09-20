"""
Financial Chatbot Schemas.
Handles conversational chat messages, grounded financial context, and detected actionable intents.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class PendingActionPayload(BaseModel):
    action_type: Literal["UPDATE_PROFILE", "CREATE_GOAL", "UPDATE_LOAN", "NONE"] = "NONE"
    title: str = ""
    description: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User prompt or question")
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    include_statement_insights: bool = True


class ChatMessageItem(BaseModel):
    id: str
    sender: Literal["user", "assistant", "system"]
    text: str
    timestamp: str
    action_payload: Optional[PendingActionPayload] = None
    metrics_referenced: Optional[Dict[str, Any]] = None


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    reply: str
    action_payload: Optional[PendingActionPayload] = None
    evidence: Optional[str] = None
    relevant_metrics: Optional[Dict[str, Any]] = None
    suggested_followups: List[str] = Field(default_factory=list)


class ConfirmActionRequest(BaseModel):
    action_type: Literal["UPDATE_PROFILE", "CREATE_GOAL", "UPDATE_LOAN"]
    data: Dict[str, Any]
    user_id: Optional[str] = None


class ConfirmActionResponse(BaseModel):
    status: str
    message: str
    updated_entity: Dict[str, Any]
    invalidated_queries: List[str] = Field(default_factory=list)
