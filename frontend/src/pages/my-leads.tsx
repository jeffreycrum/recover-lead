import { useState } from "react";
import { useMyLeads } from "@/hooks/use-leads";
import { LeadTable } from "@/components/leads/lead-table";
import { LeadDetail } from "@/components/leads/lead-detail";
import { EmptyState } from "@/components/common/empty-state";
import { BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";
import { EyebrowTag, ProductCard } from "@/components/landing-chrome";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function MyLeadsPage() {
  const allValue = "__all__";
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

  const selectTriggerClass =
    "h-10 min-w-[180px] rounded-full border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 text-[var(--lt-text)] hover:bg-[var(--lt-surface-2)]";
  const selectContentClass =
    "border border-[var(--lt-line)] bg-[var(--lt-surface)] text-[var(--lt-text)] shadow-[0_18px_50px_-24px_rgba(0,0,0,0.8)]";
  const selectItemClass =
    "text-[var(--lt-text)] focus:bg-[var(--lt-surface-2)] focus:text-[var(--lt-text)]";

  return (
    <div className="space-y-4">
      <div>
        <EyebrowTag>Active pipeline</EyebrowTag>
        <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
          My Leads
        </h1>
        <p className="mt-2 text-[var(--lt-text-muted)]">Leads you&apos;ve claimed and are working</p>
      </div>

      <ProductCard heading="Filters" bodyClassName="pt-4">
        <div className="flex flex-wrap gap-3">
          <Select
            value={filters.status || undefined}
            onValueChange={(value) =>
              setFilters((f) => {
                const { status: _dropped, ...rest } = f;
                return value && value !== allValue ? { ...rest, status: value } : rest;
              })
            }
          >
            <SelectTrigger className={selectTriggerClass}>
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent className={selectContentClass}>
              <SelectItem value={allValue} className={selectItemClass}>All Statuses</SelectItem>
              <SelectItem value="new" className={selectItemClass}>New</SelectItem>
              <SelectItem value="qualified" className={selectItemClass}>Qualified</SelectItem>
              <SelectItem value="contacted" className={selectItemClass}>Contacted</SelectItem>
              <SelectItem value="signed" className={selectItemClass}>Signed</SelectItem>
              <SelectItem value="filed" className={selectItemClass}>Filed</SelectItem>
              <SelectItem value="paid" className={selectItemClass}>Paid</SelectItem>
              <SelectItem value="closed" className={selectItemClass}>Closed</SelectItem>
            </SelectContent>
          </Select>

          <Input
            type="number"
            placeholder="Min score"
            className="h-10 w-28 rounded-full border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 text-[var(--lt-text)] placeholder:text-[var(--lt-text-dim)]"
            onChange={(e) =>
              setFilters((f) => {
                const { min_score: _dropped, ...rest } = f;
                return e.target.value ? { ...rest, min_score: e.target.value } : rest;
              })
            }
          />
        </div>
      </ProductCard>

      {isLoading ? (
        <div className="py-16 text-center text-[var(--lt-text-muted)]">Loading...</div>
      ) : leads.length > 0 ? (
        <LeadTable
          leads={leads}
          onSelect={setSelectedLead}
          showScore
          showStatus
        />
      ) : (
        <ProductCard bodyClassName="py-10">
          <EmptyState
            icon={<BarChart3 size={48} />}
            title="No claimed leads"
            description="Browse available leads and claim ones you want to work."
            className="text-[var(--lt-text)]"
            action={
              <Link
                to="/leads"
                className="inline-flex rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]"
              >
                Browse Leads
              </Link>
            }
          />
        </ProductCard>
      )}

      {selectedLead && (
        <LeadDetail leadId={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
