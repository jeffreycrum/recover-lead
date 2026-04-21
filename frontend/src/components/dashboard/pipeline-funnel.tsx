import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { api } from "@/lib/api";
import { ProductCard } from "@/components/landing-chrome";

const COLORS = {
  new: "#64748b",
  qualified: "#8b5cf6",
  contacted: "#3b82f6",
  signed: "url(#signed-gradient)",
  filed: "#f59e0b",
  paid: "url(#paid-gradient)",
  closed: "#475569",
};

export function PipelineFunnel() {
  const { data: pipeline, isLoading } = useQuery({
    queryKey: ["pipeline-stats"],
    queryFn: () => api.getPipelineStats(),
  });

  if (isLoading || !pipeline) return null;

  const data = [
    { stage: "New", count: pipeline.leads_new, color: COLORS.new },
    { stage: "Qualified", count: pipeline.leads_qualified, color: COLORS.qualified },
    { stage: "Contacted", count: pipeline.leads_contacted, color: COLORS.contacted },
    { stage: "Signed", count: pipeline.leads_signed, color: COLORS.signed },
    { stage: "Filed", count: pipeline.leads_filed, color: COLORS.filed },
    { stage: "Paid", count: pipeline.leads_paid, color: COLORS.paid },
    { stage: "Closed", count: pipeline.leads_closed, color: COLORS.closed },
  ];

  if (pipeline.leads_total === 0) {
    return (
      <ProductCard heading="Pipeline">
        <p className="text-sm text-[var(--lt-text-muted)]">
          Claim your first lead to see your pipeline.
        </p>
      </ProductCard>
    );
  }

  return (
    <ProductCard heading="Pipeline" showDots>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <defs>
            <linearGradient id="signed-gradient" x1="0" x2="1">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
            <linearGradient id="paid-gradient" x1="0" x2="1">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#0ea572" />
            </linearGradient>
          </defs>
          <XAxis type="number" allowDecimals={false} stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis type="category" dataKey="stage" width={84} stroke="#64748b" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <Tooltip
            cursor={{ fill: "rgba(16,185,129,0.08)" }}
            contentStyle={{
              background: "var(--lt-surface)",
              border: "1px solid var(--lt-line)",
              borderRadius: 12,
              color: "var(--lt-text)",
            }}
            labelStyle={{ color: "var(--lt-text)" }}
          />
          <Bar dataKey="count" radius={[8, 8, 8, 8]}>
            {data.map((entry) => (
              <Cell key={entry.stage} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ProductCard>
  );
}
