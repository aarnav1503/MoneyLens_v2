"""
API Integration Tests using FastAPI TestClient.
Tests all canonical public API endpoints:
- GET /health
- GET /
- POST /api/v1/transactions & GET /api/v1/transactions & GET /api/v1/transactions/summary & DELETE
- POST /api/v1/simulate/position
- POST /api/v1/simulate/purchase
- POST /api/v1/simulate/emi
- POST /api/v1/simulate/savings
- POST /api/v1/goals & POST /api/v1/goals/reverse & GET /api/v1/goals/saved & POST /api/v1/goals/save & DELETE
- POST /api/v1/experiments/compare
- GET /api/v1/radar & POST /api/v1/radar/analyze
- Input Validation & Error Handling
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ai_integration_status"] == "ready"


def test_root_index_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_api_prefix"] == "/api/v1"
    assert any("/api/v1/simulate/emi" in ep for ep in data["available_endpoints"])


def test_transactions_endpoints():
    # 1. Create income and expense transactions
    create_payload = {
        "title": "Freelance Design Gig",
        "type": "income",
        "amount": 15000.0,
        "category": "Freelance",
        "transaction_date": "2026-09-15",
        "is_recurring": False,
        "recurring_frequency": "none",
        "description": "Mobile app UI consultation"
    }
    create_resp = client.post("/api/v1/transactions", json=create_payload)
    assert create_resp.status_code == 201
    created_txn = create_resp.json()
    assert created_txn["amount"] == 15000.0
    txn_id = created_txn["id"]

    expense_payload = {
        "title": "Groceries",
        "type": "expense",
        "amount": 3000.0,
        "category": "Food",
        "transaction_date": "2026-09-16",
        "is_recurring": False,
        "recurring_frequency": "none"
    }
    client.post("/api/v1/transactions", json=expense_payload)

    # 2. List transactions
    list_resp = client.get("/api/v1/transactions")
    assert list_resp.status_code == 200
    txns = list_resp.json()
    assert len(txns) >= 2

    # 3. Get summary
    summary_resp = client.get("/api/v1/transactions/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_income"] >= 15000.0
    assert summary["total_expenses"] >= 3000.0
    assert "category_wise_spending" in summary
    assert "recurring_summary" in summary

    # 4. Get by ID
    get_resp = client.get(f"/api/v1/transactions/{txn_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == txn_id

    # 5. Delete transaction
    del_resp = client.delete(f"/api/v1/transactions/{txn_id}")
    assert del_resp.status_code == 200

    # 6. Delete non-existent ID -> 404
    del_missing = client.delete("/api/v1/transactions/invalid_id_999")
    assert del_missing.status_code == 404


def test_simulate_position_endpoint():
    payload = {
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0,
        "existing_emi": 5000.0
    }
    resp = client.post("/api/v1/simulate/position", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["monthly_surplus"] == 30000.0
    assert data["savings_rate_pct"] == 37.5
    assert data["projected_balance_3_months"] == 290000.0
    assert data["projected_balance_6_months"] == 380000.0
    assert data["projected_balance_12_months"] == 560000.0


def test_simulate_purchase_endpoint():
    payload = {
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0,
        "purchase_amount": 70000.0,
        "existing_emi": 0.0,
        "duration_months": 12
    }
    resp = client.post("/api/v1/simulate/purchase", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["purchase_amount"] == 70000.0
    assert data["post_purchase_savings"] == 130000.0
    assert data["monthly_surplus"] == 35000.0
    assert data["post_purchase_projected_savings"]["3_months"] == 235000.0
    assert data["post_purchase_projected_savings"]["6_months"] == 340000.0
    assert data["post_purchase_projected_savings"]["12_months"] == 550000.0


def test_simulate_emi_endpoint():
    payload = {
        "purchase_amount": 70000.0,
        "down_payment": 10000.0,
        "annual_interest_rate_pct": 12.0,
        "tenure_months": 12,
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0,
        "existing_emi": 0.0
    }
    resp = client.post("/api/v1/simulate/emi", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["loan_amount"] == 60000.0
    assert data["monthly_emi"] > 5000.0
    assert data["total_interest"] > 0
    assert "3_months" in data["projected_savings"]


def test_simulate_savings_endpoint():
    payload = {
        "current_savings": 200000.0,
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "existing_emi": 0.0,
        "annual_return_pct": 8.0,
        "duration_months": 12
    }
    resp = client.post("/api/v1/simulate/savings", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["starting_savings"] == 200000.0
    assert len(data["monthly_trajectory"]) == 12


def test_goal_endpoints_and_crud():
    # 1. Forward Goal Calculation
    goal_payload = {
        "target_amount": 500000.0,
        "current_savings_allocated": 100000.0,
        "target_months": 12,
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "existing_emi": 0.0
    }
    resp = client.post("/api/v1/goals", json=goal_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["remaining_amount"] == 400000.0
    assert data["is_reachable"] is True

    # 2. Reverse Goal Calculation
    rev_payload = {
        "target_amount": 500000.0,
        "target_months": 12,
        "current_monthly_income": 80000.0,
        "current_monthly_expenses": 45000.0,
        "existing_emi": 0.0
    }
    rev_resp = client.post("/api/v1/goals/reverse", json=rev_payload)
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["required_monthly_saving"] > 0
    assert "actionable_levers" in rev_data

    # 3. Save Goal & List Saved
    save_resp = client.post("/api/v1/goals/save", json={
        "title": "New Car Down Payment",
        "target_amount": 200000.0,
        "current_savings_allocated": 50000.0,
        "target_months": 8
    })
    assert save_resp.status_code == 201
    saved_goal = save_resp.json()
    goal_id = saved_goal["id"]

    list_saved = client.get("/api/v1/goals/saved")
    assert list_saved.status_code == 200
    assert any(g["id"] == goal_id for g in list_saved.json())

    # 4. Delete Saved Goal
    del_goal = client.delete(f"/api/v1/goals/saved/{goal_id}")
    assert del_goal.status_code == 200


def test_experiment_compare_endpoint():
    payload = {
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0,
        "existing_emi": 0.0,
        "target_goal_amount": 500000.0,
        "target_goal_months": 12,
        "scenarios": [
            {
                "scenario_id": "sc_a",
                "scenario_name": "No Purchase",
                "scenario_type": "no_purchase"
            },
            {
                "scenario_id": "sc_b",
                "scenario_name": "Cash Purchase",
                "scenario_type": "cash_purchase",
                "purchase_amount": 70000.0
            }
        ]
    }
    resp = client.post("/api/v1/experiments/compare", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["comparison_matrix"]) == 2
    assert "summary_insights" in data


def test_radar_endpoints():
    # GET /api/v1/radar
    resp = client.get("/api/v1/radar")
    assert resp.status_code == 200
    data = resp.json()
    assert "health_score" in data
    assert "alerts" in data

    # POST /api/v1/radar/analyze (custom profile)
    custom_resp = client.post("/api/v1/radar/analyze", json={
        "monthly_income": 90000.0,
        "monthly_expenses": 30000.0,
        "current_savings": 300000.0,
        "existing_emi": 0.0
    })
    assert custom_resp.status_code == 200
    custom_data = custom_resp.json()
    assert custom_data["health_score"] >= 80


def test_input_validation_errors():
    # Negative income on position simulation -> 422 Unprocessable Entity
    resp = client.post("/api/v1/simulate/position", json={
        "monthly_income": -5000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0
    })
    assert resp.status_code == 422

    # Zero purchase amount on purchase simulation (requires gt=0) -> 422
    resp_purchase = client.post("/api/v1/simulate/purchase", json={
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0,
        "purchase_amount": 0.0
    })
    assert resp_purchase.status_code == 422

    # Invalid tenure (tenure <= 0) on EMI simulation -> 422
    resp_emi = client.post("/api/v1/simulate/emi", json={
        "purchase_amount": 70000.0,
        "annual_interest_rate_pct": 12.0,
        "tenure_months": 0,
        "monthly_income": 80000.0,
        "monthly_expenses": 45000.0,
        "current_savings": 200000.0
    })
    assert resp_emi.status_code == 422
