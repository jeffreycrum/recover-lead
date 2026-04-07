const API_BASE = "/api/v1";


export interface ApiError {
  code: string;
  message: string;
}

export class ApiClient {
  private getTokenFn: (() => Promise<string | null>) | null = null;

  setTokenFn(fn: () => Promise<string | null>) {
    this.getTokenFn = fn;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    // Get a fresh token for every request (handles expiry automatically)
    const token = this.getTokenFn ? await this.getTokenFn() : null;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        error: { code: "UNKNOWN", message: "Request failed" },
      }));
      throw error.error || error;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  // Auth
  getMe() {
    return this.request<any>("/auth/me");
  }

  // Leads
  browseLeads(params: Record<string, string> = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request<any>(`/leads${qs ? `?${qs}` : ""}`);
  }

  getMyLeads(params: Record<string, string> = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request<any>(`/leads/mine${qs ? `?${qs}` : ""}`);
  }

  getLead(id: string) {
    return this.request<any>(`/leads/${id}`);
  }

  claimLead(id: string) {
    return this.request<any>(`/leads/${id}/claim`, { method: "POST" });
  }

  releaseLead(id: string) {
    return this.request<void>(`/leads/${id}/release`, { method: "POST" });
  }

  updateLead(id: string, data: { status?: string; priority?: string }) {
    return this.request<any>(`/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  qualifyLead(id: string) {
    return this.request<any>(`/leads/${id}/qualify`, { method: "POST" });
  }

  bulkQualify(leadIds: string[]) {
    return this.request<any>("/leads/bulk-qualify", {
      method: "POST",
      body: JSON.stringify(leadIds),
    });
  }

  // Letters
  generateLetter(leadId: string, letterType: string = "tax_deed") {
    return this.request<any>("/letters/generate", {
      method: "POST",
      body: JSON.stringify({ lead_id: leadId, letter_type: letterType }),
    });
  }

  generateBatch(leadIds: string[], letterType: string = "tax_deed") {
    return this.request<any>("/letters/generate-batch", {
      method: "POST",
      body: JSON.stringify({ lead_ids: leadIds, letter_type: letterType }),
    });
  }

  getLetters(params: Record<string, string> = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request<any>(`/letters${qs ? `?${qs}` : ""}`);
  }

  getLetter(id: string) {
    return this.request<any>(`/letters/${id}`);
  }

  updateLetter(id: string, data: { content?: string; status?: string }) {
    return this.request<any>(`/letters/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  deleteLetter(id: string) {
    return this.request<void>(`/letters/${id}`, { method: "DELETE" });
  }

  async downloadLetterPdf(id: string): Promise<Blob> {
    const token = this.getTokenFn ? await this.getTokenFn() : null;
    const headers: Record<string, string> = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const response = await fetch(`${API_BASE}/letters/${id}/pdf`, { headers });
    if (!response.ok) throw new Error("Failed to download PDF");
    return response.blob();
  }

  // Counties
  getCounties(params: Record<string, string> = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request<any[]>(`/counties${qs ? `?${qs}` : ""}`);
  }

  getCounty(id: string) {
    return this.request<any>(`/counties/${id}`);
  }

  // Billing
  createCheckout(plan: string, interval: string = "monthly") {
    return this.request<{ checkout_url: string }>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ plan, billing_interval: interval }),
    });
  }

  getSubscription() {
    return this.request<any>("/billing/subscription");
  }

  getBillingPortal() {
    return this.request<{ portal_url: string }>("/billing/portal");
  }

  // Skip Trace
  skipTraceLead(leadId: string) {
    return this.request<any>(`/leads/${leadId}/skip-trace`, { method: "POST" });
  }

  bulkSkipTrace(leadIds: string[]) {
    return this.request<any>("/leads/bulk-skip-trace", {
      method: "POST",
      body: JSON.stringify({ lead_ids: leadIds }),
    });
  }

  // Tasks
  getTaskStatus(taskId: string) {
    return this.request<any>(`/tasks/${taskId}`);
  }
}

export const api = new ApiClient();
