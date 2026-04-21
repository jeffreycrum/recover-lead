import { Phone, Mail, MapPin, AlertTriangle, Shield, User, Skull } from "lucide-react";

interface PhoneData {
  number: string;
  type: string;
  dnc: boolean;
  carrier: string;
  rank: number;
}

interface EmailData {
  email: string;
  rank: number;
}

interface PersonData {
  first_name: string;
  last_name: string;
  full_name: string;
  dob: string | null;
  age: number | null;
  deceased: boolean;
  property_owner: boolean;
  litigator: boolean;
  mailing_address: {
    street: string;
    city: string;
    state: string;
    zip_code: string;
  } | null;
  phones: PhoneData[];
  emails: EmailData[];
}

interface SkipTraceResult {
  id: string;
  provider: string;
  status: string;
  persons: PersonData[];
  hit_count: number;
  cost: number;
  created_at: string;
}

export function SkipTraceResults({ results }: { results: SkipTraceResult[] }) {
  if (!results || results.length === 0) return null;

  const latest = results[0];

  if (latest.status === "miss") {
    return (
      <div className="mt-4 rounded-[18px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] p-4">
        <p className="text-sm text-[var(--lt-text-muted)]">
          No contact information found. Try a premium lookup for better results.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-[var(--lt-text)]">Skip Trace Results</h4>
        <span className="text-xs text-[var(--lt-text-muted)]">
          via {latest.provider} &middot; {new Date(latest.created_at).toLocaleDateString()}
        </span>
      </div>

      {latest.persons.map((person, i) => (
        <div
          key={i}
          className="space-y-3 rounded-[18px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] p-4"
        >
          <div className="flex flex-wrap items-center gap-2">
            <User size={14} className="text-[var(--lt-text-dim)]" />
            <span className="font-medium text-[var(--lt-text)]">
              {person.full_name || `${person.first_name} ${person.last_name}`}
            </span>
            {person.age && (
              <span className="text-xs text-[var(--lt-text-muted)]">Age {person.age}</span>
            )}
            {person.property_owner && (
              <span className="rounded-md bg-[var(--lt-emerald-dim)] px-2 py-1 text-xs text-[var(--lt-emerald-light)]">
                Owner
              </span>
            )}
            {person.deceased && (
              <span className="flex items-center gap-1 rounded-md bg-[var(--lt-red-dim)] px-2 py-1 text-xs text-[#fca5a5]">
                <Skull size={10} /> Deceased
              </span>
            )}
            {person.litigator && (
              <span className="flex items-center gap-1 rounded-md bg-[var(--lt-amber-dim)] px-2 py-1 text-xs text-[#fcd34d]">
                <Shield size={10} /> TCPA Litigator
              </span>
            )}
          </div>

          {person.phones.length > 0 && (
            <div className="space-y-1.5">
              {person.phones.map((phone, j) => (
                <div key={j} className="flex flex-wrap items-center gap-2 text-sm text-[var(--lt-text)]">
                  <Phone size={12} className="text-[var(--lt-text-dim)]" />
                  <span className="mono">{phone.number}</span>
                  <span className="rounded-md bg-[rgba(148,163,184,0.12)] px-2 py-0.5 text-xs text-[var(--lt-text-muted)]">
                    {phone.type || "unknown"}
                  </span>
                  {phone.carrier && (
                    <span className="text-xs text-[var(--lt-text-muted)]">{phone.carrier}</span>
                  )}
                  {phone.dnc && (
                    <span className="flex items-center gap-1 rounded-md bg-[var(--lt-red-dim)] px-2 py-0.5 text-xs text-[#fca5a5]">
                      <AlertTriangle size={10} /> DNC
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {person.emails.length > 0 && (
            <div className="space-y-1.5">
              {person.emails.map((email, j) => (
                <div key={j} className="flex items-center gap-2 text-sm text-[var(--lt-text)]">
                  <Mail size={12} className="text-[var(--lt-text-dim)]" />
                  <span>{email.email}</span>
                </div>
              ))}
            </div>
          )}

          {person.mailing_address && person.mailing_address.street && (
            <div className="flex items-center gap-2 text-sm text-[var(--lt-text)]">
              <MapPin size={12} className="text-[var(--lt-text-dim)]" />
              <span>
                {person.mailing_address.street}, {person.mailing_address.city},{" "}
                {person.mailing_address.state} {person.mailing_address.zip_code}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
