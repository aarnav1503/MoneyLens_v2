import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight, ArrowDownRight, Sparkles, Upload, FileText } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { CashflowChart, HealthRadarChart, NetWorthChart } from "@/components/dashboard/charts";
import {
  currency,
  simulations,
} from "@/lib/dashboard-data";
import { useProfile, useSpending, useGoals, useStatementTransactions } from "@/hooks/use-money-lens";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({
    meta: [
      { title: "Overview — Money Lens" },
      {
        name: "description",
        content:
          "Money Lens shows your net worth, spending, goals and financial health in one calm, premium overview.",
      },
      { property: "og:title", content: "Overview — Money Lens" },
      {
        property: "og:description",
        content:
          "Understand your finances, analyse spending and simulate decisions with AI-powered insights.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

const toneText: Record<string, string> = {
  positive: "text-positive",
  info: "text-info",
  attention: "text-attention",
  risk: "text-risk",
};

const toneBg: Record<string, string> = {
  positive: "bg-positive-soft text-positive",
  info: "bg-info-soft text-info",
  attention: "bg-attention-soft text-attention",
  risk: "bg-risk-soft text-risk",
};

const toneBar: Record<string, string> = {
  positive: "bg-positive",
  info: "bg-info",
  attention: "bg-attention",
  risk: "bg-risk",
};

function Dashboard() {
  const { data: profile } = useProfile();
  const { data: spendingData } = useSpending();
  const { data: liveGoals } = useGoals();
  const { data: liveTransactions = [] } = useStatementTransactions();

  const userName = profile?.name || "User";
  // Net worth = Assets (Savings) - Liabilities (Loans)
  const netWorthValue = (profile?.current_savings || 0) - (profile?.active_loans || 0);
  const cashOnHandValue = profile?.current_savings || 0;
  const monthlySpendValue = spendingData?.total_spending || profile?.total_monthly_expenses || 0;
  const savingsRateValue = `${profile?.savings_rate_pct || 0}%`;

  const spendCategories = spendingData?.categories && spendingData.categories.length > 0
    ? spendingData.categories.filter((c) => c.total_amount > 0).map((c, i) => ({
        category: c.category,
        amount: c.total_amount,
        tone: `chart-${(i % 5) + 1}`,
      }))
    : [];

  const spendTotal = spendCategories.reduce((sum, s) => sum + s.amount, 0);

  const displayGoals = liveGoals && liveGoals.length > 0
    ? liveGoals.map((g) => ({
        name: g.title,
        current: g.current_savings_allocated || 0,
        target: g.target_amount,
        state: (g.current_savings_allocated / g.target_amount) >= 0.5 ? ("positive" as const) : ("info" as const),
      }))
    : [];

  const displayInsights = spendingData?.observations && spendingData.observations.length > 0
    ? spendingData.observations.map((obs) => ({
        tone: obs.type === "positive" ? ("positive" as const) : obs.type === "recurring" ? ("info" as const) : ("attention" as const),
        title: obs.title,
        body: obs.summary,
      }))
    : [];

  // Derive radar health dimensions
  const healthRadarData = [
    { axis: "Savings", score: Math.min(100, Math.round((profile?.savings_rate_pct || 0) * 4)) || 50 },
    { axis: "Spending", score: spendTotal > 0 ? (spendTotal < (profile?.monthly_income || 1) ? 80 : 45) : 50 },
    { axis: "Debt", score: profile?.active_emis === 0 ? 95 : 60 },
    { axis: "Liquidity", score: Math.min(100, Math.round((profile?.emergency_fund_runway_months || 0) * 16)) || 50 },
    { axis: "Growth", score: (profile?.monthly_investments || 0) > 0 ? 80 : 40 },
    { axis: "Protection", score: (profile?.emergency_fund_runway_months || 0) >= 3 ? 85 : 45 },
  ];

  return (
    <AppShell>
      {/* Headline */}
      <section>
        <p className="text-sm text-subtle-foreground">Live Telemetry · Deterministic Engine Connected</p>
        <h1 className="mt-2 font-display text-4xl md:text-5xl">Good evening, {userName}.</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          {spendTotal > 0 || (profile?.monthly_income || 0) > 0
            ? `Your uncommitted monthly surplus is ${currency(profile?.monthly_surplus || 0)}, baseline health score is ${profile?.health_score || 50}/100, and emergency runway covers ${profile?.emergency_fund_runway_months || 0} months.`
            : "Money Lens is running in real-data mode. Upload your bank statement in the Spending tab to view verified transactions, auto-categorized cashflow, and health metrics."}
        </p>
      </section>

      {/* Key numbers */}
      <section className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Net worth", value: currency(netWorthValue), change: (profile?.monthly_income || 0) > 0 ? "+3.3%" : "0.0%", up: true },
          { label: "Cash on hand", value: currency(cashOnHandValue), change: (profile?.current_savings || 0) > 0 ? "Current" : "Calibrate", up: true },
          { label: "Monthly spend", value: currency(monthlySpendValue), change: `${spendCategories.length} categories`, up: false },
          { label: "Savings rate", value: savingsRateValue, change: (profile?.monthly_income || 0) > 0 ? "Active" : "Uncalibrated", up: true },
        ].map((stat) => (
          <div key={stat.label} className="panel p-5">
            <p className="text-xs uppercase tracking-wide text-subtle-foreground">{stat.label}</p>
            <p className="numeric mt-3 text-2xl font-semibold">{stat.value}</p>
            <p
              className={cn(
                "mt-2 flex items-center gap-1 text-xs",
                stat.up ? "text-positive" : "text-muted-foreground",
              )}
            >
              {stat.up ? (
                <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={2} />
              ) : (
                <ArrowDownRight className="h-3.5 w-3.5" strokeWidth={2} />
              )}
              {stat.change}
            </p>
          </div>
        ))}
      </section>

      {/* Net worth + health */}
      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="panel p-6 lg:col-span-2">
          <div className="flex items-baseline justify-between">
            <div>
              <h2 className="text-sm font-medium">Net worth</h2>
              <p className="mt-1 text-xs text-subtle-foreground">Liquid assets + investments minus liabilities</p>
            </div>
            <p className="numeric text-lg font-semibold">{currency(netWorthValue)}</p>
          </div>
          <div className="mt-6">
            <NetWorthChart currentValue={netWorthValue} />
          </div>
        </div>

        <div className="panel p-6">
          <h2 className="text-sm font-medium">Financial health</h2>
          <p className="mt-1 text-xs text-subtle-foreground">Composite score {profile?.health_score || 50} / 100</p>
          <HealthRadarChart data={healthRadarData} />
        </div>
      </section>

      {/* Cashflow + spending */}
      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="panel p-6">
          <h2 className="text-sm font-medium">Income vs spending</h2>
          <p className="mt-1 text-xs text-subtle-foreground">
            Monthly surplus: {currency(profile?.monthly_surplus || 0)}
          </p>
          <div className="mt-6">
            <CashflowChart income={profile?.monthly_income || 0} spending={monthlySpendValue} />
          </div>
        </div>

        <div className="panel p-6">
          <h2 className="text-sm font-medium">Where it went</h2>
          <p className="mt-1 text-xs text-subtle-foreground">Current Cycle · {currency(spendTotal)}</p>
          {spendCategories.length > 0 ? (
            <ul className="mt-6 space-y-4">
              {spendCategories.map((row) => (
                <li key={row.category}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{row.category}</span>
                    <span className="numeric text-muted-foreground">{currency(row.amount)}</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${spendTotal > 0 ? (row.amount / spendTotal) * 100 : 0}%`,
                        backgroundColor: `var(--color-${row.tone})`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-8 text-center py-8 border border-dashed border-border rounded-xl">
              <Upload className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">No spending recorded yet.</p>
              <Link to="/spending" className="mt-2 inline-block text-xs text-primary font-medium hover:underline">
                Upload a Bank Statement &rarr;
              </Link>
            </div>
          )}
        </div>
      </section>

      {/* Insights */}
      {displayInsights.length > 0 && (
        <section className="mt-14">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" strokeWidth={1.75} />
            <h2 className="text-sm font-medium">Lens insights</h2>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-3">
            {displayInsights.map((item) => (
              <article key={item.title} className="panel p-5">
                <span
                  className={cn(
                    "inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium",
                    toneBg[item.tone],
                  )}
                >
                  {item.tone === "positive"
                    ? "On track"
                    : item.tone === "info"
                      ? "Opportunity"
                      : "Attention"}
                </span>
                <h3 className="mt-4 text-sm font-medium">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.body}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* Goals + simulations */}
      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="panel p-6">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-medium">Goals</h2>
            <Link to="/goals" className="text-xs text-primary hover:underline">Manage Goals</Link>
          </div>
          {displayGoals.length > 0 ? (
            <ul className="mt-6 space-y-6">
              {displayGoals.map((goal) => (
                <li key={goal.name}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{goal.name}</span>
                    <span className="numeric text-muted-foreground">
                      {currency(goal.current)} / {currency(goal.target)}
                    </span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className={cn("h-full rounded-full", toneBar[goal.state])}
                      style={{ width: `${goal.target > 0 ? Math.min(100, (goal.current / goal.target) * 100) : 0}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-xs text-muted-foreground py-4 text-center border border-dashed border-border rounded-xl">
              No financial goals configured. Add target reserves or purchase goals in the Goals tab.
            </p>
          )}
        </div>

        <div className="panel p-6">
          <h2 className="text-sm font-medium">Simulations</h2>
          <p className="mt-1 text-xs text-subtle-foreground">Modelled against active profile parameters</p>
          <ul className="mt-6 divide-y divide-border">
            {simulations.map((sim) => (
              <li key={sim.label} className="flex items-center justify-between gap-4 py-3.5">
                <span className="text-sm">{sim.label}</span>
                <span className={cn("numeric text-sm font-medium", toneText[sim.tone])}>
                  {sim.delta}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Recent statement transactions */}
      <section className="mt-6 panel p-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium">Recent statement activity</h2>
          <span className="text-xs text-subtle-foreground">{liveTransactions.length} transactions</span>
        </div>
        {liveTransactions.length > 0 ? (
          <ul className="mt-4 divide-y divide-border">
            {liveTransactions.slice(0, 10).map((tx) => (
              <li key={tx.id} className="flex items-center justify-between gap-4 py-3.5">
                <div>
                  <p className="text-sm font-medium">{tx.description}</p>
                  <p className="text-xs text-subtle-foreground">
                    {tx.category} · {tx.date}
                  </p>
                </div>
                <span
                  className={cn(
                    "numeric text-sm font-semibold",
                    tx.type === "credit" ? "text-positive" : "text-foreground",
                  )}
                >
                  {tx.type === "credit" ? "+" : "−"}
                  {currency(Math.abs(tx.amount), 2)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-4 py-8 text-center border border-dashed border-border rounded-xl">
            <FileText className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
            <p className="text-xs text-muted-foreground">No bank transactions ingested yet.</p>
            <p className="text-[11px] text-subtle-foreground mt-1">
              Upload a CSV or PDF statement in the Spending tab to view your parsed transaction feed.
            </p>
          </div>
        )}
      </section>
    </AppShell>
  );
}
