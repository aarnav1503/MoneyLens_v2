import { useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { NetWorthChart } from "@/components/dashboard/charts";
import { Badge, PageHeader, Panel } from "@/components/dashboard/ui";
import { accounts as mockAccounts, currency } from "@/lib/dashboard-data";
import { useProfile, useUpdateProfile } from "@/hooks/use-money-lens";
import { cn } from "@/lib/utils";
import { Check, Edit2, ShieldCheck, X } from "lucide-react";

export const Route = createFileRoute("/_authenticated/accounts")({
  head: () => ({
    meta: [
      { title: "Accounts & Financial Profile — Money Lens" },
      {
        name: "description",
        content:
          "Every account in one place: cash, investments, credit and debt, with balances and monthly movement.",
      },
      { property: "og:title", content: "Accounts — Money Lens" },
      {
        property: "og:description",
        content: "Cash, investments, credit and debt balances with net worth over time.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AccountsPage,
});

const groups = ["Cash", "Investments", "Credit", "Debt"] as const;

function AccountsPage() {
  const { data: profile } = useProfile();
  const updateProfileMutation = useUpdateProfile();
  const [isEditing, setIsEditing] = useState(false);

  const [income, setIncome] = useState(profile?.monthly_income || 0);
  const [essential, setEssential] = useState(profile?.essential_expenses || 0);
  const [discretionary, setDiscretionary] = useState(profile?.discretionary_expenses || 0);
  const [savings, setSavings] = useState(profile?.current_savings || 0);
  const [investments, setInvestments] = useState(profile?.monthly_investments || 0);
  const [emis, setEmis] = useState(profile?.active_emis || 0);
  const [loans, setLoans] = useState(profile?.active_loans || 0);

  // Sync form state when profile data arrives
  useEffect(() => {
    if (profile) {
      setIncome(profile.monthly_income || 0);
      setEssential(profile.essential_expenses || 0);
      setDiscretionary(profile.discretionary_expenses || 0);
      setSavings(profile.current_savings || 0);
      setInvestments(profile.monthly_investments || 0);
      setEmis(profile.active_emis || 0);
      setLoans(profile.active_loans || 0);
    }
  }, [profile]);


  const assets = (profile?.current_savings || 0) + (profile?.monthly_investments || 0) * 12;
  const liabilities = profile?.active_loans || 0;
  const net = assets - liabilities;

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateProfileMutation.mutateAsync({
      monthly_income: Number(income),
      essential_expenses: Number(essential),
      discretionary_expenses: Number(discretionary),
      current_savings: Number(savings),
      monthly_investments: Number(investments),
      active_emis: Number(emis),
      active_loans: Number(loans),
    });
    setIsEditing(false);
  };

  return (
    <AppShell>
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4">
        <PageHeader
          eyebrow="Deterministic Financial Profile"
          title="Everything you own and owe."
          description="Balances and baseline cashflow parameters powering the Money Lens financial engine."
        />
        <button
          onClick={() => {
            if (profile) {
              setIncome(profile.monthly_income);
              setEssential(profile.essential_expenses);
              setDiscretionary(profile.discretionary_expenses);
              setSavings(profile.current_savings);
              setInvestments(profile.monthly_investments);
              setEmis(profile.active_emis);
              setLoans(profile.active_loans);
            }
            setIsEditing(!isEditing);
          }}
          className="inline-flex items-center gap-2 self-start sm:self-auto rounded-lg border border-border bg-surface-elevated px-3 py-1.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors cursor-pointer"
        >
          <Edit2 className="h-3.5 w-3.5" />
          <span>{isEditing ? "Cancel Edit" : "Calibrate Profile"}</span>
        </button>
      </div>

      {/* Edit Profile Panel */}
      {isEditing && (
        <form onSubmit={handleSaveProfile} className="mt-6 panel p-6 border-primary/30 space-y-6 animate-in fade-in">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">Calibrate Baseline Parameters</h2>
            <span className="text-xs text-subtle-foreground font-mono">Backend Synchronization Active</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Monthly Net Income</label>
              <input
                type="number"
                value={income}
                onChange={(e) => setIncome(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Essential Expenses</label>
              <input
                type="number"
                value={essential}
                onChange={(e) => setEssential(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Discretionary Expenses</label>
              <input
                type="number"
                value={discretionary}
                onChange={(e) => setDiscretionary(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Liquid Savings Buffer</label>
              <input
                type="number"
                value={savings}
                onChange={(e) => setSavings(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Monthly Investments (SIP)</label>
              <input
                type="number"
                value={investments}
                onChange={(e) => setInvestments(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Active Monthly EMIs</label>
              <input
                type="number"
                value={emis}
                onChange={(e) => setEmis(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label className="text-xs text-subtle-foreground uppercase tracking-wide">Outstanding Loan Principal</label>
              <input
                type="number"
                value={loans}
                onChange={(e) => setLoans(Number(e.target.value))}
                className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
              />
            </div>

            <div className="flex items-end">
              <button
                type="submit"
                disabled={updateProfileMutation.isPending}
                className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                <span>{updateProfileMutation.isPending ? "Saving..." : "Save Baseline"}</span>
              </button>
            </div>
          </div>
        </form>
      )}

      <section className="mt-10 grid gap-4 sm:grid-cols-3">
        {[
          { label: "Assets", value: currency(assets), tone: "text-positive" },
          { label: "Liabilities", value: currency(Math.abs(liabilities)), tone: "text-risk" },
          { label: "Net worth", value: currency(net), tone: "text-foreground" },
        ].map((stat) => (
          <div key={stat.label} className="panel p-5">
            <p className="text-xs uppercase tracking-wide text-subtle-foreground">{stat.label}</p>
            <p className={cn("numeric mt-3 text-2xl font-semibold", stat.tone)}>{stat.value}</p>
          </div>
        ))}
      </section>

      <Panel title="Net worth" subtitle="Current assets minus liabilities" className="mt-6">
        <div className="mt-6">
          <NetWorthChart currentValue={net} />
        </div>
      </Panel>

      <section className="mt-6 space-y-4">
        {groups.map((group) => {
          const rows = mockAccounts.filter((a) => a.type === group);
          if (rows.length === 0) return null;
          const subtotal = rows.reduce((s, a) => s + a.balance, 0);
          return (
            <Panel key={group} title={group} subtitle={`${rows.length} accounts`}>
              <ul className="mt-4 divide-y divide-border">
                {rows.map((a) => (
                  <li key={a.name} className="flex items-center justify-between gap-4 py-3.5">
                    <div>
                      <p className="text-sm">{a.name}</p>
                      <p className="text-xs text-subtle-foreground">{a.institution}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <Badge tone={a.tone}>
                        {a.change > 0 ? "+" : "−"}
                        {Math.abs(a.change)}%
                      </Badge>
                      <span
                        className={cn(
                          "numeric w-28 text-right text-sm font-medium",
                          a.balance < 0 && "text-risk",
                        )}
                      >
                        {a.balance < 0 ? "−" : ""}
                        {currency(Math.abs(a.balance))}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex items-center justify-between border-t border-border pt-4 text-sm">
                <span className="text-muted-foreground">Subtotal</span>
                <span className={cn("numeric font-medium", subtotal < 0 && "text-risk")}>
                  {subtotal < 0 ? "−" : ""}
                  {currency(Math.abs(subtotal))}
                </span>
              </div>
            </Panel>
          );
        })}
      </section>
    </AppShell>
  );
}
