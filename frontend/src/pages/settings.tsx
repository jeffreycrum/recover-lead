import { useState, useEffect } from "react";
import { UserProfile } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSubscription } from "@/hooks/use-subscription";
import { api } from "@/lib/api";
import { EyebrowTag, MonoCell, ProductCard } from "@/components/landing-chrome";

const PLANS = [
  { name: "Free", price: "$0", qualifications: 15, letters: 10, skipTraces: 0 },
  { name: "Starter", price: "$79/mo", qualifications: 200, letters: 100, skipTraces: 25, plan: "starter" },
  { name: "Pro", price: "$199/mo", qualifications: "1,000", letters: 500, skipTraces: 100, plan: "pro" },
  { name: "Agency", price: "$499/mo", qualifications: "5,000", letters: "2,000", skipTraces: 500, plan: "agency" },
];

const primaryButtonClass =
  "inline-flex items-center justify-center rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]";
const secondaryButtonClass =
  "inline-flex items-center justify-center rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)]";
const inputClass =
  "rounded-[14px] border border-[var(--lt-line)] bg-[rgba(7,11,21,0.75)] px-3 py-2 text-sm text-[var(--lt-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.02)] focus:outline-none focus:ring-2 focus:ring-[rgba(16,185,129,0.3)]";

export function SettingsPage() {
  const { data: sub } = useSubscription();
  const qc = useQueryClient();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  const [alertEnabled, setAlertEnabled] = useState(true);
  const [minAmount, setMinAmount] = useState("");

  useEffect(() => {
    if (me?.user) {
      setAlertEnabled(me.user.alert_enabled ?? true);
      setMinAmount(me.user.min_alert_amount?.toString() || "");
    }
  }, [me]);

  const prefMutation = useMutation({
    mutationFn: (data: { alert_enabled?: boolean; min_alert_amount?: number | null }) =>
      api.updatePreferences(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });

  const handleUpgrade = async (plan: string) => {
    const { checkout_url } = await api.createCheckout(plan);
    window.location.href = checkout_url;
  };

  const handleManageBilling = async () => {
    const { portal_url } = await api.getBillingPortal();
    window.location.href = portal_url;
  };

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <EyebrowTag>Account controls</EyebrowTag>
        <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
          Settings
        </h1>
        <p className="mt-2 text-[var(--lt-text-muted)]">Manage your account, alerts, and subscription</p>
      </div>

      {/* Current plan & usage */}
      {sub && (
        <ProductCard heading="Current plan" subtitle="Usage and billing state">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className="rounded-full border border-[rgba(16,185,129,0.2)] bg-[var(--lt-emerald-dim)] px-3 py-1 text-sm font-semibold uppercase tracking-[0.12em] text-[var(--lt-emerald)]">
              {sub.plan}
            </span>
            <span className="text-sm capitalize text-[var(--lt-text-muted)]">{sub.status}</span>
          </div>

          {sub.usage && (
            <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-[18px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] p-4">
                <p className="text-sm text-[var(--lt-text-muted)]">Qualifications</p>
                <MonoCell className="mt-2">
                  {sub.usage.qualifications_used} / {sub.usage.qualifications_limit}
                </MonoCell>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-[rgba(148,163,184,0.12)]">
                  <div
                    className={`h-full rounded-full ${
                      sub.usage.qualifications_pct >= 90 ? "bg-[#ef4444]" :
                      sub.usage.qualifications_pct >= 80 ? "bg-[#f59e0b]" : "bg-[var(--lt-emerald)]"
                    }`}
                    style={{ width: `${Math.min(100, sub.usage.qualifications_pct)}%` }}
                  />
                </div>
              </div>
              <div className="rounded-[18px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] p-4">
                <p className="text-sm text-[var(--lt-text-muted)]">Letters</p>
                <MonoCell className="mt-2">
                  {sub.usage.letters_used} / {sub.usage.letters_limit}
                </MonoCell>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-[rgba(148,163,184,0.12)]">
                  <div
                    className={`h-full rounded-full ${
                      sub.usage.letters_pct >= 90 ? "bg-[#ef4444]" :
                      sub.usage.letters_pct >= 80 ? "bg-[#f59e0b]" : "bg-[var(--lt-emerald)]"
                    }`}
                    style={{ width: `${Math.min(100, sub.usage.letters_pct)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {sub.usage && sub.usage.overage_cost_estimate > 0 && sub.plan !== "free" && (
            <div className="mt-3 rounded-[18px] border border-[rgba(59,130,246,0.18)] bg-[var(--lt-blue-dim)] p-3 text-sm text-[#bfdbfe]">
              Estimated overage charges this period:{" "}
              <span className="font-semibold">
                ${sub.usage.overage_cost_estimate.toFixed(2)}
              </span>
              {sub.usage.qualifications_overage > 0 && (
                <span className="ml-1">
                  ({sub.usage.qualifications_overage} extra qualification{sub.usage.qualifications_overage !== 1 ? "s" : ""})
                </span>
              )}
              {sub.usage.letters_overage > 0 && (
                <span className="ml-1">
                  ({sub.usage.letters_overage} extra letter{sub.usage.letters_overage !== 1 ? "s" : ""})
                </span>
              )}
            </div>
          )}

          {sub.plan !== "free" && (
            <button
              onClick={handleManageBilling}
              className={`${secondaryButtonClass} mt-4`}
            >
              Manage billing
            </button>
          )}
        </ProductCard>
      )}

      {/* Email Alerts */}
      <ProductCard heading="Email alerts" subtitle="Daily lead thresholds">
        <p className="mb-4 text-sm text-[var(--lt-text-muted)]">
          Get daily emails about new high-value leads in your counties.
        </p>
        <div className="space-y-4">
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={alertEnabled}
              onChange={(e) => {
                setAlertEnabled(e.target.checked);
                prefMutation.mutate({ alert_enabled: e.target.checked });
              }}
              className="h-4 w-4 rounded border-[var(--lt-line)] bg-[var(--lt-surface)]"
            />
            <span className="text-sm text-[var(--lt-text)]">Enable daily lead alerts</span>
          </label>
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--lt-text)]">
              Minimum surplus amount
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--lt-text-muted)]">$</span>
              <input
                type="number"
                min="0"
                step="1000"
                value={minAmount}
                onChange={(e) => setMinAmount(e.target.value)}
                onBlur={() => {
                  const val = minAmount ? parseFloat(minAmount) : null;
                  prefMutation.mutate({ min_alert_amount: val });
                }}
                placeholder="5000"
                className={`${inputClass} w-40`}
              />
            </div>
            <p className="mt-1 text-xs text-[var(--lt-text-muted)]">
              Only alert for leads above this amount (default: $5,000)
            </p>
          </div>
        </div>
      </ProductCard>

      {/* Plan comparison */}
      <section>
        <h2 className="text-lg font-semibold text-[var(--lt-text)]">Plans</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {PLANS.map((plan) => (
            <ProductCard
              key={plan.name}
              heading={plan.name}
              className={`${
                sub?.plan === (plan.plan || "free")
                  ? "border-[rgba(16,185,129,0.32)] shadow-[0_40px_80px_-30px_rgba(0,0,0,0.8),0_0_0_1px_rgba(16,185,129,0.18)_inset,0_-1px_0_rgba(255,255,255,0.02)_inset]"
                  : ""
              }`}
            >
              <MonoCell size="lg" tone="emerald">{plan.price}</MonoCell>
              <ul className="mt-4 space-y-1 text-sm text-[var(--lt-text-muted)]">
                <li>{plan.qualifications} qualifications</li>
                <li>{plan.letters} letters</li>
                <li>{plan.skipTraces} skip traces</li>
                <li>All FL counties</li>
              </ul>
              {plan.plan && sub?.plan !== plan.plan && (
                <button
                  onClick={() => handleUpgrade(plan.plan!)}
                  className={`${primaryButtonClass} mt-4 w-full`}
                >
                  Upgrade
                </button>
              )}
              {sub?.plan === (plan.plan || "free") && (
                <p className="mt-4 text-center text-sm font-medium text-[var(--lt-emerald)]">Current plan</p>
              )}
            </ProductCard>
          ))}
        </div>
      </section>

      {/* Profile */}
      <ProductCard heading="Profile" subtitle="Clerk account controls">
        <div className="overflow-hidden rounded-[18px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] p-2">
          <UserProfile />
        </div>
      </ProductCard>
    </div>
  );
}
