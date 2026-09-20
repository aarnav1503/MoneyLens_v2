import { useState, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { CashflowChart } from "@/components/dashboard/charts";
import { Badge, PageHeader, Panel } from "@/components/dashboard/ui";
import { currency } from "@/lib/dashboard-data";
import { useSpending, useProfile, useStatementTransactions, useUploadStatement, useConfirmObservation } from "@/hooks/use-money-lens";
import { cn } from "@/lib/utils";
import { Upload, Shield, CheckCircle2, AlertCircle, Lock, X, FileText, RefreshCw, Eye } from "lucide-react";
import type { StatementAnalysisSummary } from "@/lib/api-client";

export const Route = createFileRoute("/_authenticated/spending")({
  head: () => ({
    meta: [
      { title: "Spending & Statement Intelligence — Money Lens" },
      {
        name: "description",
        content:
          "See where every rupee went: categories, top merchants, subscriptions and the full transaction list.",
      },
      { property: "og:title", content: "Spending — Money Lens" },
      {
        property: "og:description",
        content: "Category breakdowns, merchant patterns and subscription creep, month by month.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SpendingPage,
});

function SpendingPage() {
  const { data: liveSpending } = useSpending();
  const { data: profile } = useProfile();
  const { data: liveTransactions = [] } = useStatementTransactions();
  const uploadMutation = useUploadStatement();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lastSummary, setLastSummary] = useState<StatementAnalysisSummary | null>(null);
  
  const confirmObservationMutation = useConfirmObservation();

  const categories = useMemo(() => {
    if (liveSpending?.categories && liveSpending.categories.length > 0) {
      return liveSpending.categories.filter((c) => c.total_amount > 0).map((c, i) => ({
        category: c.category,
        amount: c.total_amount,
        tone: `chart-${(i % 5) + 1}`,
        pct: c.percentage_of_total,
      }));
    }
    return [];
  }, [liveSpending]);

  const total = liveSpending?.total_spending || 0;
  const subsTotal = liveSpending?.recurring_total || 0;

  // Aggregate top merchants from real debit transactions
  const topMerchants = useMemo(() => {
    const debitTxs = liveTransactions.filter((t) => t.type === "debit");
    const merchantMap = new Map<string, { name: string; category: string; amount: number; visits: number }>();

    for (const tx of debitTxs) {
      const cleanName = tx.description.replace(/^UPI-|\/.*$/g, "").trim().slice(0, 32);
      const existing = merchantMap.get(cleanName);
      if (existing) {
        existing.amount += tx.amount;
        existing.visits += 1;
      } else {
        merchantMap.set(cleanName, {
          name: cleanName || "Unknown Merchant",
          category: tx.category,
          amount: tx.amount,
          visits: 1,
        });
      }
    }

    return Array.from(merchantMap.values())
      .sort((a, b) => b.amount - a.amount)
      .slice(0, 6);
  }, [liveTransactions]);

  // Aggregate recurring subscriptions from transactions
  const detectedSubscriptions = useMemo(() => {
    return liveTransactions.filter((t) => t.is_recurring || t.category === "Subscriptions");
  }, [liveTransactions]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadError(null);
      setUploadStatus(null);
      setIsPrivacyModalOpen(true);
    }
  };

  const handleProcessStatement = async (saveRaw: boolean) => {
    if (!selectedFile) return;
    setIsPrivacyModalOpen(false);
    setUploadStatus(null);
    setUploadError(null);

    try {
      const summary = await uploadMutation.mutateAsync({ file: selectedFile, saveRaw });
      setLastSummary(summary);
      setUploadStatus(`Statement "${selectedFile.name}" successfully parsed using ${summary.extraction_source === 'ocr' ? 'OCR Fallback' : 'Native Parsing'}.`);
    } catch (err: any) {
      setUploadError(err.message || "Failed to process statement. Please ensure it is a valid CSV or PDF bank statement.");
    } finally {
      setSelectedFile(null);
    }
  };

  const handleConfirmObservation = async (obs: any) => {
    try {
      await confirmObservationMutation.mutateAsync({
        type: obs.type,
        field: obs.field,
        value: obs.amount,
      });
      // Remove it from the list
      if (lastSummary && lastSummary.pending_observations) {
        setLastSummary({
          ...lastSummary,
          pending_observations: lastSummary.pending_observations.filter((o) => o !== obs),
        });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleDismissObservation = (obs: any) => {
    if (lastSummary && lastSummary.pending_observations) {
      setLastSummary({
        ...lastSummary,
        pending_observations: lastSummary.pending_observations.filter((o) => o !== obs),
      });
    }
  };

  return (
    <AppShell>
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-4">
        <PageHeader
          eyebrow="Spending Intelligence"
          title="Where the money went."
          description="Decomposed monthly outflows across 12 standard categories, recurring commitments, and real statement ingestion."
        />

        <label className="inline-flex items-center gap-2 self-start sm:self-auto rounded-lg bg-surface-elevated border border-border px-3.5 py-1.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors cursor-pointer shadow-xs">
          {uploadMutation.isPending ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary" />
          ) : (
            <Upload className="h-3.5 w-3.5" />
          )}
          <span>{uploadMutation.isPending ? "Analyzing..." : "Upload Statement"}</span>
          <input
            type="file"
            accept=".csv,.pdf,.txt"
            onChange={handleFileChange}
            disabled={uploadMutation.isPending}
            className="hidden"
          />
        </label>
      </div>

      {/* Upload Notification */}
      {uploadMutation.isPending && (
        <div className="mt-4 p-4 rounded-xl border border-primary/30 bg-primary-soft flex items-center gap-3 text-xs text-foreground animate-pulse">
          <div className="w-2.5 h-2.5 rounded-full bg-primary animate-ping" />
          <span>Ingesting statement, classifying transactions into standard categories, and synchronizing financial telemetry...</span>
        </div>
      )}

      {uploadStatus && (
        <div className="mt-4 p-4 rounded-xl border border-border bg-surface-muted flex items-center justify-between text-xs text-foreground">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-positive" />
            <span>{uploadStatus}</span>
          </div>
          <button onClick={() => setUploadStatus(null)} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Statement Review Panel */}
      {lastSummary && lastSummary.pending_observations && lastSummary.pending_observations.length > 0 && (
        <div className="mt-4 rounded-xl border border-primary/20 bg-background shadow-xs overflow-hidden">
          <div className="bg-primary/5 px-5 py-3 border-b border-primary/10 flex items-center gap-2">
            <Eye className="h-4 w-4 text-primary" />
            <h3 className="font-medium text-sm text-foreground">Statement Intelligence Review</h3>
          </div>
          <div className="p-5 space-y-4">
            <p className="text-xs text-muted-foreground leading-relaxed">
              We detected the following signals in your recent statement upload. Confirm these observations to update your central financial profile.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {lastSummary.pending_observations.map((obs, idx) => (
                <div key={idx} className="p-4 rounded-lg border border-border bg-surface-muted flex flex-col gap-3">
                  <div>
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-foreground">{obs.description}</h4>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-background text-muted-foreground border border-border">
                        {(obs.confidence * 100).toFixed(0)}% CONFIDENCE
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Current profile value: {currency(obs.current_value)}
                    </p>
                  </div>
                  
                  <div className="flex items-center justify-between mt-auto pt-2">
                    <span className="numeric text-lg font-bold text-primary">{currency(obs.amount)}</span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDismissObservation(obs)}
                        className="text-xs px-3 py-1.5 rounded-md hover:bg-background border border-transparent hover:border-border text-subtle-foreground hover:text-foreground transition-colors"
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={() => handleConfirmObservation(obs)}
                        disabled={confirmObservationMutation.isPending}
                        className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
                      >
                        Update Profile
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {uploadError && (
        <div className="mt-4 p-4 rounded-xl border border-risk/40 bg-risk-soft flex items-center justify-between text-xs text-risk">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>{uploadError}</span>
          </div>
          <button onClick={() => setUploadError(null)} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Privacy Consent Modal */}
      {isPrivacyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/20 backdrop-blur-xs">
          <div className="bg-surface-elevated rounded-2xl border border-border p-6 max-w-md w-full shadow-2xl space-y-5 animate-in fade-in">
            <div className="flex items-center gap-2 text-primary">
              <Lock className="h-5 w-5" />
              <h3 className="font-display text-lg">Statement Privacy Policy</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              How should Money Lens handle your statement file <span className="font-semibold text-foreground font-mono">{selectedFile?.name}</span>?
            </p>

            <div className="space-y-3">
              <button
                onClick={() => handleProcessStatement(false)}
                className="w-full text-left p-3.5 rounded-xl border-2 border-primary bg-primary-soft text-foreground hover:opacity-95 transition-opacity cursor-pointer"
              >
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span>DON&apos;T SAVE MY STATEMENT</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary text-primary-foreground">Recommended</span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Process in-memory, extract categorized analytics, then delete the raw document immediately.
                </p>
              </button>

              <button
                onClick={() => handleProcessStatement(true)}
                className="w-full text-left p-3.5 rounded-xl border border-border bg-background hover:bg-secondary transition-colors cursor-pointer"
              >
                <span className="text-xs font-semibold text-foreground">SAVE MY STATEMENT</span>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Securely retain raw statement for permitted historical comparisons.
                </p>
              </button>
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={() => {
                  setIsPrivacyModalOpen(false);
                  setSelectedFile(null);
                }}
                className="text-xs text-subtle-foreground hover:text-foreground cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <section className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Total spend", value: currency(total) },
          { label: "Essential Outflows", value: currency(liveSpending?.essential_total || 0) },
          { label: "Subscriptions & Recurring", value: `${currency(subsTotal)} / mo` },
          { label: "Categories tracked", value: `${categories.length}` },
        ].map((stat) => (
          <div key={stat.label} className="panel p-5">
            <p className="text-xs uppercase tracking-wide text-subtle-foreground">{stat.label}</p>
            <p className="numeric mt-3 text-2xl font-semibold">{stat.value}</p>
          </div>
        ))}
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <Panel title="Income vs spending" subtitle="Real-time statement synchronization">
          <div className="mt-6">
            <CashflowChart income={profile?.monthly_income || 0} spending={total} />
          </div>
        </Panel>

        <Panel title="By category" subtitle={`Current Cycle · ${currency(total)}`}>
          {categories.length > 0 ? (
            <ul className="mt-6 space-y-4">
              {categories.map((row) => (
                <li key={row.category}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span>{row.category}</span>
                    <span className="numeric text-muted-foreground">
                      {currency(row.amount)} · {row.pct}%
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${total > 0 ? (row.amount / total) * 100 : 0}%`,
                        backgroundColor: `var(--color-${row.tone})`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="py-8 text-center border border-dashed border-border rounded-xl mt-6">
              <Upload className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">No statement categories available yet.</p>
              <p className="text-[11px] text-subtle-foreground mt-1">Upload a CSV or PDF bank statement to decompose spending.</p>
            </div>
          )}
        </Panel>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <Panel title="Top merchants" subtitle="Ranked by statement transaction amount">
          {topMerchants.length > 0 ? (
            <ul className="mt-4 divide-y divide-border">
              {topMerchants.map((m) => (
                <li key={m.name} className="flex items-center justify-between gap-4 py-3.5">
                  <div>
                    <p className="text-sm font-medium">{m.name}</p>
                    <p className="text-xs text-subtle-foreground">
                      {m.category} · {m.visits} {m.visits === 1 ? "transaction" : "transactions"}
                    </p>
                  </div>
                  <span className="numeric text-sm font-semibold">{currency(m.amount)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl mt-4">
              No merchant transactions discovered yet.
            </p>
          )}
        </Panel>

        <Panel title="Subscriptions & recurring" subtitle={`${detectedSubscriptions.length} identified commitments`}>
          {detectedSubscriptions.length > 0 ? (
            <ul className="mt-4 divide-y divide-border">
              {detectedSubscriptions.slice(0, 6).map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-4 py-3.5">
                  <div>
                    <p className="text-sm font-medium">{s.description}</p>
                    <p className="text-xs text-subtle-foreground">
                      {s.category} · {s.date}
                    </p>
                  </div>
                  <span className="numeric text-sm font-semibold">{currency(s.amount)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl mt-4">
              No recurring subscriptions identified in current statements.
            </p>
          )}
        </Panel>
      </section>

      <section className="mt-6 panel p-6">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-medium">All statement transactions</h2>
          <span className="text-xs text-subtle-foreground">{liveTransactions.length} items</span>
        </div>
        {liveTransactions.length > 0 ? (
          <ul className="mt-4 divide-y divide-border">
            {liveTransactions.map((tx) => (
              <li key={tx.id} className="flex items-center justify-between gap-4 py-3.5">
                <div>
                  <p className="text-sm font-medium">{tx.description}</p>
                  <p className="text-xs text-subtle-foreground">
                    {tx.category} · {tx.date} {tx.is_essential ? "· Essential" : ""}
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
            <p className="text-xs text-muted-foreground">No transaction records uploaded.</p>
            <p className="text-[11px] text-subtle-foreground mt-1">
              Click &quot;Upload Statement&quot; above to import your bank statement CSV or PDF.
            </p>
          </div>
        )}
      </section>
    </AppShell>
  );
}
