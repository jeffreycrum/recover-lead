import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import { LeadScoreBadge } from "./lead-score-badge";
import { MonoCell, ProductCard, StatusPill } from "@/components/landing-chrome";
import { cn } from "@/lib/utils";

interface Lead {
  id: string;
  county_name: string;
  case_number: string;
  parcel_id?: string | null;
  property_address: string | null;
  property_city: string | null;
  surplus_amount: number;
  sale_date: string | null;
  sale_type: string | null;
  owner_name: string | null;
  quality_score?: number | null;
  status?: string;
}

type SortKey = "county_name" | "case_number" | "owner_name" | "surplus_amount" | "sale_date";
type SortDir = "asc" | "desc";

interface LeadTableProps {
  leads: Lead[];
  onSelect?: (id: string) => void;
  onClaim?: (id: string) => void;
  showScore?: boolean;
  showStatus?: boolean;
  showClaim?: boolean;
}

function SortIcon({ col, sortKey, sortDir }: { col: SortKey; sortKey: SortKey | null; sortDir: SortDir }) {
  if (sortKey !== col) return <ChevronsUpDown size={13} className="opacity-40" />;
  return sortDir === "asc" ? <ChevronUp size={13} /> : <ChevronDown size={13} />;
}

export function LeadTable({
  leads,
  onSelect,
  onClaim,
  showScore = false,
  showStatus = false,
  showClaim = false,
}: LeadTableProps) {
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (col: SortKey) => {
    if (sortKey === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return leads;
    return [...leads].sort((a, b) => {
      const av = a[sortKey] ?? "";
      const bv = b[sortKey] ?? "";
      let cmp = 0;
      if (typeof av === "number" && typeof bv === "number") {
        cmp = av - bv;
      } else {
        cmp = String(av).localeCompare(String(bv));
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [leads, sortKey, sortDir]);

  if (leads.length === 0) return null;

  const cardTitle = showClaim ? "Available leads" : showStatus ? "Claimed leads" : "Lead list";
  const headerCellClass =
    "px-4 py-3 align-middle text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--lt-text-dim)]";

  const Th = ({ col, label, align = "left" }: { col: SortKey; label: string; align?: "left" | "right" }) => (
    <th
      className={cn(
        headerCellClass,
        "cursor-pointer select-none transition-colors hover:text-[var(--lt-text)]",
        align === "right" ? "text-right" : "text-left"
      )}
      onClick={() => handleSort(col)}
    >
      <span
        className={cn(
          "mono inline-flex items-center gap-1.5",
          align === "right" ? "flex-row-reverse" : ""
        )}
      >
        {label}
        <SortIcon col={col} sortKey={sortKey} sortDir={sortDir} />
      </span>
    </th>
  );

  return (
    <ProductCard heading={cardTitle} showDots bodyClassName="px-0 pb-0 pt-4">
      <div className="overflow-x-auto">
        <table className="min-w-[1024px] w-full text-sm">
          <thead>
            <tr className="border-y border-[var(--lt-line)] bg-[var(--lt-bg-2)]">
              <Th col="county_name" label="County" />
              <Th col="case_number" label="Case #" />
              <Th col="owner_name" label="Owner" />
              <Th col="surplus_amount" label="Surplus" align="right" />
              <th className={cn(headerCellClass, "text-left")}>
                <span className="mono">Parcel / APN</span>
              </th>
              <th className={cn(headerCellClass, "text-left")}>
                <span className="mono">Property</span>
              </th>
              <Th col="sale_date" label="Sale Date" />
              {showScore && (
                <th className={cn(headerCellClass, "text-center")}>
                  <span className="mono">Score</span>
                </th>
              )}
              {showStatus && (
                <th className={cn(headerCellClass, "text-left")}>
                  <span className="mono">Status</span>
                </th>
              )}
              {showClaim && <th className={headerCellClass} />}
            </tr>
          </thead>
          <tbody>
            {sorted.map((lead) => (
              <tr
                key={lead.id}
                onClick={() => onSelect?.(lead.id)}
                className="cursor-pointer border-b border-[var(--lt-line)] transition-colors hover:bg-[var(--lt-emerald-dim)]"
              >
                <td className="px-4 py-3.5 text-[var(--lt-text)]">{lead.county_name}</td>
                <td className="px-4 py-3.5">
                  <MonoCell size="sm">{lead.case_number}</MonoCell>
                </td>
                <td className="px-4 py-3.5 text-[var(--lt-text)]">{lead.owner_name || "—"}</td>
                <td className="px-4 py-3.5 text-right">
                  <MonoCell size="md" tone="emerald">
                    {formatCurrency(lead.surplus_amount)}
                  </MonoCell>
                </td>
                <td className="px-4 py-3.5">
                  {lead.parcel_id ? (
                    <MonoCell size="sm" tone="muted">
                      {lead.parcel_id}
                    </MonoCell>
                  ) : (
                    <span className="text-[var(--lt-text-muted)]">—</span>
                  )}
                </td>
                <td className="px-4 py-3.5 text-[var(--lt-text-muted)]">
                  {lead.property_address
                    ? `${lead.property_address}${lead.property_city ? `, ${lead.property_city}` : ""}`
                    : "—"}
                </td>
                <td className="px-4 py-3.5">
                  <MonoCell size="sm" tone="muted">
                    {formatDate(lead.sale_date)}
                  </MonoCell>
                </td>
                {showScore && (
                  <td className="px-4 py-3.5 text-center">
                    <LeadScoreBadge score={lead.quality_score ?? null} />
                  </td>
                )}
                {showStatus && (
                  <td className="px-4 py-3.5">
                    <StatusPill status={lead.status || "new"} />
                  </td>
                )}
                {showClaim && (
                  <td className="px-4 py-3.5">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onClaim?.(lead.id);
                        onSelect?.(lead.id);
                      }}
                      className="rounded-full bg-[var(--lt-emerald)] px-3.5 py-1.5 text-xs font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]"
                    >
                      Claim
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ProductCard>
  );
}
