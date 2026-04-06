import { useCounties } from "@/hooks/use-subscription";
import { formatDate } from "@/lib/utils";
import { Map, CheckCircle, XCircle } from "lucide-react";
import { EmptyState } from "@/components/common/empty-state";

export function CountiesPage() {
  const { data: counties, isLoading } = useCounties();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Counties</h1>
        <p className="text-muted-foreground">
          Florida counties with surplus fund data
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading...</div>
      ) : counties && counties.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {counties.map((county: any) => (
            <div
              key={county.id}
              className="p-4 bg-white rounded-lg border hover:border-emerald/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium">{county.name}</h3>
                {county.is_active ? (
                  <CheckCircle size={16} className="text-emerald" />
                ) : (
                  <XCircle size={16} className="text-muted-foreground" />
                )}
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>State: {county.state}</p>
                <p>Leads: {county.lead_count.toLocaleString()}</p>
                <p>Source: {county.source_type?.toUpperCase() || "—"}</p>
                <p>Last scraped: {formatDate(county.last_scraped_at)}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Map size={48} />}
          title="No counties available"
          description="County data is being loaded. Check back shortly."
        />
      )}
    </div>
  );
}
