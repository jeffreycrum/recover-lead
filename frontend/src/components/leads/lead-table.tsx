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

interface LeadTableProps {
  leads: Lead[];
  onSelect?: (id: string) => void;
  onClaim?: (id: string) => void;
  showScore?: boolean;
  showStatus?: boolean;
  showClaim?: boolean;
}

export function LeadTable({
  leads,
  onSelect,
  onClaim,
  showScore = false,
  showStatus = false,
  showClaim = false,
}: LeadTableProps) {
  if (leads.length === 0) {
    return null;
  }

  return (
    <div className="overflow-x-auto rounded-lg border bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50/50">
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">County</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Case #</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Owner</th>
            <th className="text-right px-4 py-3 font-medium text-muted-foreground">Surplus</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Property</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Sale Date</th>
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
          {leads.map((lead) => (
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
