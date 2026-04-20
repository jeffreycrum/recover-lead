export type AnalyticsEvent = string;
export type AnalyticsProps = Record<string, unknown>;

let initialized = false;

export function initAnalytics(): void {
  if (initialized) return;
  initialized = true;
}

export function track(event: AnalyticsEvent, props?: AnalyticsProps): void {
  if (import.meta.env.DEV) {
    console.debug("[analytics]", event, props ?? {});
  }
}
