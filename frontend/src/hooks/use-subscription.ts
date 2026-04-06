import { useAuth } from "@clerk/clerk-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "@/lib/api";

export function useSubscription() {
  const { getToken } = useAuth();
  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  return useQuery({
    queryKey: ["subscription"],
    queryFn: () => api.getSubscription(),
  });
}

export function useCounties() {
  const { getToken } = useAuth();
  useEffect(() => {
    api.setTokenFn(getToken);
  }, [getToken]);

  return useQuery({
    queryKey: ["counties"],
    queryFn: () => api.getCounties(),
  });
}
