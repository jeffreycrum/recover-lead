import { Phone, Mail, MapPin, AlertTriangle, Shield, User, Skull, Search } from "lucide-react";

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

function formatRunTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function PersonCard({ person, keyPrefix }: { person: PersonData; keyPrefix: string }) {
  return (
    <div
      key={keyPrefix}
      className="space-y-3 rounded-[14px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.015)] p-3"
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
          {person.phones.map((phone) => (
            <div key={phone.number} className="flex flex-wrap items-center gap-2 text-sm text-[var(--lt-text)]">
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
          {person.emails.map((email) => (
            <div key={email.email} className="flex items-center gap-2 text-sm text-[var(--lt-text)]">
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
  );
}

function RunCard({ run }: { run: SkipTraceResult }) {
  const timestamp = formatRunTimestamp(run.created_at);
  const isMiss = run.status === "miss" || run.persons.length === 0;

  return (
    <div className="rounded-[18px] border border-[var(--lt-line)] bg-[rgba(255,255,255,0.01)] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Search size={12} className="text-[var(--lt-text-dim)]" />
          <span className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--lt-text-muted)]">
            {run.provider}
          </span>
          <span
            className={`rounded-md px-2 py-0.5 text-xs ${
              isMiss
                ? "bg-[rgba(148,163,184,0.12)] text-[var(--lt-text-muted)]"
                : "bg-[var(--lt-emerald-dim)] text-[var(--lt-emerald-light)]"
            }`}
          >
            {isMiss ? "No matches" : `${run.persons.length} match${run.persons.length === 1 ? "" : "es"}`}
          </span>
        </div>
        <span className="text-xs text-[var(--lt-text-muted)]">{timestamp}</span>
      </div>

      {isMiss ? (
        <p className="text-sm text-[var(--lt-text-muted)]">
          No contact information found on this run.
        </p>
      ) : (
        <div className="space-y-3">
          {run.persons.map((person, i) => (
            <PersonCard
              key={`${run.id}-${i}`}
              person={person}
              keyPrefix={`${run.id}-${person.full_name || `${person.first_name}-${person.last_name}-${i}`}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function SkipTraceResults({ results }: { results: SkipTraceResult[] }) {
  if (!results || results.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-[var(--lt-text)]">
          Skip Trace Results
        </h4>
        <span className="text-xs text-[var(--lt-text-muted)]">
          {results.length} run{results.length === 1 ? "" : "s"}
        </span>
      </div>
      {/* Render every run, most recent first. Multiple lookups (address,
          parcel, name-only) accumulate so users can compare and pull
          contacts from any run. */}
      <div className="space-y-3">
        {results.map((run) => (
          <RunCard key={run.id} run={run} />
        ))}
      </div>
    </div>
  );
}
