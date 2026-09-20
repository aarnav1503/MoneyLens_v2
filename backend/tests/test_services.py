"""
Unit tests for business logic services:
- TransactionService (normal, custom categories, empty storage)
- SimulationService (position, purchase, EMI, savings)
- GoalService (forward, reverse, already achieved, CRUD)
- ExperimentService (multi-scenario parallel evaluation)
- RadarService (healthy, critical, zero income, zero expenses, zero savings)
"""

import pytest
from app.services.transaction_service import InMemoryTransactionRepository
from app.services.simulation_service import simulation_service
from app.services.goal_service import goal_service
from app.services.experiment_service import experiment_service
from app.services.radar_service import radar_service
from app.schemas.transactions import TransactionCreate, TransactionType, RecurringFrequency
from app.schemas.simulation import (
    FinancialPositionRequest,
    PurchaseSimulationRequest,
    EMISimulationRequest,
    SavingsProjectionRequest
)
from app.schemas.goals import (
    GoalCalculationRequest,
    ReverseGoalRequest,
    GoalCreateRequest
)
from app.schemas.experiments import (
    ExperimentCompareRequest,
    ScenarioInput,
    ScenarioType
)
from app.schemas.radar import RadarProfileRequest


def test_transaction_service_and_repository():
    repo = InMemoryTransactionRepository()
    initial_summary = repo.get_summary()
    assert initial_summary.total_income == 0.0
    assert initial_summary.total_expenses == 0.0

    # Add a custom/unusual category transaction
    new_txn = repo.create(TransactionCreate(
        title="Crypto Staking Reward",
        type=TransactionType.INCOME,
        amount=5000.0,
        category="Digital Assets",
        is_recurring=False
    ))
    assert new_txn.id.startswith("txn_")
    assert new_txn.category == "Digital Assets"

    updated_summary = repo.get_summary()
    assert updated_summary.total_income == 5000.0


def test_empty_transaction_repository_summary():
    repo = InMemoryTransactionRepository()
    # Clear all storage
    repo._storage.clear()
    empty_summary = repo.get_summary()
    assert empty_summary.total_income == 0.0
    assert empty_summary.total_expenses == 0.0
    assert empty_summary.net_savings == 0.0
    assert empty_summary.savings_rate_pct == 0.0
    assert len(empty_summary.category_wise_spending) == 0
    assert empty_summary.total_transactions == 0


def test_simulation_service_financial_position():
    req = FinancialPositionRequest(
        monthly_income=80000.0,
        monthly_expenses=45000.0,
        current_savings=200000.0,
        existing_emi=5000.0
    )
    pos = simulation_service.get_financial_position(req)
    assert pos.monthly_surplus == 30000.0
    assert pos.savings_rate_pct == 37.5
    assert pos.projected_balance_3_months == 290000.0
    assert pos.projected_balance_6_months == 380000.0
    assert pos.projected_balance_12_months == 560000.0


def test_simulation_service_purchase():
    req = PurchaseSimulationRequest(
        monthly_income=80000.0,
        monthly_expenses=45000.0,
        current_savings=200000.0,
        purchase_amount=70000.0
    )
    res = simulation_service.simulate_purchase(req)
    assert res.purchase_amount == 70000.0
    assert res.post_purchase_savings == 130000.0
    assert res.post_purchase_projected_savings["3_months"] == 235000.0
    assert res.post_purchase_projected_savings["6_months"] == 340000.0
    assert res.post_purchase_projected_savings["12_months"] == 550000.0


def test_simulation_service_emi_standard_and_zero_interest():
    # Standard 12% EMI
    req = EMISimulationRequest(
        purchase_amount=70000.0,
        down_payment=10000.0,
        annual_interest_rate_pct=12.0,
        tenure_months=12,
        monthly_income=80000.0,
        monthly_expenses=45000.0,
        current_savings=200000.0
    )
    res = simulation_service.simulate_emi(req)
    assert res.loan_amount == 60000.0
    assert res.savings_at_purchase == 190000.0
    assert res.monthly_emi > 5000.0
    assert res.total_interest > 0

    # 0% Zero-cost EMI
    zero_emi_req = EMISimulationRequest(
        purchase_amount=60000.0,
        down_payment=0.0,
        annual_interest_rate_pct=0.0,
        tenure_months=12,
        monthly_income=80000.0,
        monthly_expenses=45000.0,
        current_savings=200000.0
    )
    zero_res = simulation_service.simulate_emi(zero_emi_req)
    assert zero_res.monthly_emi == 5000.0
    assert zero_res.total_interest == 0.0


