import { useState, useEffect } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCounties } from "@/hooks/use-subscription";
import { formatCurrency } from "@/lib/utils";
import { LeadScoreBadge } from "@/components/leads/lead-score-badge";
import { Map, Zap, FileText, Download, ArrowRight, CheckCircle, Loader2 } from "lucide-react";
import { EyebrowTag, MonoCell, ProductCard } from "@/components/landing-chrome";

type Step = "county" | "qualifying" | "results" | "letter" | "done";

interface WizardLead {
  id: string;
  case_number: string;
  owner_name: string | null;
  surplus_amount: number;
  property_address: string | null;
  property_city: string | null;
  quality_score: number | null;
}

const primaryButtonClass =
  "inline-flex items-center justify-center gap-2 rounded-full bg-[var(--lt-emerald)] px-4 py-2 text-sm font-semibold text-[#042014] transition-all hover:bg-[var(--lt-emerald-light)]";
const secondaryButtonClass =
  "inline-flex items-center justify-center rounded-full border border-[var(--lt-line)] bg-[var(--lt-surface)] px-4 py-2 text-sm font-medium text-[var(--lt-text)] transition-colors hover:bg-[var(--lt-surface-2)]";

export function OnboardingWizard({ onComplete }: { onComplete: () => void }) {
  const { getToken } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: counties } = useCounties();
  const [step, setStep] = useState<Step>("county");
  const [_selectedCounty, setSelectedCounty] = useState<string | null>(null);
  const [selectedCountyName, setSelectedCountyName] = useState("");
  const [leads, setLeads] = useState<WizardLead[]>([]);
  const [qualifyProgress, setQualifyProgress] = useState({ done: 0, total: 0 });
  const [generatedLetterId, setGeneratedLetterId] = useState<string | null>(null);
  const [_selectedLeadId, setSelectedLeadId] = useState<string | null>(null);

  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  const activeCounties = counties?.filter((county: any) => county.is_active && county.lead_count > 0) ?? [];

  const handleSelectCounty = async (countyId: string, name: string) => {
    setSelectedCounty(countyId);
    setSelectedCountyName(name);
    setStep("qualifying");

    try {
      const data = await api.browseLeads({
        county_id: countyId,
        limit: "10",
      });

      const topLeads: WizardLead[] = (data.items || []).map((lead: any) => ({
        id: lead.id,
        case_number: lead.case_number,
        owner_name: lead.owner_name,
        surplus_amount: lead.surplus_amount,
        property_address: lead.property_address,
        property_city: lead.property_city,
        quality_score: null,
      }));

      setLeads(topLeads);
      setQualifyProgress({ done: 0, total: topLeads.length });

      for (let i = 0; i < topLeads.length; i++) {
        try {
          await api.claimLead(topLeads[i].id);
          const result = await api.qualifyLead(topLeads[i].id);
          if (result.task_id && result.task_id !== "placeholder") {
            await pollTask(result.task_id);
          }
          const detail = await api.getLead(topLeads[i].id);
          if (detail.user_lead?.quality_score) {
            topLeads[i].quality_score = detail.user_lead.quality_score;
          }
        } catch {
          // Continue with next lead on error.
        }
        setQualifyProgress({ done: i + 1, total: topLeads.length });
        setLeads([...topLeads]);
      }

      topLeads.sort((a, b) => (b.quality_score ?? 0) - (a.quality_score ?? 0));
      setLeads([...topLeads]);
      setStep("results");
    } catch {
      setStep("results");
    }
  };

  const handleGenerateLetter = async (leadId: string) => {
    setSelectedLeadId(leadId);
    setStep("letter");
    try {
      const result = await api.generateLetter(leadId);
      if (result.task_id) {
        const taskResult = await pollTask(result.task_id);
        if (taskResult?.letter_id) {
          setGeneratedLetterId(taskResult.letter_id);
        }
      }
      qc.invalidateQueries({ queryKey: ["letters"] });
      setStep("done");
    } catch {
      setStep("done");
    }
  };

  const handleDownloadPdf = async () => {
    if (!generatedLetterId) return;
    const blob = await api.downloadLetterPdf(generatedLetterId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "letter.pdf";
    a.click();
    URL.revokeObjectURL(url);
  };

  const pollTask = async (taskId: string, maxAttempts = 30): Promise<any> => {
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const status = await api.getTaskStatus(taskId);
      if (status.status === "SUCCESS") return status.result;
      if (status.status === "FAILURE") return null;
    }
    return null;
  };

  const steps = [
    { key: "county", label: "County", icon: Map },
    { key: "qualifying", label: "Qualify", icon: Zap },
    { key: "results", label: "Results", icon: CheckCircle },
    { key: "letter", label: "Letter", icon: FileText },
    { key: "done", label: "Download", icon: Download },
  ];

  const currentStepIndex = steps.findIndex((item) => item.key === step);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8 grid grid-cols-5 gap-2">
        {steps.map((item, index) => (
          <div key={item.key} className="flex flex-col items-center gap-2 text-center">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-medium ${
                index <= currentStepIndex
                  ? "bg-[var(--lt-emerald)] text-[#042014]"
                  : "bg-[rgba(148,163,184,0.14)] text-[var(--lt-text-dim)]"
              }`}
            >
              {index < currentStepIndex ? <CheckCircle size={16} /> : <item.icon size={16} />}
            </div>
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--lt-text-dim)]">
              {item.label}
            </span>
          </div>
        ))}
      </div>

      {step === "county" && (
        <div>
          <EyebrowTag>Step 1</EyebrowTag>
          <h2 className="mb-2 mt-4 text-xl font-bold text-[var(--lt-text)]">Select Your County</h2>
          <p className="mb-6 text-[var(--lt-text-muted)]">
            Choose a Florida county to see qualified surplus fund leads.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {activeCounties.map((county: any) => (
              <ProductCard
                key={county.id}
                as="button"
                type="button"
                heading={county.name}
                subtitle={`${county.lead_count.toLocaleString()} leads`}
                onClick={() => handleSelectCounty(county.id, county.name)}
                className="text-left transition-transform hover:-translate-y-0.5"
              >
                <p className="text-sm text-[var(--lt-text-muted)]">
                  Start by qualifying the top county leads automatically.
                </p>
              </ProductCard>
            ))}
          </div>
          {activeCounties.length === 0 && (
            <p className="py-8 text-center text-[var(--lt-text-muted)]">
              {counties
                ? "No active counties are available yet. Check back after county data finishes syncing."
                : "Loading counties..."}
            </p>
          )}
        </div>
      )}

      {step === "qualifying" && (
        <div className="py-8 text-center">
          <Loader2 size={48} className="mx-auto mb-4 animate-spin text-emerald" />
          <h2 className="mb-2 text-xl font-bold text-[var(--lt-text)]">
            Qualifying leads in {selectedCountyName}
          </h2>
          <p className="mb-4 text-[var(--lt-text-muted)]">
            Our AI is scoring each lead on recovery potential...
          </p>
          <div className="mx-auto w-64">
            <div className="h-3 overflow-hidden rounded-full bg-[rgba(148,163,184,0.12)]">
              <div
                className="h-full rounded-full bg-[var(--lt-emerald)] transition-all duration-500"
                style={{
                  width: `${
                    qualifyProgress.total > 0
                      ? (qualifyProgress.done / qualifyProgress.total) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
            <p className="mt-2 text-sm text-[var(--lt-text-muted)]">
              {qualifyProgress.done} / {qualifyProgress.total} leads
            </p>
          </div>
        </div>
      )}

      {step === "results" && (
        <div>
          <EyebrowTag>Step 3</EyebrowTag>
          <h2 className="mb-2 mt-4 text-xl font-bold text-[var(--lt-text)]">
            Top Leads in {selectedCountyName}
          </h2>
          <p className="mb-6 text-[var(--lt-text-muted)]">
            Select a lead to generate a personalized outreach letter.
          </p>
          <div className="space-y-2">
            {leads.map((lead) => (
              <ProductCard key={lead.id} className="transition-transform hover:-translate-y-0.5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-[var(--lt-text-muted)]">
                        {lead.case_number}
                      </span>
                      <LeadScoreBadge score={lead.quality_score} />
                    </div>
                    <p className="mt-1 font-medium text-[var(--lt-text)]">
                      {lead.owner_name || "Unknown Owner"}
                    </p>
                    <p className="text-sm text-[var(--lt-text-muted)]">
                      {lead.property_address
                        ? `${lead.property_address}${lead.property_city ? `, ${lead.property_city}` : ""}`
                        : "Address not on file"}
                    </p>
                  </div>
                  <div className="flex flex-col items-start gap-2 sm:items-end">
                    <MonoCell tone="emerald">{formatCurrency(lead.surplus_amount)}</MonoCell>
                    <button
                      onClick={() => handleGenerateLetter(lead.id)}
                      className={`${primaryButtonClass} text-xs`}
                    >
                      Generate Letter <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              </ProductCard>
            ))}
          </div>
        </div>
      )}

      {step === "letter" && (
        <div className="py-8 text-center">
          <Loader2 size={48} className="mx-auto mb-4 animate-spin text-emerald" />
          <h2 className="mb-2 text-xl font-bold text-[var(--lt-text)]">Generating your letter</h2>
          <p className="text-[var(--lt-text-muted)]">
            AI is writing a personalized outreach letter...
          </p>
        </div>
      )}

      {step === "done" && (
        <div className="py-8 text-center">
          <CheckCircle size={48} className="mx-auto mb-4 text-emerald" />
          <h2 className="mb-2 text-xl font-bold text-[var(--lt-text)]">Your letter is ready!</h2>
          <p className="mb-6 text-[var(--lt-text-muted)]">
            Review, edit, and download your personalized outreach letter.
          </p>
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            {generatedLetterId && (
              <button onClick={handleDownloadPdf} className={primaryButtonClass}>
                <Download size={16} /> Download PDF
              </button>
            )}
            <button
              onClick={() => {
                onComplete();
                navigate("/letters");
              }}
              className={secondaryButtonClass}
            >
              View All Letters
            </button>
          </div>
          <button
            onClick={onComplete}
            className="mt-4 text-sm text-[var(--lt-text-muted)] transition-colors hover:text-[var(--lt-text)]"
          >
            Skip to dashboard
          </button>
        </div>
      )}
    </div>
  );
}
