import { useState } from "react";
import { useSubscription, useCounties } from "@/hooks/use-subscription";
import { useMyLeads } from "@/hooks/use-leads";
import { formatPercent } from "@/lib/utils";
import { BarChart3, FileText, Map, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";

export function DashboardPage() {
  const { data: sub } = useSubscription();
  const { data: myLeads } = useMyLeads();
  const { data: counties } = useCounties();
  const [showOnboarding, setShowOnboarding] = useState(() => {
    return !localStorage.getItem("recoverlead_onboarded");
  });

  const handleOnboardingComplete = () => {
    localStorage.setItem("recoverlead_onboarded", "true");
    setShowOnboarding(false);
  };

  // Show onboarding wizard for first-time users
  if (showOnboarding && (myLeads?.items?.length ?? 0) === 0) {
    return (
      <div className="space-y-6">
        <div className="text-center mb-4">
          <h1 className="text-2xl font-bold">
            Welcome to <span className="text-emerald">Recover</span>Lead
          </h1>
          <p className="text-muted-foreground">
            Let's get you started with your first qualified lead and outreach letter.
          </p>
        </div>
        <OnboardingWizard onComplete={handleOnboardingComplete} />
      </div>
    );
  }

  const stats = [
    {
      label: "My Leads",
      value: myLeads?.items?.length ?? 0,
      icon: BarChart3,
      to: "/my-leads",
    },
    {
      label: "Counties Available",
      value: counties?.length ?? 0,
      icon: Map,
      to: "/counties",
    },
    {
      label: "Qualifications Used",
      value: sub?.usage
        ? `${sub.usage.qualifications_used}/${sub.usage.qualifications_limit}`
        : "—",
      icon: TrendingUp,
      to: "/settings",
    },
    {
      label: "Letters Generated",
      value: sub?.usage
        ? `${sub.usage.letters_used}/${sub.usage.letters_limit}`
        : "—",
      icon: FileText,
      to: "/letters",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Welcome to RecoverLead</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Link
            key={stat.label}
            to={stat.to}
            className="p-6 bg-white rounded-lg border hover:border-emerald/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">{stat.label}</span>
              <stat.icon size={18} className="text-muted-foreground" />
            </div>
            <p className="text-2xl font-bold">{stat.value}</p>
          </Link>
        ))}
      </div>

      {sub?.usage && sub.usage.qualifications_pct >= 80 && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-sm text-amber-800">
            You've used {formatPercent(sub.usage.qualifications_pct)} of your monthly qualifications.
            {sub.usage.qualifications_pct >= 100
              ? " Upgrade your plan to continue qualifying leads."
              : " Consider upgrading to avoid interruptions."}
          </p>
          <Link
            to="/settings"
            className="mt-2 inline-block text-sm font-medium text-amber-900 underline"
          >
            Manage subscription
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          to="/leads"
          className="p-6 bg-white rounded-lg border hover:border-emerald/50 transition-colors"
        >
          <h3 className="font-medium mb-1">Browse Leads</h3>
          <p className="text-sm text-muted-foreground">
            Search surplus fund leads across all Florida counties
          </p>
        </Link>
        <Link
          to="/counties"
          className="p-6 bg-white rounded-lg border hover:border-emerald/50 transition-colors"
        >
          <h3 className="font-medium mb-1">View Counties</h3>
          <p className="text-sm text-muted-foreground">
            See available counties and their latest lead counts
          </p>
        </Link>
      </div>
    </div>
  );
}
