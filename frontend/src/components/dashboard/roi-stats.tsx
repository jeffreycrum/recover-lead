import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DollarSign, TrendingUp, Award, Clock } from "lucide-react";

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
      <div className="p-6 bg-white rounded-lg border text-center">
        <p className="text-muted-foreground text-sm">
          Close your first deal to see ROI metrics here.
        </p>
      </div>
    );
  }

  const cards = [
    {
      label: "Total Recovered",
      value: formatCurrency(roi.total_recovered),
      icon: DollarSign,
      color: "text-emerald",
    },
    {
      label: "Fees Earned",
      value: formatCurrency(roi.total_fees),
      icon: TrendingUp,
      color: "text-emerald",
    },
    {
      label: "Deals Closed",
      value: roi.deal_count.toString(),
      icon: Award,
      color: "text-blue-600",
    },
    {
      label: "Avg Days to Close",
      value: roi.avg_days_to_close
        ? Math.round(roi.avg_days_to_close).toString()
        : "—",
      icon: Clock,
      color: "text-amber-600",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="p-4 bg-white rounded-lg border">
          <div className="flex items-center gap-2 mb-2">
            <card.icon size={16} className={card.color} />
            <span className="text-xs text-muted-foreground">{card.label}</span>
          </div>
          <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
