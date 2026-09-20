import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Badge, PageHeader, Panel, Progress } from "@/components/dashboard/ui";
import { currency } from "@/lib/dashboard-data";
import { useGoals, useCreateGoal, useDeleteGoal } from "@/hooks/use-money-lens";
import { Plus, Trash2, X, Check } from "lucide-react";

export const Route = createFileRoute("/_authenticated/goals")({
  head: () => ({
    meta: [
      { title: "Goals — Money Lens" },
      {
        name: "description",
        content:
          "Track every savings goal: progress, monthly contribution, projected completion date and what would speed it up.",
      },
      { property: "og:title", content: "Goals — Money Lens" },
      {
        property: "og:description",
        content: "Progress, contributions and projected dates for each savings goal.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: GoalsPage,
});

function GoalsPage() {
  const { data: liveGoals } = useGoals();
  const createGoalMutation = useCreateGoal();
  const deleteGoalMutation = useDeleteGoal();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [targetAmount, setTargetAmount] = useState(500000);
  const [targetMonths, setTargetMonths] = useState(12);

  const displayGoals = liveGoals && liveGoals.length > 0
    ? liveGoals.map((g) => {
        const curr = g.current_savings_allocated || 0;
        const tgt = g.target_amount || 100000;
        const mos = g.target_months || 12;
        const monthlyContrib = Math.round((tgt - curr) / maxVal(1, mos));
        const pct = Math.round((curr / tgt) * 100);
        return {
          id: g.id,
          name: g.title,
          current: curr,
          target: tgt,
          monthly: monthlyContrib,
          monthsLeft: mos,
          state: pct >= 50 ? ("positive" as const) : pct >= 20 ? ("info" as const) : ("attention" as const),
          note: `Required sinking fund allocation: ${currency(monthlyContrib)}/month over ${mos} months.`,
          isLive: true,
        };
      })
    : [];

  const saved = displayGoals.reduce((s, g) => s + g.current, 0);
  const target = displayGoals.reduce((s, g) => s + g.target, 0);
  const monthly = displayGoals.reduce((s, g) => s + g.monthly, 0);

  const handleCreateGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    await createGoalMutation.mutateAsync({
      title: title.trim(),
      target_amount: Number(targetAmount),
      target_months: Number(targetMonths),
      current_savings_allocated: 0,
      category: "major_purchase",
    });
    setTitle("");
    setIsModalOpen(false);
  };

  return (
    <AppShell>
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4">
        <PageHeader
          eyebrow={`${displayGoals.length} active goals`}
          title="What you're saving toward."
          description={`You've put aside ${currency(saved)} of ${currency(target)} and are adding ${currency(monthly)} every month.`}
        />
        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center gap-2 self-start sm:self-auto rounded-lg bg-primary text-primary-foreground px-3.5 py-1.5 text-xs font-medium hover:opacity-90 transition-opacity cursor-pointer shadow-xs"
        >
          <Plus className="h-4 w-4" />
          <span>Add Goal</span>
        </button>
      </div>

      {/* Add Goal Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/20 backdrop-blur-xs">
          <div className="bg-surface-elevated rounded-2xl border border-border p-6 max-w-md w-full shadow-2xl space-y-5 animate-in fade-in">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-lg">Create New Savings Goal</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleCreateGoal} className="space-y-4">
              <div>
                <label className="text-xs text-subtle-foreground uppercase tracking-wide">Goal Name</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Electric Vehicle Down Payment"
                  className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium focus:outline-none focus:border-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-subtle-foreground uppercase tracking-wide">Target (₹)</label>
                  <input
                    type="number"
                    required
                    min={1000}
                    value={targetAmount}
                    onChange={(e) => setTargetAmount(Number(e.target.value))}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="text-xs text-subtle-foreground uppercase tracking-wide">Horizon (Months)</label>
                  <input
                    type="number"
                    required
                    min={1}
                    value={targetMonths}
                    onChange={(e) => setTargetMonths(Number(e.target.value))}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium numeric focus:outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="p-3 rounded-lg bg-surface-muted border border-border text-xs text-muted-foreground">
                Monthly required saving: <span className="numeric font-semibold text-foreground">{currency(Math.round(targetAmount / Math.max(1, targetMonths)))}/mo</span>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="rounded-lg border border-border px-3.5 py-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createGoalMutation.isPending}
                  className="rounded-lg bg-primary text-primary-foreground px-4 py-1.5 text-xs font-medium hover:opacity-90 cursor-pointer disabled:opacity-50"
                >
                  {createGoalMutation.isPending ? "Adding..." : "Confirm Goal"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <section className="mt-10 grid gap-4 sm:grid-cols-3">
        {[
          { label: "Saved so far", value: currency(saved) },
          { label: "Combined target", value: currency(target) },
          { label: "Monthly contribution", value: currency(monthly) },
        ].map((stat) => (
          <div key={stat.label} className="panel p-5">
            <p className="text-xs uppercase tracking-wide text-subtle-foreground">{stat.label}</p>
            <p className="numeric mt-3 text-2xl font-semibold">{stat.value}</p>
          </div>
        ))}
      </section>

      <section className="mt-6 space-y-4">
        {displayGoals.map((goal) => {
          const pct = Math.round((goal.current / goal.target) * 100);
          return (
            <div key={goal.id} className="panel p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="font-display text-2xl">{goal.name}</h2>
                  <p className="mt-1 text-xs text-subtle-foreground">
                    {currency(goal.monthly)} a month · {goal.monthsLeft} months horizon
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={goal.state}>
                    {goal.state === "positive"
                      ? "On track"
                      : goal.state === "info"
                        ? "Steady"
                        : "Behind plan"}
                  </Badge>
                  {goal.isLive && (
                    <button
                      onClick={() => deleteGoalMutation.mutate(goal.id)}
                      className="p-1.5 text-subtle-foreground hover:text-risk rounded-md transition-colors cursor-pointer"
                      title="Remove Goal"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-6 flex items-baseline justify-between text-sm">
                <span className="numeric font-medium">{currency(goal.current)}</span>
                <span className="numeric text-muted-foreground">
                  {pct}% of {currency(goal.target)}
                </span>
              </div>
              <div className="mt-2">
                <Progress value={pct} tone={goal.state} />
              </div>

              <p className="mt-5 text-sm leading-relaxed text-muted-foreground">{goal.note}</p>

              <div className="mt-5 grid gap-4 border-t border-border pt-5 sm:grid-cols-3">
                {[
                  { label: "Remaining", value: currency(Math.max(0, goal.target - goal.current)) },
                  {
                    label: "Months left",
                    value: `${goal.monthsLeft}`,
                  },
                  { label: "Required Monthly", value: currency(goal.monthly) },
                ].map((cell) => (
                  <div key={cell.label}>
                    <p className="text-xs uppercase tracking-wide text-subtle-foreground">
                      {cell.label}
                    </p>
                    <p className="numeric mt-1.5 text-sm font-medium">{cell.value}</p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        {displayGoals.length === 0 && (
          <div className="panel p-12 text-center text-muted-foreground">
            No goals set yet. Click "Add Goal" to get started!
          </div>
        )}
      </section>
    </AppShell>
  );
}

function maxVal(a: number, b: number) {
  return a > b ? a : b;
}