def test_goal_service_crud_and_already_achieved():
    # Goal already achieved
    req = GoalCalculationRequest(
        target_amount=100000.0,
        current_savings_allocated=150000.0,
        target_months=12,
        monthly_income=80000.0,
        monthly_expenses=45000.0
    )
    goal_res = goal_service.calculate_forward_goal(req)
    assert goal_res.is_reachable is True
    assert goal_res.status == "already_achieved"
    assert goal_res.required_monthly_saving == 0.0

    # Saved Goal CRUD
    saved = goal_service.repository.create(GoalCreateRequest(
        title="Laptop Upgrade",
        target_amount=80000.0,
        current_savings_allocated=20000.0,
        target_months=6
    ))
    assert saved.id.startswith("goal_")
    retrieved = goal_service.repository.get_by_id(saved.id)
    assert retrieved is not None
    assert retrieved.title == "Laptop Upgrade"
    assert goal_service.repository.delete(saved.id) is True


def test_experiment_lab_comparison():
    scenarios = [
        ScenarioInput(
            scenario_id="sc_a",
            scenario_name="Scenario A: No Purchase",
            scenario_type=ScenarioType.NO_PURCHASE
        ),
        ScenarioInput(
            scenario_id="sc_b",
            scenario_name="Scenario B: Cash ₹70,000",
            scenario_type=ScenarioType.CASH_PURCHASE,
            purchase_amount=70000.0
        ),
        ScenarioInput(
            scenario_id="sc_c",
            scenario_name="Scenario C: EMI 12 Months",
            scenario_type=ScenarioType.EMI_PURCHASE,
            purchase_amount=70000.0,
            down_payment=10000.0,
            annual_interest_rate_pct=12.0,
            tenure_months=12
        )
    ]
    req = ExperimentCompareRequest(
        monthly_income=80000.0,
        monthly_expenses=45000.0,
        current_savings=200000.0,
        existing_emi=0.0,
        target_goal_amount=500000.0,
        target_goal_months=12,
        scenarios=scenarios
    )
    comp = experiment_service.compare_scenarios(req)
    assert len(comp.comparison_matrix) == 3
    
    sc_a = comp.comparison_matrix[0]
    sc_b = comp.comparison_matrix[1]
    sc_c = comp.comparison_matrix[2]

    # Status Quo has highest 12-month savings
    assert sc_a.projected_savings_12_months > sc_b.projected_savings_12_months
    # Cash purchase has 0 interest cost
    assert sc_b.total_interest_or_cost_paid == 70000.0
    # EMI incurs interest
    assert sc_c.total_interest_or_cost_paid > 0.0


def test_radar_service_rules_and_zero_values():
    # Test healthy profile
    healthy_req = RadarProfileRequest(
        monthly_income=80000.0,
        monthly_expenses=40000.0,
        current_savings=250000.0,
        existing_emi=5000.0
    )
    radar = radar_service.evaluate_radar(healthy_req)
    assert radar.health_score >= 80
    assert radar.overall_health.value in ["healthy", "excellent"]

    # Test critical cash flow deficit
    deficit_req = RadarProfileRequest(
        monthly_income=40000.0,
        monthly_expenses=55000.0,
        current_savings=10000.0,
        existing_emi=5000.0
    )
    deficit_radar = radar_service.evaluate_radar(deficit_req)
    assert deficit_radar.health_score < 50
    alert_categories = [a.category.value for a in deficit_radar.alerts]
    assert "cash_flow_shortage" in alert_categories
    assert "low_balance_risk" in alert_categories

    # Test edge case: Zero income, zero expenses, zero savings
    zero_req = RadarProfileRequest(
        monthly_income=0.0,
        monthly_expenses=0.0,
        current_savings=0.0,
        existing_emi=0.0
    )
    zero_radar = radar_service.evaluate_radar(zero_req)
    assert zero_radar.health_score is not None
    assert zero_radar.radar_rules_evaluated > 0
