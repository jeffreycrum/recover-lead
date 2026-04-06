import { useState } from "react";
import { useMyLeads } from "@/hooks/use-leads";
import { LeadTable } from "@/components/leads/lead-table";
import { LeadDetail } from "@/components/leads/lead-detail";
import { EmptyState } from "@/components/common/empty-state";
import { BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";

export function MyLeadsPage() {
  const [selectedLead, setSelectedLead] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const { data, isLoading } = useMyLeads(filters);

  const leads =
    data?.items?.map((item: any) => ({
      id: item.lead_id,
      county_name: item.county_name,
      case_number: item.case_number,
      property_address: item.property_address,
      property_city: item.property_city,
      surplus_amount: item.surplus_amount,
      sale_date: item.sale_date,
      sale_type: null,
      owner_name: item.owner_name,
      quality_score: item.quality_score,
      status: item.status,
    })) ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">My Leads</h1>
        <p className="text-muted-foreground">Leads you've claimed and are working</p>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select
          className="px-3 py-2 border rounded-md text-sm bg-white"
          value={filters.status || ""}
          onChange={(e) =>
            setFilters((f) => ({ ...f, status: e.target.value || undefined! }))
          }
        >
          <option value="">All Statuses</option>
          <option value="new">New</option>
          <option value="qualified">Qualified</option>
          <option value="contacted">Contacted</option>
          <option value="signed">Signed</option>
          <option value="filed">Filed</option>
          <option value="paid">Paid</option>
          <option value="closed">Closed</option>
        </select>
        <input
          type="number"
          placeholder="Min score"
          className="px-3 py-2 border rounded-md text-sm w-28"
          onChange={(e) =>
            setFilters((f) => ({ ...f, min_score: e.target.value || undefined! }))
          }
        />
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading...</div>
      ) : leads.length > 0 ? (
        <LeadTable
          leads={leads}
          onSelect={setSelectedLead}
          showScore
          showStatus
        />
      ) : (
        <EmptyState
          icon={<BarChart3 size={48} />}
          title="No claimed leads"
          description="Browse available leads and claim ones you want to work."
          action={
            <Link
              to="/leads"
              className="px-4 py-2 bg-emerald text-white rounded-md hover:bg-emerald/90 text-sm font-medium"
            >
              Browse Leads
            </Link>
          }
        />
      )}

      {selectedLead && (
        <LeadDetail leadId={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
