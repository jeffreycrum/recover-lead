import { useAuth } from "@clerk/clerk-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/lib/api";

function useApiToken() {
  const { getToken } = useAuth();
  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);
}

export function useBrowseLeads(params: Record<string, string> = {}) {
  useApiToken();
  return useQuery({
    queryKey: ["leads", "browse", params],
    queryFn: () => api.browseLeads(params),
  });
}

export function useMyLeads(params: Record<string, string> = {}) {
  useApiToken();
  return useQuery({
    queryKey: ["leads", "mine", params],
    queryFn: () => api.getMyLeads(params),
  });
}

export function useLead(id: string) {
  useApiToken();
  return useQuery({
    queryKey: ["leads", id],
    queryFn: () => api.getLead(id),
    enabled: !!id,
  });
}

export function useClaimLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.claimLead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useReleaseLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.releaseLead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useUpdateLead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { status?: string; priority?: string } }) =>
      api.updateLead(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useQualifyLead() {
  return useMutation({
    mutationFn: (id: string) => api.qualifyLead(id),
  });
}
