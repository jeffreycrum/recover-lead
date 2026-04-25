import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useBrowseLeads, useClaimLead } from "@/hooks/use-leads";
import { useCounties } from "@/hooks/use-subscription";
import { LeadTable } from "@/components/leads/lead-table";
import { LeadDetail } from "@/components/leads/lead-detail";
import { EmptyState } from "@/components/common/empty-state";
import { Search } from "lucide-react";
import { EyebrowTag, ProductCard } from "@/components/landing-chrome";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function LeadsPage() {
  const allValue = "__all__";
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedLead, setSelectedLead] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    const state = searchParams.get("property_state");
    const countyId = searchParams.get("county_id");
    if (state) initial.property_state = state;
    if (countyId) initial.county_id = countyId;
    return initial;
  });
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [allLeads, setAllLeads] = useState<any[]>([]);
  const appendRef = useRef(false);

  // Clear the URL once the filter state is seeded so a page reload
  // doesn't re-apply stale params after the user changes filters.
  useEffect(() => {
    if (searchParams.has("property_state") || searchParams.has("county_id")) {
      const next = new URLSearchParams(searchParams);
      next.delete("property_state");
      next.delete("county_id");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const { data, isLoading } = useBrowseLeads(
    cursor ? { ...filters, cursor } : filters,
  );
  const { data: counties } = useCounties();

  // Hide counties without any leads from the dropdowns. The full list
  // (including pending counties with 0 leads) lives on the Counties
  // page where the user can request data; the Browse Leads filter
  // should only surface counties that actually contribute leads.
  const integratedCounties = (counties ?? []).filter(
    (c: any) => (c.lead_count ?? 0) > 0,
  );

  const allStates = Array.from(
    new Set(integratedCounties.map((c: any) => c.state as string))
  ).sort();

  const visibleCounties = filters.property_state
    ? integratedCounties.filter((c: any) => c.state === filters.property_state)
    : integratedCounties;
  const claimMutation = useClaimLead();
  const selectTriggerClass =
    "h-10 min-w-[160px] rounded-full border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 text-[var(--lt-text)] hover:bg-[var(--lt-surface-2)]";
  const selectContentClass =
    "border border-[var(--lt-line)] bg-[var(--lt-surface)] text-[var(--lt-text)] shadow-[0_18px_50px_-24px_rgba(0,0,0,0.8)]";
  const selectItemClass =
    "text-[var(--lt-text)] focus:bg-[var(--lt-surface-2)] focus:text-[var(--lt-text)]";
  const inputClass =
    "h-10 w-36 rounded-full border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 text-[var(--lt-text)] placeholder:text-[var(--lt-text-dim)]";

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
      <div>
        <EyebrowTag>Lead discovery</EyebrowTag>
        <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
          Browse Leads
        </h1>
        <p className="mt-2 text-[var(--lt-text-muted)]">
          All surplus fund leads across available counties
        </p>
      </div>

      <ProductCard heading="Filters" bodyClassName="pt-4">
        <div className="flex flex-wrap gap-3">
          <Select
            value={filters.property_state || undefined}
            onValueChange={(value) =>
              updateFilter((f) => {
                const { county_id: _dropped, ...rest } = f;
                return value && value !== allValue ? { ...rest, property_state: value } : rest;
              })
            }
          >
            <SelectTrigger className={selectTriggerClass}>
              <SelectValue placeholder="All States" />
            </SelectTrigger>
            <SelectContent className={selectContentClass}>
              <SelectItem value={allValue} className={selectItemClass}>
                All States
              </SelectItem>
              {allStates.map((s) => (
                <SelectItem key={s} value={s} className={selectItemClass}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.county_id || undefined}
            onValueChange={(value) =>
              updateFilter((f) => {
                const { county_id: _dropped, ...rest } = f;
                return value && value !== allValue ? { ...rest, county_id: value } : rest;
              })
            }
          >
            <SelectTrigger className={selectTriggerClass}>
              <SelectValue placeholder="All Counties">
                {filters.county_id
                  ? (visibleCounties.find((c: any) => c.id === filters.county_id)?.name ?? "County")
                  : undefined}
              </SelectValue>
            </SelectTrigger>
            <SelectContent className={selectContentClass}>
              <SelectItem value={allValue} className={selectItemClass}>
                All Counties
              </SelectItem>
              {visibleCounties.map((c: any) => (
                <SelectItem key={c.id} value={c.id} className={selectItemClass}>
                  {c.name} ({c.lead_count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            type="number"
            placeholder="Min surplus ($)"
            className={inputClass}
            value={filters.surplus_min ?? ""}
            onChange={(e) =>
              updateFilter((f) => {
                const { surplus_min: _dropped, ...rest } = f;
                return e.target.value ? { ...rest, surplus_min: e.target.value } : rest;
              })
            }
          />
          <Input
            type="number"
            placeholder="Max surplus ($)"
            className={inputClass}
            value={filters.surplus_max ?? ""}
            onChange={(e) =>
              updateFilter((f) => {
                const { surplus_max: _dropped, ...rest } = f;
                return e.target.value ? { ...rest, surplus_max: e.target.value } : rest;
              })
            }
          />

          <Select
            value={filters.sale_type || undefined}
            onValueChange={(value) =>
              updateFilter((f) => {
                const { sale_type: _dropped, ...rest } = f;
                return value && value !== allValue ? { ...rest, sale_type: value } : rest;
              })
            }
          >
            <SelectTrigger className={selectTriggerClass}>
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent className={selectContentClass}>
              <SelectItem value={allValue} className={selectItemClass}>
                All Types
              </SelectItem>
              <SelectItem value="tax_deed" className={selectItemClass}>
                Tax Deed
              </SelectItem>
              <SelectItem value="foreclosure" className={selectItemClass}>
                Foreclosure
              </SelectItem>
              <SelectItem value="lien" className={selectItemClass}>
                Lien
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </ProductCard>

      {isLoading && allLeads.length === 0 ? (
        <div className="py-16 text-center text-[var(--lt-text-muted)]">Loading leads...</div>
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
                className="rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)] disabled:opacity-50"
              >
                {isLoading ? "Loading..." : "Load more"}
              </button>
            </div>
          )}
        </>
      ) : (
        <ProductCard bodyClassName="py-10">
          <EmptyState
            icon={<Search size={48} />}
            title="No leads found"
            description="Try adjusting your filters or check back later for new leads."
            className="text-[var(--lt-text)]"
          />
        </ProductCard>
      )}

      {selectedLead && (
        <LeadDetail leadId={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
