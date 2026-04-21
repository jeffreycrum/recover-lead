import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DollarSign, TrendingUp, Award, Clock } from "lucide-react";
import { MonoCell, ProductCard } from "@/components/landing-chrome";

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

export function RoiStats() {
  const { data: roi, isLoading } = useQuery({
    queryKey: ["roi-stats"],
    queryFn: () => api.getRoiStats(),
  });

  if (isLoading) return null;
  if (!roi || roi.deal_count === 0) {
    return (
      <ProductCard heading="ROI snapshot">
        <p className="text-sm text-[var(--lt-text-muted)]">
          Close your first deal to see ROI metrics here.
        </p>
      </ProductCard>
    );
  }

  const cards = [
    {
      label: "Total Recovered",
      value: formatCurrency(roi.total_recovered),
      icon: DollarSign,
      color: "text-[var(--lt-emerald)]",
    },
    {
      label: "Fees Earned",
      value: formatCurrency(roi.total_fees),
      icon: TrendingUp,
      color: "text-[var(--lt-emerald)]",
    },
    {
      label: "Deals Closed",
      value: roi.deal_count.toString(),
      icon: Award,
      color: "text-[#93c5fd]",
    },
    {
      label: "Avg Days to Close",
      value: roi.avg_days_to_close
        ? Math.round(roi.avg_days_to_close).toString()
        : "—",
      icon: Clock,
      color: "text-[#fcd34d]",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <ProductCard key={card.label} heading={card.label}>
          <div className="mb-3 flex items-center gap-2">
            <card.icon size={16} className={card.color} />
          </div>
          <MonoCell size="lg" className={card.color}>
            {card.value}
          </MonoCell>
        </ProductCard>
      ))}
    </div>
  );
}
