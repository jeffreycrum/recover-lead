import { UserProfile } from "@clerk/clerk-react";
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

          {sub.plan !== "free" && (
            <button
              onClick={handleManageBilling}
              className="text-sm text-emerald hover:underline"
            >
              Manage billing
            </button>
          )}
        </section>
      )}

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
