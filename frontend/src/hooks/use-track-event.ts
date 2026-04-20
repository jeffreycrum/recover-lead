import { useCallback } from "react";
import {
  track,
  type AnalyticsEvent,
  type AnalyticsProps,
} from "@/lib/analytics";

export function useTrackEvent() {
  return useCallback((event: AnalyticsEvent, props?: AnalyticsProps) => {
    track(event, props);
  }, []);
}
