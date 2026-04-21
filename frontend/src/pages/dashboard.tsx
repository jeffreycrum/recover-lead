import { useState } from "react";
import { useSubscription, useCounties } from "@/hooks/use-subscription";
import { useMyLeads } from "@/hooks/use-leads";
import { formatPercent } from "@/lib/utils";
import { BarChart3, FileText, Map, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";
import { RoiStats } from "@/components/dashboard/roi-stats";
import { PipelineFunnel } from "@/components/dashboard/pipeline-funnel";
import { CountyUpsellBanner } from "@/components/dashboard/county-upsell-banner";
import { EyebrowTag, MonoCell, ProductCard } from "@/components/landing-chrome";

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

  if (showOnboarding && (myLeads?.items?.length ?? 0) === 0) {
    return (
      <div className="space-y-6">
        <div className="mb-4 text-center">
          <EyebrowTag>First-run setup</EyebrowTag>
          <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
            Welcome to <span className="text-[var(--lt-emerald)]">Recover</span>Lead
          </h1>
          <p className="mt-2 text-[var(--lt-text-muted)]">
            Let&apos;s get you started with your first qualified lead and outreach letter.
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
        <EyebrowTag>Operator dashboard</EyebrowTag>
        <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
          Dashboard
        </h1>
        <p className="mt-2 text-[var(--lt-text-muted)]">Welcome to RecoverLead</p>
      </div>

      <CountyUpsellBanner />
      <RoiStats />
      <PipelineFunnel />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <ProductCard
            key={stat.label}
            as={Link}
            to={stat.to}
            heading={stat.label}
            showDots
            className="transition-transform hover:-translate-y-0.5"
          >
            <div className="flex items-end justify-between gap-4">
              <MonoCell size="lg" tone="emerald">
                {stat.value}
              </MonoCell>
              <div className="rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] p-2 text-[var(--lt-text-muted)]">
                <stat.icon size={16} />
              </div>
            </div>
          </ProductCard>
        ))}
      </div>

      {sub?.usage && sub.usage.qualifications_pct >= 80 && (
        <div className="rounded-[18px] border border-[rgba(245,158,11,0.3)] bg-[rgba(245,158,11,0.12)] p-4">
          <p className="text-sm leading-6 text-[#fde68a]">
            You&apos;ve used {formatPercent(sub.usage.qualifications_pct)} of your monthly
            qualifications.
            {sub.usage.qualifications_pct >= 100
              ? " Upgrade your plan to continue qualifying leads."
              : " Consider upgrading to avoid interruptions."}
          </p>
          <Link
            to="/settings"
            className="mt-3 inline-block text-sm font-medium text-[#fcd34d] underline underline-offset-4"
          >
            Manage subscription
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ProductCard
          as={Link}
          to="/leads"
          heading="Browse Leads"
          className="transition-transform hover:-translate-y-0.5"
        >
          <p className="text-sm font-medium text-[var(--lt-text)]">Browse Leads</p>
          <p className="mt-2 text-sm leading-6 text-[var(--lt-text-muted)]">
            Search surplus fund leads across all Florida counties.
          </p>
        </ProductCard>
        <ProductCard
          as={Link}
          to="/counties"
          heading="View Counties"
          className="transition-transform hover:-translate-y-0.5"
        >
          <p className="text-sm font-medium text-[var(--lt-text)]">View Counties</p>
          <p className="mt-2 text-sm leading-6 text-[var(--lt-text-muted)]">
            See available counties and their latest lead counts.
          </p>
        </ProductCard>
      </div>
    </div>
  );
}
