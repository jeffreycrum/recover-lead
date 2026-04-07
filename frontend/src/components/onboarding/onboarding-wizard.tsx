import { useState, useEffect } from "react";
import { useAuth } from "@clerk/clerk-react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useCounties } from "@/hooks/use-subscription";
import { formatCurrency } from "@/lib/utils";
import { LeadScoreBadge } from "@/components/leads/lead-score-badge";
import { Map, Zap, FileText, Download, ArrowRight, CheckCircle, Loader2 } from "lucide-react";

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

export function OnboardingWizard({ onComplete }: { onComplete: () => void }) {
  const { getToken } = useAuth();
  const navigate = useNavigate();
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

  const activeCounties = counties?.filter((c: any) => c.is_active && c.lead_count > 0) ?? [];

  const handleSelectCounty = async (countyId: string, name: string) => {
    setSelectedCounty(countyId);
    setSelectedCountyName(name);
    setStep("qualifying");

    // Fetch top leads from this county
    try {
      const data = await api.browseLeads({
        county_id: countyId,
        limit: "10",
      });

      const topLeads: WizardLead[] = (data.items || []).map((l: any) => ({
        id: l.id,
        case_number: l.case_number,
        owner_name: l.owner_name,
        surplus_amount: l.surplus_amount,
        property_address: l.property_address,
        property_city: l.property_city,
        quality_score: null,
      }));

      setLeads(topLeads);
      setQualifyProgress({ done: 0, total: topLeads.length });

      // Claim and qualify each lead
      for (let i = 0; i < topLeads.length; i++) {
        try {
          await api.claimLead(topLeads[i].id);
          const result = await api.qualifyLead(topLeads[i].id);
          // Poll for completion
          if (result.task_id && result.task_id !== "placeholder") {
            await pollTask(result.task_id);
          }
          // Refresh lead data
          const detail = await api.getLead(topLeads[i].id);
          if (detail.user_lead?.quality_score) {
            topLeads[i].quality_score = detail.user_lead.quality_score;
          }
        } catch {
          // Continue with next lead on error
        }
        setQualifyProgress({ done: i + 1, total: topLeads.length });
        setLeads([...topLeads]);
      }

      // Sort by score descending
      topLeads.sort((a, b) => (b.quality_score ?? 0) - (a.quality_score ?? 0));
      setLeads([...topLeads]);
      setStep("results");
    } catch {
      // If fetching fails, show results with what we have
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
        // Use the letter_id from the task result directly
        if (taskResult?.letter_id) {
          setGeneratedLetterId(taskResult.letter_id);
        }
      }
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
      await new Promise((r) => setTimeout(r, 2000));
      const status = await api.getTaskStatus(taskId);
      if (status.status === "SUCCESS") return status.result;
      if (status.status === "FAILURE") return null;
    }
    return null;
  };

  const steps = [
    { key: "county", label: "Select County", icon: Map },
    { key: "qualifying", label: "Qualifying", icon: Zap },
    { key: "results", label: "Top Leads", icon: CheckCircle },
    { key: "letter", label: "Generate Letter", icon: FileText },
    { key: "done", label: "Download", icon: Download },
  ];

  const currentStepIndex = steps.findIndex((s) => s.key === step);

  return (
    <div className="max-w-3xl mx-auto">
      {/* Step indicator */}
      <div className="flex items-center justify-between mb-8">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center">
            <div
              className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium ${
                i <= currentStepIndex
                  ? "bg-emerald text-white"
                  : "bg-gray-200 text-gray-500"
              }`}
            >
              {i < currentStepIndex ? (
                <CheckCircle size={16} />
              ) : (
                <s.icon size={16} />
              )}
            </div>
            {i < steps.length - 1 && (
              <div
                className={`w-16 h-0.5 mx-2 ${
                  i < currentStepIndex ? "bg-emerald" : "bg-gray-200"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      {step === "county" && (
        <div>
          <h2 className="text-xl font-bold mb-2">Select Your County</h2>
          <p className="text-muted-foreground mb-6">
            Choose a Florida county to see qualified surplus fund leads.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {activeCounties.map((county: any) => (
              <button
                key={county.id}
                onClick={() => handleSelectCounty(county.id, county.name)}
                className="p-4 text-left bg-white border rounded-lg hover:border-emerald transition-colors"
              >
                <p className="font-medium">{county.name}</p>
                <p className="text-sm text-muted-foreground">
                  {county.lead_count.toLocaleString()} leads
                </p>
              </button>
            ))}
          </div>
          {activeCounties.length === 0 && (
            <p className="text-center text-muted-foreground py-8">
              Loading counties...
            </p>
          )}
        </div>
      )}

      {step === "qualifying" && (
        <div className="text-center py-8">
          <Loader2 size={48} className="animate-spin text-emerald mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">
            Qualifying leads in {selectedCountyName}
          </h2>
          <p className="text-muted-foreground mb-4">
            Our AI is scoring each lead on recovery potential...
          </p>
          <div className="w-64 mx-auto">
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald rounded-full transition-all duration-500"
                style={{
                  width: `${
                    qualifyProgress.total > 0
                      ? (qualifyProgress.done / qualifyProgress.total) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              {qualifyProgress.done} / {qualifyProgress.total} leads
            </p>
          </div>
        </div>
      )}

      {step === "results" && (
        <div>
          <h2 className="text-xl font-bold mb-2">
            Top Leads in {selectedCountyName}
          </h2>
          <p className="text-muted-foreground mb-6">
            Select a lead to generate a personalized outreach letter.
          </p>
          <div className="space-y-2">
            {leads.map((lead) => (
              <div
                key={lead.id}
                className="flex items-center justify-between p-4 bg-white border rounded-lg hover:border-emerald transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">
                      {lead.case_number}
                    </span>
                    <LeadScoreBadge score={lead.quality_score} />
                  </div>
                  <p className="font-medium mt-1">{lead.owner_name || "Unknown Owner"}</p>
                  <p className="text-sm text-muted-foreground">
                    {lead.property_address}
                    {lead.property_city ? `, ${lead.property_city}` : ""}
                  </p>
                </div>
                <div className="text-right ml-4">
                  <p className="font-bold text-emerald">
                    {formatCurrency(lead.surplus_amount)}
                  </p>
                  <button
                    onClick={() => handleGenerateLetter(lead.id)}
                    className="mt-2 px-3 py-1.5 text-xs bg-emerald text-white rounded hover:bg-emerald/90 flex items-center gap-1"
                  >
                    Generate Letter <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {step === "letter" && (
        <div className="text-center py-8">
          <Loader2 size={48} className="animate-spin text-emerald mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Generating your letter</h2>
          <p className="text-muted-foreground">
            AI is writing a personalized outreach letter...
          </p>
        </div>
      )}

      {step === "done" && (
        <div className="text-center py-8">
          <CheckCircle size={48} className="text-emerald mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Your letter is ready!</h2>
          <p className="text-muted-foreground mb-6">
            Review, edit, and download your personalized outreach letter.
          </p>
          <div className="flex items-center justify-center gap-3">
            {generatedLetterId && (
              <button
                onClick={handleDownloadPdf}
                className="px-6 py-2.5 bg-emerald text-white rounded-md hover:bg-emerald/90 flex items-center gap-2"
              >
                <Download size={16} /> Download PDF
              </button>
            )}
            <button
              onClick={() => {
                onComplete();
                navigate("/letters");
              }}
              className="px-6 py-2.5 border rounded-md hover:bg-gray-50"
            >
              View All Letters
            </button>
          </div>
          <button
            onClick={onComplete}
            className="mt-4 text-sm text-muted-foreground hover:text-foreground"
          >
            Skip to dashboard
          </button>
        </div>
      )}
    </div>
  );
}
