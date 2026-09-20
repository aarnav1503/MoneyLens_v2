"""
Financial Radar Service.
Deterministic rule-based anomaly detection, liquidity warnings, and health assessment.
"""

from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.services.transaction_service import transaction_repository
from app.schemas.common import SeverityLevel, HealthStatus
from app.schemas.radar import (
    RadarAlert,
    AlertCategory,
    RadarProfileRequest,
    FinancialRadarResponse
)
from app.utils.calculations import calculate_monthly_surplus, calculate_savings_rate


class RadarService:
    """Rule-based Financial Radar detection engine."""

    @staticmethod
    def evaluate_radar(
        profile: Optional[RadarProfileRequest] = None,
        user_id: Optional[str] = None
    ) -> FinancialRadarResponse:
        effective_user_id = user_id or "default"
        try:
            summary = transaction_repository.get_summary(effective_user_id)
            all_txns = transaction_repository.get_all(user_id=effective_user_id)
        except Exception:
            summary = None
            all_txns = []

        # Determine baseline numbers (either from profile request override or from recorded transactions)
        est_income = summary.monthly_estimated_income if summary and summary.monthly_estimated_income > 0 else 80000.0
        est_expenses = summary.monthly_estimated_expenses if summary and summary.monthly_estimated_expenses > 0 else 45000.0

        monthly_income = (profile.monthly_income if profile and profile.monthly_income is not None else est_income)
        monthly_expenses = (profile.monthly_expenses if profile and profile.monthly_expenses is not None else est_expenses)
        existing_emi = (profile.existing_emi if profile and profile.existing_emi is not None else 0.0)
        current_savings = (profile.current_savings if profile and profile.current_savings is not None else 200000.0)

        monthly_surplus = calculate_monthly_surplus(monthly_income, monthly_expenses, existing_emi)
        savings_rate = calculate_savings_rate(monthly_income, monthly_surplus)
        
        if monthly_expenses > 0:
            emergency_months = round(current_savings / monthly_expenses, 2)
        else:
            emergency_months = 999.0 if current_savings > 0 else 0.0

        if monthly_income > 0:
            debt_to_income_pct = round((existing_emi / monthly_income * 100), 2)
        else:
            debt_to_income_pct = 100.0 if existing_emi > 0 else 0.0

        alerts: List[RadarAlert] = []
        rules_evaluated = 0
        health_penalties = 0

        # Rule 1: Cash Flow Shortage Check
        rules_evaluated += 1
        if monthly_surplus < 0:
            health_penalties += 40
            alerts.append(RadarAlert(
                id="radar_cashflow_critical",
                category=AlertCategory.CASH_FLOW_SHORTAGE,
                severity=SeverityLevel.CRITICAL,
                title="Negative Monthly Cash Flow Deficit",
                message=f"Monthly outflows exceed income by ₹{abs(monthly_surplus):,.2f} per month.",
                metric_value=monthly_surplus,
                threshold_value=0.0,
                trigger_rule="Monthly Surplus < ₹0",
                impact="Depleting accumulated savings every month; risk of overdraft or debt spiral."
            ))
        elif monthly_income > 0 and monthly_surplus < (monthly_income * 0.10):
            health_penalties += 20
            alerts.append(RadarAlert(
                id="radar_cashflow_tight",
                category=AlertCategory.CASH_FLOW_SHORTAGE,
                severity=SeverityLevel.WARNING,
                title="Tight Cash Flow Cushion",
                message=f"Monthly surplus of ₹{monthly_surplus:,.2f} is under 10% of income ({savings_rate:.1f}%).",
                metric_value=savings_rate,
                threshold_value=10.0,
                trigger_rule="Savings Rate < 10%",
                impact="Limited buffer against minor unexpected monthly expenses."
            ))

        # Rule 2: Emergency Fund / Low Balance Runway Check
        rules_evaluated += 1
        if emergency_months < settings.CRITICAL_EMERGENCY_FUND_MONTHS:
            health_penalties += 35
            alerts.append(RadarAlert(
                id="radar_emergency_critical",
                category=AlertCategory.LOW_BALANCE_RISK,
                severity=SeverityLevel.CRITICAL,
                title="Critical Emergency Fund Shortage",
                message=f"Liquid savings (₹{current_savings:,.2f}) cover only {emergency_months:.1f} months of expenses.",
                metric_value=emergency_months,
                threshold_value=float(settings.CRITICAL_EMERGENCY_FUND_MONTHS),
                trigger_rule=f"Emergency Runway < {settings.CRITICAL_EMERGENCY_FUND_MONTHS} month",
                impact="High vulnerability to sudden income disruption or medical emergency."
            ))
        elif emergency_months < settings.DEFAULT_EMERGENCY_FUND_MONTHS:
            health_penalties += 15
            alerts.append(RadarAlert(
                id="radar_emergency_warning",
                category=AlertCategory.LOW_BALANCE_RISK,
                severity=SeverityLevel.WARNING,
                title="Sub-Optimal Emergency Fund Coverage",
                message=f"Current savings provide {emergency_months:.1f} months of runway (recommended: 3+ months).",
                metric_value=emergency_months,
                threshold_value=float(settings.DEFAULT_EMERGENCY_FUND_MONTHS),
                trigger_rule=f"Emergency Runway < {settings.DEFAULT_EMERGENCY_FUND_MONTHS} months",
                impact=f"Recommend building liquid buffer up to at least ₹{round(monthly_expenses * 3, 2):,.2f}."
            ))

        # Rule 3: Debt Burden / DTI Check
        rules_evaluated += 1
        if debt_to_income_pct > settings.HIGH_DEBT_TO_INCOME_PCT:
            health_penalties += 25
            alerts.append(RadarAlert(
                id="radar_debt_high",
                category=AlertCategory.DEBT_BURDEN_RISK,
                severity=SeverityLevel.WARNING,
                title="High Debt-to-Income (DTI) Ratio",
                message=f"Existing EMI obligations consume {debt_to_income_pct:.1f}% of monthly income.",
                metric_value=debt_to_income_pct,
                threshold_value=settings.HIGH_DEBT_TO_INCOME_PCT,
                trigger_rule=f"Total EMI > {settings.HIGH_DEBT_TO_INCOME_PCT}% of Income",
                impact="Constrains financial flexibility and increases default vulnerability."
            ))

        # Rule 4: Upcoming Recurring Commitments Check
        rules_evaluated += 1
        recurring_exp = summary.recurring_summary.total_recurring_expenses if summary else 0.0
        recurring_items_count = summary.recurring_summary.recurring_items_count if summary else 0
        recurring_ratio_pct = round((recurring_exp / monthly_income * 100), 2) if monthly_income > 0 else (100.0 if recurring_exp > 0 else 0.0)
        if recurring_ratio_pct > 50.0:
            health_penalties += 15
            alerts.append(RadarAlert(
                id="radar_recurring_high",
                category=AlertCategory.RECURRING_EXPENSE,
                severity=SeverityLevel.WARNING,
                title="High Fixed Recurring Obligations",
                message=f"Fixed recurring expenses total ₹{recurring_exp:,.2f} ({recurring_ratio_pct:.1f}% of income).",
                metric_value=recurring_ratio_pct,
                threshold_value=50.0,
                trigger_rule="Recurring Fixed Expenses > 50% of Income",
                impact="Leaves less than half of monthly income for variable expenses and investments."
            ))
        else:
            alerts.append(RadarAlert(
                id="radar_recurring_info",
                category=AlertCategory.RECURRING_EXPENSE,
                severity=SeverityLevel.INFO,
                title="Tracked Recurring Commitments",
                message=f"{recurring_items_count} recurring items totaling ₹{recurring_exp:,.2f}/month.",
                metric_value=recurring_exp,
                threshold_value=monthly_income * 0.5 if monthly_income > 0 else 0.0,
                trigger_rule="Fixed commitments within healthy range (<= 50%)",
                impact="Healthy ratio of recurring commitments."
            ))

        # Rule 5: Unusually High Expense Anomaly Detection
        rules_evaluated += 1
        if monthly_income > 0:
            high_threshold = monthly_income * settings.HIGH_EXPENSE_INCOME_RATIO
            for txn in all_txns:
                if txn.type.value == "expense" and txn.amount > high_threshold:
                    pct_share = round((txn.amount / monthly_income) * 100, 1)
                    alerts.append(RadarAlert(
                        id=f"radar_spike_{txn.id}",
                        category=AlertCategory.HIGH_EXPENSE_ANOMALY,
                        severity=SeverityLevel.WARNING,
                        title=f"Unusually High Expense: {txn.title}",
                        message=f"Expense of ₹{txn.amount:,.2f} in '{txn.category}' exceeds 35% of monthly income.",
                        metric_value=txn.amount,
                        threshold_value=round(high_threshold, 2),
                        trigger_rule="Single expense > 35% of Monthly Income",
                        impact=f"Single-handedly accounts for {pct_share}% of monthly income."
                    ))

        # Deterministic 0-100 Health Score
        health_score = max(5, min(100, 100 - health_penalties))
        
        if health_score >= 80:
            overall_health = HealthStatus.EXCELLENT
        elif health_score >= 60:
            overall_health = HealthStatus.HEALTHY
        elif health_score >= 40:
            overall_health = HealthStatus.VULNERABLE
        else:
            overall_health = HealthStatus.AT_RISK

        return FinancialRadarResponse(
            overall_health=overall_health,
            health_score=health_score,
            total_alerts=len(alerts),
            alerts=alerts,
            metrics_summary={
                "monthly_income": round(monthly_income, 2),
                "monthly_expenses": round(monthly_expenses, 2),
                "monthly_surplus": monthly_surplus,
                "savings_rate_pct": savings_rate,
                "current_savings": round(current_savings, 2),
                "emergency_fund_months": emergency_months,
                "debt_to_income_pct": debt_to_income_pct,
                "recurring_expense_ratio_pct": recurring_ratio_pct
            },
            radar_rules_evaluated=rules_evaluated,
            assumptions=[
                "Rule checks evaluated on current cash flow and historical transaction thresholds",
                "Emergency fund baseline targeted at 3.0 months of living expenses",
                "High expense anomaly threshold calibrated to 35.0% of monthly income"
            ]
        )


radar_service = RadarService()
