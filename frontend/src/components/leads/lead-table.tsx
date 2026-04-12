import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import { LeadScoreBadge } from "./lead-score-badge";

interface Lead {
  id: string;
  county_name: string;
  case_number: string;
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

  const thClass = "px-4 py-3 font-medium text-muted-foreground select-none cursor-pointer hover:text-foreground";

  const Th = ({ col, label, align = "left" }: { col: SortKey; label: string; align?: "left" | "right" }) => (
    <th
      className={`${thClass} text-${align}`}
      onClick={() => handleSort(col)}
    >
      <span className={`inline-flex items-center gap-1 ${align === "right" ? "flex-row-reverse" : ""}`}>
        {label}
        <SortIcon col={col} sortKey={sortKey} sortDir={sortDir} />
      </span>
    </th>
  );

  return (
    <div className="overflow-x-auto rounded-lg border bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50/50">
            <Th col="county_name" label="County" />
            <Th col="case_number" label="Case #" />
            <Th col="owner_name" label="Owner" />
            <Th col="surplus_amount" label="Surplus" align="right" />
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Property</th>
            <Th col="sale_date" label="Sale Date" />
            {showScore && (
              <th className="text-center px-4 py-3 font-medium text-muted-foreground">Score</th>
            )}
            {showStatus && (
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
            )}
            {showClaim && <th className="px-4 py-3" />}
          </tr>
        </thead>
        <tbody>
          {sorted.map((lead) => (
            <tr
              key={lead.id}
              onClick={() => onSelect?.(lead.id)}
              className="border-b hover:bg-gray-50 cursor-pointer transition-colors"
            >
              <td className="px-4 py-3">{lead.county_name}</td>
              <td className="px-4 py-3 font-mono text-xs">{lead.case_number}</td>
              <td className="px-4 py-3">{lead.owner_name || "—"}</td>
              <td className="px-4 py-3 text-right font-medium text-emerald">
                {formatCurrency(lead.surplus_amount)}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {lead.property_address
                  ? `${lead.property_address}${lead.property_city ? `, ${lead.property_city}` : ""}`
                  : "—"}
              </td>
              <td className="px-4 py-3 text-muted-foreground">{formatDate(lead.sale_date)}</td>
              {showScore && (
                <td className="px-4 py-3 text-center">
                  <LeadScoreBadge score={lead.quality_score ?? null} />
                </td>
              )}
              {showStatus && (
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 capitalize">
                    {lead.status || "new"}
                  </span>
                </td>
              )}
              {showClaim && (
                <td className="px-4 py-3">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onClaim?.(lead.id);
                      onSelect?.(lead.id);
                    }}
                    className="px-3 py-1 text-xs bg-emerald text-white rounded hover:bg-emerald/90 transition-colors"
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
  );
}
