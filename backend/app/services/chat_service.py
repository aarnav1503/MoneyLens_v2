"""
Dedicated Financial Chatbot Service.
Orchestrates context-aware financial discussions grounded in user profile, goals,
radar metrics, and statement intelligence.

Extracts and confirms actionable intents:
- Profile updates:
    * "My salary increased to ₹85,000" → UPDATE monthly_income
    * "My expenses are ₹35,000" → UPDATE essential + discretionary expenses
    * "I have savings of ₹2 lakh" → UPDATE current_savings
    * "I have an EMI of ₹12,000" → UPDATE active_emis
    * "I invest ₹5,000 per month in SIP" → UPDATE monthly_investments
- Goal creation: "I want to buy a ₹6 lakh car in 18 months" → CREATE goal
"""

import uuid
import re
from typing import Optional, Dict, Any, List
from app.services.intent_service import IntentService
from app.services.profile_service import ProfileService
from app.services.goal_service import GoalService
from app.services.spending_service import SpendingService
from app.schemas.chat import (
    ChatMessageResponse,
    PendingActionPayload,
    ConfirmActionRequest,
    ConfirmActionResponse,
)
from app.schemas.profile import FinancialProfileUpdate
from app.schemas.goals import GoalCreateRequest


class ChatService:
    def __init__(
        self,
        intent_service: Optional[IntentService] = None,
        profile_service: Optional[ProfileService] = None,
        goal_service: Optional[GoalService] = None,
        spending_service: Optional[SpendingService] = None,
    ):
        self.intent_service = intent_service or IntentService()
        self.profile_service = profile_service or ProfileService()
        self.goal_service = goal_service or GoalService()
        self.spending_service = spending_service or SpendingService()

    def _parse_amount_from_message(self, message: str) -> Optional[float]:
        """Try intent service first, then a raw Indian-amount parse."""
        parsed = self.intent_service.parse_intent(message)
        amount = parsed.amount or self.intent_service.parse_indian_amount(message)
        return amount if amount and amount > 0 else None

    def handle_chat_message(
        self,
        message: str,
        user_id: str,
        session_id: Optional[str] = None,
        include_statement_insights: bool = True,
    ) -> ChatMessageResponse:
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        msg_lower = message.lower()

        profile = self.profile_service.get_profile(user_id)
        current_goals = self.goal_service.get_saved_goals(user_id)
        spending_data = self.spending_service.get_spending_insights(user_id)

        # ----------------------------------------------------------------
        # 1. SALARY / INCOME UPDATE
        # Triggers: "salary", "income", "earning", "ctc", "in hand"
        # ----------------------------------------------------------------
        income_keywords = ["salary", "income", "earn", "ctc", "in hand", "inhand", "take home", "package"]
        if any(kw in msg_lower for kw in income_keywords):
            amount_val = self._parse_amount_from_message(message)
            if amount_val:
                action = PendingActionPayload(
                    action_type="UPDATE_PROFILE",
                    title="Income Update Detected",
                    description=f"Update reported monthly income from ₹{profile.monthly_income:,.0f} to ₹{amount_val:,.0f}",
                    data={"monthly_income": amount_val, "field": "Monthly Income"},
                )
                new_surplus = amount_val - profile.total_monthly_expenses
                return ChatMessageResponse(
                    message_id=msg_id,
                    session_id=session_id,
                    reply=(
                        f"I detected a monthly income of ₹{amount_val:,.0f}. "
                        f"If confirmed, your estimated monthly surplus would be ₹{max(0, new_surplus):,.0f}. "
                        "Should I update your financial profile?"
                    ),
                    action_payload=action,
                    evidence=f"Current income: ₹{profile.monthly_income:,.0f} | Proposed: ₹{amount_val:,.0f}",
                    relevant_metrics={"current_income": profile.monthly_income, "proposed_income": amount_val},
                    suggested_followups=["Yes, update my income", "Keep current income", "What will my new surplus be?"],
                )
            else:
                # Asked about salary without a number
                return ChatMessageResponse(
                    message_id=msg_id,
                    session_id=session_id,
                    reply=(
                        f"Your current recorded monthly income is ₹{profile.monthly_income:,.0f}. "
                        "If your salary has changed, just mention the new amount — e.g., 'My salary is now ₹75,000'."
                    ),
                    evidence=f"Profile income: ₹{profile.monthly_income:,.0f}",
                    relevant_metrics={"monthly_income": profile.monthly_income},
                    suggested_followups=["My salary changed to ₹80,000", "How is my health score calculated?"],
                )

        # ----------------------------------------------------------------
        # 2. EXPENSE UPDATE
        # Triggers: "expense", "spending" + update keyword
        # ----------------------------------------------------------------
        expense_keywords = ["expense", "spending", "spend"]
        update_keywords = ["update", "increased", "is now", "is", "changed to", "became", "my"]
        if any(kw in msg_lower for kw in expense_keywords) and any(kw in msg_lower for kw in update_keywords):
            amount_val = self._parse_amount_from_message(message)
            if amount_val:
                essential_share = round(amount_val * 0.6, 2)
                disc_share = round(amount_val * 0.4, 2)
                action = PendingActionPayload(
                    action_type="UPDATE_PROFILE",
                    title="Expenses Update Detected",
                    description=f"Update total monthly expenses to ₹{amount_val:,.0f} (essential: ₹{essential_share:,.0f}, discretionary: ₹{disc_share:,.0f})",
                    data={"essential_expenses": essential_share, "discretionary_expenses": disc_share, "field": "Monthly Expenses"},
                )
                new_surplus = profile.monthly_income - amount_val
                return ChatMessageResponse(
                    message_id=msg_id,
                    session_id=session_id,
                    reply=(
                        f"I detected monthly expenses of ₹{amount_val:,.0f}. "
                        f"Your new estimated surplus would be ₹{max(0, new_surplus):,.0f}/month. "
                        "Should I apply this to your profile?"
                    ),
                    action_payload=action,
                    evidence=f"Current total expenses: ₹{profile.total_monthly_expenses:,.0f}",
                    relevant_metrics={"current_expenses": profile.total_monthly_expenses, "proposed_expenses": amount_val},
                    suggested_followups=["Yes, update my expenses", "Cancel", "How does this affect my emergency fund?"],
                )

        # ----------------------------------------------------------------
        # 3. SAVINGS / BALANCE UPDATE
        # Triggers: "savings", "saved", "balance", "emergency fund", "have in bank"
        # ----------------------------------------------------------------
        savings_keywords = ["savings", "saved", "have in bank", "balance", "emergency fund", "bank balance", "in account"]
        if any(kw in msg_lower for kw in savings_keywords):
            amount_val = self._parse_amount_from_message(message)
            if amount_val:
                action = PendingActionPayload(
                    action_type="UPDATE_PROFILE",
                    title="Savings Balance Update Detected",
                    description=f"Update liquid savings balance to ₹{amount_val:,.0f}",
                    data={"current_savings": amount_val, "field": "Current Savings"},
                )
                runway = round(amount_val / max(1, profile.total_monthly_expenses), 1)
                return ChatMessageResponse(
                    message_id=msg_id,
                    session_id=session_id,
                    reply=(
                        f"I detected a savings balance of ₹{amount_val:,.0f}. "
                        f"At your current expense level, this covers approximately {runway} months of expenses. "
                        "Should I update your savings balance?"
                    ),
                    action_payload=action,
                    evidence=f"Current recorded savings: ₹{profile.current_savings:,.0f} | Proposed: ₹{amount_val:,.0f}",
                    relevant_metrics={"current_savings": profile.current_savings, "proposed_savings": amount_val, "new_runway": runway},
                    suggested_followups=["Yes, update savings", "Cancel", "Is my emergency fund sufficient?"],
                )

        # ----------------------------------------------------------------
        # 4. LOAN / EMI UPDATE
        # Triggers: "loan", "emi", "loan emi", "monthly emi"
        # ----------------------------------------------------------------
        emi_keywords = ["emi", "loan emi", "monthly emi", "installment", "home loan emi", "car emi", "car loan"]
        loan_keywords = ["loan", "borrowed", "debt"]
        
        # Check for complex loan + EMI (e.g., "I have a 2 lakh loan with 6000 EMI")
        if any(kw in msg_lower for kw in loan_keywords) and any(kw in msg_lower for kw in emi_keywords):
            # Try to extract two amounts. This is basic; we'll assume the larger is loan and smaller is EMI.
            numbers = [float(x.replace(",", "")) for x in re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', message)]
            # Also try intent service for lakh/k words
            parsed_amt = self._parse_amount_from_message(message)
            
            amounts = []
            if parsed_amt: amounts.append(parsed_amt)
            amounts.extend(numbers)
            amounts = sorted(list(set([a for a in amounts if a > 0])), reverse=True)
            
            if len(amounts) >= 2:
                loan_amt = amounts[0]
                emi_amt = amounts[1]
                
                # If they say "2 lakh loan with 6k EMI", parsed_amt might be 200000. numbers might have 6000.
                if loan_amt > emi_amt:
                    action = PendingActionPayload(
                        action_type="UPDATE_LOAN",
                        title="Loan & EMI Update Detected",
                        description=f"Update active loans to ₹{loan_amt:,.0f} and monthly EMI to ₹{emi_amt:,.0f}",
                        data={"active_loans": loan_amt, "active_emis": emi_amt, "field": "Loans and EMIs"},
                    )
                    dti = round((emi_amt / max(1, profile.monthly_income)) * 100, 1)
                    return ChatMessageResponse(
                        message_id=msg_id,
                        session_id=session_id,
                        reply=(
                            f"I detected a total loan of ₹{loan_amt:,.0f} with a monthly EMI of ₹{emi_amt:,.0f}. "
                            f"This EMI is {dti}% of your reported income. "
                            "Should I update your profile with this loan and EMI?"
                        ),
                        action_payload=action,
                        evidence=f"Proposed Loan: ₹{loan_amt:,.0f} | Proposed EMI: ₹{emi_amt:,.0f}",
                        relevant_metrics={"proposed_loan": loan_amt, "proposed_emi": emi_amt, "dti_pct": dti},
                        suggested_followups=["Yes, update my loan details", "Cancel"],
                    )

        if any(kw in msg_lower for kw in emi_keywords):
            amount_val = self._parse_amount_from_message(message)
            if amount_val:
                action = PendingActionPayload(
                    action_type="UPDATE_PROFILE",
                    title="EMI Update Detected",
                    description=f"Update active monthly EMI to ₹{amount_val:,.0f}",
                    data={"active_emis": amount_val, "field": "Active EMIs"},
                )
                dti = round((amount_val / max(1, profile.monthly_income)) * 100, 1)
                return ChatMessageResponse(
                    message_id=msg_id,
                    session_id=session_id,
                    reply=(
                        f"I detected a monthly EMI of ₹{amount_val:,.0f}. "
                        f"This is {dti}% of your reported income — "
                        f"{'within the recommended 40% threshold.' if dti < 40 else 'above the recommended 40% threshold, which may strain your finances.'} "
                        "Should I update your EMI commitment in your profile?"
                    ),
                    action_payload=action,
                    evidence=f"Current EMI: ₹{profile.active_emis:,.0f} | Proposed: ₹{amount_val:,.0f} | DTI: {dti}%",
                    relevant_metrics={"current_emi": profile.active_emis, "proposed_emi": amount_val, "dti_pct": dti},
                    suggested_followups=["Yes, update my EMI", "Cancel", "How does this affect my health score?"],
                )

        # ----------------------------------------------------------------
        # 5. INVESTMENT / SIP UPDATE
        # Triggers: "invest", "sip", "mutual fund", "mf", "nps", "ppf"
        # ----------------------------------------------------------------
        invest_keywords = ["invest", "sip", "mutual fund", "mf", "nps", "ppf", "recurring deposit", "rd"]
        if any(kw in msg_lower for kw in invest_keywords):
            amount_val = self._parse_amount_from_message(message)
            if amount_val:
                action = PendingActionPayload(
                    action_type="UPDATE_PROFILE",
                    title="Investment Contribution Detected",
                    description=f"Update monthly investments/SIP to ₹{amount_val:,.0f}",
                    data={"monthly_investments": amount_val, "field": "Monthly Investments"},
                )
                savings_rate = round((amount_val / max(1, profile.monthly_income)) * 100, 1)
                return ChatMessageResponse(
                    message_id=msg_id,
                    session_id=session_id,
                    reply=(
                        f"I detected a monthly investment contribution of ₹{amount_val:,.0f}. "
                        f"This represents a {savings_rate}% investment rate — "
                        f"{'excellent discipline!' if savings_rate >= 20 else 'a good start towards wealth building.'} "
                        "Should I update your investment profile?"
                    ),
                    action_payload=action,
                    evidence=f"Current monthly investments: ₹{profile.monthly_investments:,.0f} | Proposed: ₹{amount_val:,.0f}",
                    relevant_metrics={"current_investments": profile.monthly_investments, "proposed_investments": amount_val, "savings_rate": savings_rate},
                    suggested_followups=["Yes, update investments", "Cancel", "How does this affect my net worth projection?"],
                )

        # ----------------------------------------------------------------
        # 6. GOAL CREATION
        # ----------------------------------------------------------------
        goal_triggers = ["goal", "want to buy", "saving for", "save for", "plan for", "target for", "purchase"]
        if any(kw in msg_lower for kw in goal_triggers) and not any(kw in msg_lower for kw in ["delete", "remove", "cancel"]):
            parsed_intent = self.intent_service.parse_intent(message)
            target_amt = parsed_intent.amount or self.intent_service.parse_indian_amount(message) or 500000.0
            timeline = parsed_intent.timeline_months or 12
            goal_title = parsed_intent.item or "New Financial Goal"
            monthly_needed = round(target_amt / max(1, timeline), 0)
            feasible = monthly_needed <= profile.monthly_surplus

            action = PendingActionPayload(
                action_type="CREATE_GOAL",
                title="Goal Detected",
                description=f"Create goal '{goal_title.title()}' for ₹{target_amt:,.0f} over {timeline} months.",
                data={
                    "title": goal_title.title(),
                    "target_amount": target_amt,
                    "target_months": timeline,
                    "category": "major_purchase",
                    "monthly_contribution": monthly_needed,
                },
            )
            feasibility_note = (
                f"Your current surplus of ₹{profile.monthly_surplus:,.0f}/month can cover this goal."
                if feasible
                else f"This requires ₹{monthly_needed:,.0f}/month but your current surplus is ₹{profile.monthly_surplus:,.0f}/month — you may need to reduce spending."
            )
            return ChatMessageResponse(
                message_id=msg_id,
                session_id=session_id,
                reply=(
                    f"I structured a goal for '{goal_title.title()}' — ₹{target_amt:,.0f} in {timeline} months "
                    f"(≈ ₹{monthly_needed:,.0f}/month required). {feasibility_note} "
                    "Would you like to add this as an active goal?"
                ),
                action_payload=action,
                evidence=f"Target: ₹{target_amt:,.0f} | Horizon: {timeline} months | Monthly surplus: ₹{profile.monthly_surplus:,.0f}",
                relevant_metrics={"target_amount": target_amt, "target_months": timeline, "monthly_surplus": profile.monthly_surplus},
                suggested_followups=["Add this goal", "Edit the timeline", "Can I afford this right now?"],
            )

        # ----------------------------------------------------------------
        # 7. FINANCIAL HEALTH / SURPLUS / SAVINGS RATE QUERY
        # ----------------------------------------------------------------
        health_triggers = ["surplus", "health", "how am i doing", "financial health", "score", "savings rate", "how much do i save"]
        if any(kw in msg_lower for kw in health_triggers):
            return ChatMessageResponse(
                message_id=msg_id,
                session_id=session_id,
                reply=(
                    f"Your gross monthly income is ₹{profile.monthly_income:,.0f}. "
                    f"Total monthly outflows are ₹{profile.total_monthly_expenses:,.0f}, "
                    f"leaving an uncommitted surplus of ₹{profile.monthly_surplus:,.0f}/month "
                    f"(savings rate: {profile.savings_rate_pct}%). "
                    f"Your liquid emergency buffer is ₹{profile.current_savings:,.0f}, "
                    f"covering {profile.emergency_fund_runway_months} months. "
                    f"Overall financial health score: {profile.health_score}/100."
                ),
                evidence=f"Income ₹{profile.monthly_income:,.0f}, Expenses ₹{profile.total_monthly_expenses:,.0f}, Savings ₹{profile.current_savings:,.0f}",
                relevant_metrics={
                    "monthly_income": profile.monthly_income,
                    "total_expenses": profile.total_monthly_expenses,
                    "monthly_surplus": profile.monthly_surplus,
                    "runway_months": profile.emergency_fund_runway_months,
                    "health_score": profile.health_score,
                },
                suggested_followups=["Simulate a purchase", "View spending insights", "Review active goals"],
            )

        # ----------------------------------------------------------------
        # 8. SPENDING BREAKDOWN QUERY
        # ----------------------------------------------------------------
        if any(kw in msg_lower for kw in ["spending", "category", "statement", "where did my money", "where is my money"]):
            return ChatMessageResponse(
                message_id=msg_id,
                session_id=session_id,
                reply=(
                    f"Your total monthly tracked spending is ₹{spending_data.total_spending:,.0f}. "
                    f"Essential obligations: ₹{spending_data.essential_total:,.0f} ({spending_data.essential_pct}%), "
                    f"discretionary outflows: ₹{spending_data.discretionary_total:,.0f} ({spending_data.discretionary_pct}%). "
                    f"Fixed recurring subscriptions & utilities: ₹{spending_data.recurring_total:,.0f}/month."
                ),
                evidence=f"Analysis from {len(spending_data.categories)} spending categories.",
                relevant_metrics={"total_spending": spending_data.total_spending, "essential_pct": spending_data.essential_pct},
                suggested_followups=["Break down food delivery", "How can I increase my surplus?", "Upload a new statement"],
            )

        # ----------------------------------------------------------------
        # 9. DEFAULT GROUNDED RESPONSE
        # ----------------------------------------------------------------
        has_data = profile.monthly_income > 0

        return ChatMessageResponse(
            message_id=msg_id,
            session_id=session_id,
            reply=(
                f"I can help you with salary updates, expense changes, savings, EMI tracking, goal planning, and spending analysis. "
                + (
                    f"Your current baseline: ₹{profile.monthly_income:,.0f} income, ₹{profile.monthly_surplus:,.0f} surplus/month, health score {profile.health_score}/100."
                    if has_data
                    else
                    "Upload your bank statement in the Spending tab first — I'll automatically read your income and expenses from it. Or tell me: 'My salary is ₹X' to get started."
                )
            ),
            relevant_metrics={"monthly_surplus": profile.monthly_surplus, "health_score": profile.health_score},
            suggested_followups=[
                "My salary is ₹75,000",
                "I have savings of ₹2 lakh",
                "I invest ₹5,000 per month in SIP",
                "I want to save for a car worth ₹8 lakh",
            ],
        )

    def confirm_action(self, request: ConfirmActionRequest) -> ConfirmActionResponse:
        """Executes a confirmed natural language action. user_id MUST be present."""
        user_id = request.user_id
        if not user_id:
            return ConfirmActionResponse(
                status="error",
                message="User identity is required to save changes. Please log in and try again.",
                updated_entity={},
            )

        if request.action_type in ["UPDATE_PROFILE", "UPDATE_LOAN"]:
            update_data = request.data
            # Filter to only valid FinancialProfileUpdate fields
            valid_fields = set(FinancialProfileUpdate.model_fields.keys())
            filtered = {k: v for k, v in update_data.items() if k in valid_fields}
            if not filtered:
                return ConfirmActionResponse(
                    status="error",
                    message="No valid profile fields to update.",
                    updated_entity={},
                    invalidated_queries=[]
                )
            updates = FinancialProfileUpdate(**filtered)
            # Will raise DatabaseConnectionError if DB write fails — caller gets a 500
            updated_prof = self.profile_service.update_profile(user_id, updates)
            return ConfirmActionResponse(
                status="success",
                message=f"Profile updated. New surplus: ₹{updated_prof.monthly_surplus:,.0f}/month, health score: {updated_prof.health_score}/100.",
                updated_entity=updated_prof.model_dump(),
                invalidated_queries=["profile", "spending", "goals", "statement_transactions"]
            )

        elif request.action_type == "CREATE_GOAL":
            goal_data = request.data
            create_req = GoalCreateRequest(
                title=goal_data.get("title", "New Goal"),
                target_amount=float(goal_data.get("target_amount", 100000.0)),
                target_months=int(goal_data.get("target_months", 12)),
                category=goal_data.get("category", "major_purchase"),
                current_savings_allocated=0.0,
            )
            # Will raise DatabaseConnectionError if DB write fails — caller gets a 500
            saved_goal = self.goal_service.save_goal(user_id, create_req)
            return ConfirmActionResponse(
                status="success",
                message=f"Goal '{saved_goal.title}' saved to your profile.",
                updated_entity=saved_goal.model_dump(),
                invalidated_queries=["goals", "profile"]
            )

        return ConfirmActionResponse(
            status="error",
            message="Unknown action type.",
            updated_entity={},
            invalidated_queries=[]
        )
