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

const COLORS = {
  new: "#94a3b8",
  qualified: "#a78bfa",
  contacted: "#60a5fa",
  signed: "#34d399",
  filed: "#fbbf24",
  paid: "#10b981",
  closed: "#6b7280",
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
      <div className="p-6 bg-white rounded-lg border text-center">
        <p className="text-muted-foreground text-sm">
          Claim your first lead to see your pipeline.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 bg-white rounded-lg border">
      <h3 className="text-lg font-semibold mb-4">Pipeline</h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} layout="vertical" margin={{ left: 16 }}>
          <XAxis type="number" allowDecimals={false} />
          <YAxis type="category" dataKey="stage" width={80} />
          <Tooltip cursor={{ fill: "rgba(0,0,0,0.04)" }} />
          <Bar dataKey="count">
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
