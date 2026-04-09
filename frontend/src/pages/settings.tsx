import { useState, useEffect } from "react";
import { UserProfile } from "@clerk/clerk-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSubscription } from "@/hooks/use-subscription";
import { api } from "@/lib/api";

const PLANS = [
  { name: "Free", price: "$0", qualifications: 15, letters: 10, skipTraces: 0 },
  { name: "Starter", price: "$79/mo", qualifications: 200, letters: 100, skipTraces: 25, plan: "starter" },
  { name: "Pro", price: "$199/mo", qualifications: "1,000", letters: 500, skipTraces: 100, plan: "pro" },
  { name: "Agency", price: "$499/mo", qualifications: "5,000", letters: "2,000", skipTraces: 500, plan: "agency" },
];

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
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your account and subscription</p>
      </div>

      {/* Current plan & usage */}
      {sub && (
        <section className="p-6 bg-white rounded-lg border">
          <h2 className="text-lg font-semibold mb-4">Current Plan</h2>
          <div className="flex items-center gap-3 mb-4">
            <span className="px-3 py-1 rounded bg-emerald/10 text-emerald font-medium text-sm uppercase">
              {sub.plan}
            </span>
            <span className="text-sm text-muted-foreground capitalize">{sub.status}</span>
          </div>

          {sub.usage && (
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-sm text-muted-foreground">Qualifications</p>
                <p className="font-medium">
                  {sub.usage.qualifications_used} / {sub.usage.qualifications_limit}
                </p>
                <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      sub.usage.qualifications_pct >= 90 ? "bg-red-500" :
                      sub.usage.qualifications_pct >= 80 ? "bg-amber-500" : "bg-emerald"
                    }`}
                    style={{ width: `${Math.min(100, sub.usage.qualifications_pct)}%` }}
                  />
                </div>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Letters</p>
                <p className="font-medium">
                  {sub.usage.letters_used} / {sub.usage.letters_limit}
                </p>
                <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      sub.usage.letters_pct >= 90 ? "bg-red-500" :
                      sub.usage.letters_pct >= 80 ? "bg-amber-500" : "bg-emerald"
                    }`}
                    style={{ width: `${Math.min(100, sub.usage.letters_pct)}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {sub.usage && sub.usage.overage_cost_estimate > 0 && sub.plan !== "free" && (
            <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
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
              className="text-sm text-emerald hover:underline mt-3"
            >
              Manage billing
            </button>
          )}
        </section>
      )}

      {/* Email Alerts */}
      <section className="p-6 bg-white rounded-lg border">
        <h2 className="text-lg font-semibold mb-4">Email Alerts</h2>
        <p className="text-sm text-muted-foreground mb-4">
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
              className="w-4 h-4 rounded border-gray-300 text-emerald focus:ring-emerald"
            />
            <span className="text-sm">Enable daily lead alerts</span>
          </label>
          <div>
            <label className="block text-sm font-medium mb-1">
              Minimum surplus amount
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">$</span>
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
                className="w-40 px-3 py-1.5 border rounded-md text-sm"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Only alert for leads above this amount (default: $5,000)
            </p>
          </div>
        </div>
      </section>

      {/* Plan comparison */}
      <section>
        <h2 className="text-lg font-semibold mb-4">Plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`p-4 bg-white rounded-lg border ${
                sub?.plan === (plan.plan || "free") ? "border-emerald ring-1 ring-emerald" : ""
              }`}
            >
              <h3 className="font-semibold">{plan.name}</h3>
              <p className="text-2xl font-bold mt-1">{plan.price}</p>
              <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                <li>{plan.qualifications} qualifications</li>
                <li>{plan.letters} letters</li>
                <li>{plan.skipTraces} skip traces</li>
                <li>All FL counties</li>
              </ul>
              {plan.plan && sub?.plan !== plan.plan && (
                <button
                  onClick={() => handleUpgrade(plan.plan!)}
                  className="mt-4 w-full px-3 py-2 text-sm bg-emerald text-white rounded-md hover:bg-emerald/90"
                >
                  Upgrade
                </button>
              )}
              {sub?.plan === (plan.plan || "free") && (
                <p className="mt-4 text-center text-sm text-emerald font-medium">Current plan</p>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Profile */}
      <section>
        <h2 className="text-lg font-semibold mb-4">Profile</h2>
        <UserProfile />
      </section>
    </div>
  );
}
