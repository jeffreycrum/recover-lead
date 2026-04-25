import { useState } from "react";
import { Link } from "react-router-dom";
import { useCounties } from "@/hooks/use-subscription";
import { formatDate } from "@/lib/utils";
import { Map, Phone, Mail, ExternalLink } from "lucide-react";
import { EmptyState } from "@/components/common/empty-state";
import { CountyChip, EyebrowTag, MonoCell, ProductCard, StateGroupLabel } from "@/components/landing-chrome";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function CountiesPage() {
  const allValue = "__all__";
  const [stateFilter, setStateFilter] = useState("");
  const { data: counties, isLoading } = useCounties();

  // Only surface counties we actually scrape (lead_count > 0). The DB
  // still carries pending counties for the future request-data flow,
  // but they create UI noise here — every state seeded with all 67/58
  // counties shows mostly zeros.
  const integratedCounties = (counties ?? []).filter(
    (c: any) => (c.lead_count ?? 0) > 0,
  );

  const allStates = Array.from(
    new Set(integratedCounties.map((c: any) => c.state as string))
  ).sort();

  const visibleCounties = integratedCounties.filter(
    (c: any) => !stateFilter || c.state === stateFilter,
  );

  const stateGroups = visibleCounties.reduce<Record<string, any[]>>((groups, county: any) => {
    const key = county.state || "Unknown";
    return { ...groups, [key]: [...(groups[key] ?? []), county] };
  }, {});

  const safeSourceUrl = (url: unknown): string | undefined =>
    typeof url === "string" && /^https?:\/\//i.test(url) ? url : undefined;

  const orderedStateGroups = Object.entries(stateGroups).sort(([left], [right]) =>
    left.localeCompare(right)
  );

  return (
    <div className="space-y-4">
      <div>
        <EyebrowTag>Coverage map</EyebrowTag>
        <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-[var(--lt-text)]">
          Counties
        </h1>
        <p className="mt-2 text-[var(--lt-text-muted)]">
          Counties currently producing surplus-fund leads
        </p>
      </div>

      <ProductCard heading="Filters" bodyClassName="pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={stateFilter || undefined}
            onValueChange={(value) => setStateFilter(!value || value === allValue ? "" : value)}
          >
            <SelectTrigger className="h-10 w-full max-w-[220px] rounded-full border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 text-[var(--lt-text)] hover:bg-[var(--lt-surface-2)]">
              <SelectValue placeholder="All States" />
            </SelectTrigger>
            <SelectContent className="border border-[var(--lt-line)] bg-[var(--lt-surface)] text-[var(--lt-text)] shadow-[0_18px_50px_-24px_rgba(0,0,0,0.8)]">
              <SelectItem value={allValue} className="text-[var(--lt-text)] focus:bg-[var(--lt-surface-2)] focus:text-[var(--lt-text)]">
                All States
              </SelectItem>
              {allStates.map((s) => (
                <SelectItem
                  key={s}
                  value={s}
                  className="text-[var(--lt-text)] focus:bg-[var(--lt-surface-2)] focus:text-[var(--lt-text)]"
                >
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </ProductCard>

      {isLoading ? (
        <div className="py-16 text-center text-[var(--lt-text-muted)]">Loading...</div>
      ) : visibleCounties.length > 0 ? (
        <div className="space-y-6">
          {orderedStateGroups.map(([state, countiesInState]) => (
            <section key={state} className="space-y-3">
              <StateGroupLabel label={state} count={countiesInState.length} />
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {countiesInState.map((county: any) => {
                  const card = (
                    <ProductCard
                      heading={county.name}
                      subtitle={`${county.state} · ${county.source_type?.toUpperCase() || "—"}`}
                      className="transition-transform hover:-translate-y-0.5"
                    >
                      <div className="mb-4 flex items-center justify-between gap-3">
                        <CountyChip variant={county.is_active ? "active" : "pending"}>
                          {county.is_active ? "Active county" : "Request data"}
                        </CountyChip>
                        <MonoCell tone="emerald">{(county.lead_count ?? 0).toLocaleString()}</MonoCell>
                      </div>

                      <div className="space-y-2 text-sm text-[var(--lt-text-muted)]">
                        <p>State: {county.state}</p>
                        <p>Source: {county.source_type?.toUpperCase() || "—"}</p>
                        <p>Last scraped: {formatDate(county.last_scraped_at)}</p>
                      </div>

                      {!county.is_active && (county.contact_phone || county.contact_email || safeSourceUrl(county.source_url)) && (
                        <div className="mt-4 space-y-2 border-t border-[var(--lt-line)] pt-4">
                          <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--lt-text-dim)]">
                            Request data
                          </p>
                          {safeSourceUrl(county.source_url) && (
                            <a
                              href={safeSourceUrl(county.source_url)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 text-sm text-[var(--lt-text)] transition-colors hover:text-[var(--lt-emerald)]"
                            >
                              <ExternalLink size={13} />
                              Clerk website
                            </a>
                          )}
                          {county.contact_phone && (
                            <a
                              href={`tel:${county.contact_phone.replace(/[^\d+]/g, "")}`}
                              className="flex items-center gap-1.5 text-sm text-[var(--lt-text)] transition-colors hover:text-[var(--lt-emerald)]"
                            >
                              <Phone size={13} />
                              {county.contact_phone}
                            </a>
                          )}
                          {county.contact_email && (
                            <a
                              href={`mailto:${county.contact_email}`}
                              className="flex items-center gap-1.5 text-sm text-[var(--lt-text)] transition-colors hover:text-[var(--lt-emerald)]"
                            >
                              <Mail size={13} />
                              {county.contact_email}
                            </a>
                          )}
                        </div>
                      )}
                    </ProductCard>
                  );

                  if (county.is_active && (county.lead_count ?? 0) > 0) {
                    return (
                      <Link
                        key={county.id}
                        to={`/leads?property_state=${encodeURIComponent(county.state)}&county_id=${encodeURIComponent(county.id)}`}
                        className="block"
                      >
                        {card}
                      </Link>
                    );
                  }
                  return <div key={county.id}>{card}</div>;
                })}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <ProductCard bodyClassName="py-10">
          <EmptyState
            icon={<Map size={48} />}
            title={
              stateFilter
                ? `No counties producing leads in ${stateFilter} yet`
                : "No counties producing leads yet"
            }
            description={
              stateFilter
                ? "Try selecting a different state."
                : "County data is being loaded. Check back shortly."
            }
            className="text-[var(--lt-text)]"
          />
        </ProductCard>
      )}
    </div>
  );
}
