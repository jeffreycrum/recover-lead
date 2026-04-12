import { useState, useEffect, useRef } from "react";
import { useBrowseLeads, useClaimLead } from "@/hooks/use-leads";
import { useCounties } from "@/hooks/use-subscription";
import { LeadTable } from "@/components/leads/lead-table";
import { LeadDetail } from "@/components/leads/lead-detail";
import { EmptyState } from "@/components/common/empty-state";
import { Search } from "lucide-react";

export function LeadsPage() {
  const [selectedLead, setSelectedLead] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [allLeads, setAllLeads] = useState<any[]>([]);
  const appendRef = useRef(false);

  const { data, isLoading } = useBrowseLeads(
    cursor ? { ...filters, cursor } : filters,
  );
  const { data: counties } = useCounties();
  const claimMutation = useClaimLead();

  useEffect(() => {
    if (!data?.items) return;
    if (appendRef.current) {
      setAllLeads((prev) => [...prev, ...data.items]);
    } else {
      setAllLeads(data.items);
    }
    appendRef.current = false;
  }, [data]);

  const updateFilter = (update: (f: Record<string, string>) => Record<string, string>) => {
    appendRef.current = false;
    setCursor(undefined);
    setFilters(update);
  };

  const handleLoadMore = () => {
    if (!data?.next_cursor) return;
    appendRef.current = true;
    setCursor(data.next_cursor);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Browse Leads</h1>
          <p className="text-muted-foreground">
            All surplus fund leads across Florida counties
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          className="px-3 py-2 border rounded-md text-sm bg-white"
          value={filters.county_id || ""}
          onChange={(e) =>
            updateFilter((f) => ({
              ...f,
              county_id: e.target.value || undefined!,
            }))
          }
        >
          <option value="">All Counties</option>
          {counties?.map((c: any) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.lead_count})
            </option>
          ))}
        </select>

        <input
          type="number"
          placeholder="Min surplus ($)"
          className="px-3 py-2 border rounded-md text-sm w-36"
          onChange={(e) =>
            updateFilter((f) => ({ ...f, surplus_min: e.target.value || undefined! }))
          }
        />
        <input
          type="number"
          placeholder="Max surplus ($)"
          className="px-3 py-2 border rounded-md text-sm w-36"
          onChange={(e) =>
            updateFilter((f) => ({ ...f, surplus_max: e.target.value || undefined! }))
          }
        />
        <select
          className="px-3 py-2 border rounded-md text-sm bg-white"
          value={filters.sale_type || ""}
          onChange={(e) =>
            updateFilter((f) => ({ ...f, sale_type: e.target.value || undefined! }))
          }
        >
          <option value="">All Types</option>
          <option value="tax_deed">Tax Deed</option>
          <option value="foreclosure">Foreclosure</option>
          <option value="lien">Lien</option>
        </select>
      </div>

      {/* Table */}
      {isLoading && allLeads.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">Loading leads...</div>
      ) : allLeads.length > 0 ? (
        <>
          <LeadTable
            leads={allLeads}
            onSelect={setSelectedLead}
            onClaim={(id) => claimMutation.mutate(id)}
            showClaim
          />
          {data?.has_more && (
            <div className="flex justify-center">
              <button
                onClick={handleLoadMore}
                disabled={isLoading}
                className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                {isLoading ? "Loading..." : "Load more"}
              </button>
            </div>
          )}
        </>
      ) : (
        <EmptyState
          icon={<Search size={48} />}
          title="No leads found"
          description="Try adjusting your filters or check back later for new leads."
        />
      )}

      {/* Detail drawer */}
      {selectedLead && (
        <LeadDetail leadId={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
