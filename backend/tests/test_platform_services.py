"""
Unit and Integration Tests for MoneyLens Personal Financial Intelligence Platform.
Covers:
- Financial Profile calculations and discrepancy detection
- Statement CSV parsing and ephemeral privacy mode
- Spending Insights across 12 standard categories
- Dedicated Financial Chatbot intent detection and confirmed actions
- User data isolation
"""

import pytest
from app.schemas.profile import FinancialProfileUpdate
from app.schemas.chat import ConfirmActionRequest
from app.services.profile_service import ProfileService
from app.services.statement_service import StatementService
from app.services.spending_service import SpendingService
from app.services.chat_service import ChatService
from app.repositories.postgres_profile_repo import PostgresProfileRepository
from app.repositories.postgres_statement_repo import PostgresStatementRepository


def test_profile_metrics_calculation():
    repo = PostgresProfileRepository()
    service = ProfileService(profile_repo=repo)
    
    # Update profile for test user
    updates = FinancialProfileUpdate(
        name="Aarav Sharma",
        monthly_income=100000.0,
        essential_expenses=30000.0,
        discretionary_expenses=20000.0,
        current_savings=300000.0,
        monthly_investments=20000.0,
        active_emis=10000.0,
        active_loans=500000.0,
        other_recurring_expenses=5000.0,
    )
    profile = service.update_profile("usr_test_101", updates)

    assert profile.name == "Aarav Sharma"
    assert profile.monthly_income == 100000.0
    # Total expenses = 30k + 20k + 10k + 5k = 65,000
    assert profile.total_monthly_expenses == 65000.0
    # Monthly surplus = 100k - (65k + 20k investments) = 15,000
    assert profile.monthly_surplus == 15000.0
    assert profile.savings_rate_pct == 20.0
    assert profile.dti_ratio_pct == 10.0
    # Emergency runway = 300,000 / 65,000 = 4.6 months
    assert profile.emergency_fund_runway_months == 4.6
    assert profile.health_score >= 80


def test_statement_csv_parsing_and_categorization():
    stmt_service = StatementService()
    sample_csv = """Date,Description,Amount,Type
2026-03-01,Salary Tech,90000,Credit
2026-03-02,BigBasket Supermarket,3500,Debit
2026-03-03,Swiggy Food Delivery,750,Debit
2026-03-04,Netflix Subscription,649,Debit
2026-03-05,Bescom Electricity,2100,Debit
"""
    summary, txs = stmt_service.process_statement(
        user_id="usr_test_102",
        filename="bank_stmt.csv",
        content_bytes=sample_csv.encode("utf-8"),
        save_raw=False,
    )

    assert summary.transaction_count == 5
    assert summary.total_credits == 90000.0
    assert summary.total_debits == (3500 + 750 + 649 + 2100)
    assert summary.save_raw is False
    
    # Check categorization
    cats = {t.description: t.category for t in txs}
    assert cats["BigBasket Supermarket"] == "Food"
    assert cats["Swiggy Food Delivery"] == "Food Delivery"
    assert cats["Netflix Subscription"] == "Subscriptions"
    assert cats["Bescom Electricity"] == "Utilities"


def test_spending_insights_neutral_language():
    statement_service = StatementService()
    sample_csv = b"Date,Description,Debit,Credit\n2026-03-05,Swiggy Food Delivery,450.00,\n2026-03-10,Netflix Subscription,649.00,\n"
    statement_service.process_statement("usr_test_103", "statement.csv", sample_csv, save_raw=False)

    spending_service = SpendingService(statement_repo=statement_service.statement_repo)
    insights = spending_service.get_spending_insights("usr_test_103")

    assert insights.total_spending > 0
    assert len(insights.categories) >= 12
    assert any(c.category == "Food Delivery" for c in insights.categories)
    assert any(c.category == "Subscriptions" for c in insights.categories)
    
    # Ensure observations are evidence-based and neutral
    for obs in insights.observations:
        assert obs.evidence != ""
        assert "bad" not in obs.summary.lower()
        assert "irresponsible" not in obs.summary.lower()


def test_chat_profile_update_detection_and_confirmation():
    chat_service = ChatService()
    
    # Natural language prompt for salary update
    response = chat_service.handle_chat_message(
        message="My salary increased to ₹95,000",
        user_id="usr_test_104",
    )

    assert response.action_payload is not None
    assert response.action_payload.action_type == "UPDATE_PROFILE"
    assert response.action_payload.data.get("monthly_income") == 95000.0

    # User confirms the action
    confirm_req = ConfirmActionRequest(
        action_type="UPDATE_PROFILE",
        data={"monthly_income": 95000.0},
        user_id="usr_test_104",
    )
    confirm_res = chat_service.confirm_action(confirm_req)
    assert confirm_res.status == "success"

    # Verify profile now reflects ₹95,000
    updated_prof = chat_service.profile_service.get_profile("usr_test_104")
    assert updated_prof.monthly_income == 95000.0


def test_chat_goal_creation_intent():
    chat_service = ChatService()
    response = chat_service.handle_chat_message(
        message="I want to buy a ₹6 lakh car in 18 months",
        user_id="usr_test_105",
    )

    assert response.action_payload is not None
    assert response.action_payload.action_type == "CREATE_GOAL"
    assert response.action_payload.data.get("target_amount") == 600000.0
    assert response.action_payload.data.get("target_months") == 18

    # Confirm goal creation
    confirm_req = ConfirmActionRequest(
        action_type="CREATE_GOAL",
        data={
            "title": "Car",
            "target_amount": 600000.0,
            "target_months": 18,
            "category": "major_purchase",
        },
        user_id="usr_test_105",
    )
    confirm_res = chat_service.confirm_action(confirm_req)
    assert confirm_res.status == "success"


def test_user_data_isolation():
    profile_repo = PostgresProfileRepository()
    profile_service = ProfileService(profile_repo=profile_repo)

    # User A profile
    profile_service.update_profile("user_A", FinancialProfileUpdate(monthly_income=120000.0))
    # User B profile
    profile_service.update_profile("user_B", FinancialProfileUpdate(monthly_income=60000.0))

    prof_a = profile_service.get_profile("user_A")
    prof_b = profile_service.get_profile("user_B")

    assert prof_a.monthly_income == 120000.0
    assert prof_b.monthly_income == 60000.0
    assert prof_a.user_id == "user_A"
    assert prof_b.user_id == "user_B"
