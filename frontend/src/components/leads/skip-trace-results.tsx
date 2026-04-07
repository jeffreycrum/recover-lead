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
      <div className="mt-4 p-4 bg-gray-50 border rounded-lg">
        <p className="text-sm text-muted-foreground">
          No contact information found. Try a premium lookup for better results.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">Skip Trace Results</h4>
        <span className="text-xs text-muted-foreground">
          via {latest.provider} &middot; {new Date(latest.created_at).toLocaleDateString()}
        </span>
      </div>

      {latest.persons.map((person, i) => (
        <div key={i} className="p-4 bg-white border rounded-lg space-y-3">
          {/* Person header */}
          <div className="flex items-center gap-2 flex-wrap">
            <User size={14} className="text-muted-foreground" />
            <span className="font-medium">{person.full_name || `${person.first_name} ${person.last_name}`}</span>
            {person.age && (
              <span className="text-xs text-muted-foreground">Age {person.age}</span>
            )}
            {person.property_owner && (
              <span className="px-1.5 py-0.5 text-xs bg-emerald/10 text-emerald rounded">Owner</span>
            )}
            {person.deceased && (
              <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded flex items-center gap-1">
                <Skull size={10} /> Deceased
              </span>
            )}
            {person.litigator && (
              <span className="px-1.5 py-0.5 text-xs bg-amber-100 text-amber-700 rounded flex items-center gap-1">
                <Shield size={10} /> TCPA Litigator
              </span>
            )}
          </div>

          {/* Phones */}
          {person.phones.length > 0 && (
            <div className="space-y-1">
              {person.phones.map((phone, j) => (
                <div key={j} className="flex items-center gap-2 text-sm">
                  <Phone size={12} className="text-muted-foreground" />
                  <span className="font-mono">{phone.number}</span>
                  <span className="px-1.5 py-0.5 text-xs bg-gray-100 rounded">
                    {phone.type || "unknown"}
                  </span>
                  {phone.carrier && (
                    <span className="text-xs text-muted-foreground">{phone.carrier}</span>
                  )}
                  {phone.dnc && (
                    <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-600 rounded flex items-center gap-1">
                      <AlertTriangle size={10} /> DNC
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Emails */}
          {person.emails.length > 0 && (
            <div className="space-y-1">
              {person.emails.map((email, j) => (
                <div key={j} className="flex items-center gap-2 text-sm">
                  <Mail size={12} className="text-muted-foreground" />
                  <span>{email.email}</span>
                </div>
              ))}
            </div>
          )}

          {/* Mailing address */}
          {person.mailing_address && person.mailing_address.street && (
            <div className="flex items-center gap-2 text-sm">
              <MapPin size={12} className="text-muted-foreground" />
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
