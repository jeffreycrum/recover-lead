export type AnalyticsEvent =
  | "marketing.nav_cta.click"
  | "marketing.signin_intent"
  | "marketing.hero_cta.click";
export type AnalyticsProps = Record<string, unknown>;

let initialized = false;
const DEV_LOGGABLE_ANALYTICS_KEYS = new Set(["destination", "variant"]);

function sanitizeAnalyticsProps(props?: AnalyticsProps): AnalyticsProps | undefined {
  if (!props) return undefined;

  const safeEntries = Object.entries(props).filter(([key]) =>
    DEV_LOGGABLE_ANALYTICS_KEYS.has(key),
  );

  if (safeEntries.length === 0) {
    return undefined;
  }

  return Object.fromEntries(safeEntries);
}

export function initAnalytics(): void {
  if (initialized) return;
  initialized = true;
}

export function track(event: AnalyticsEvent, props?: AnalyticsProps): void {
  if (import.meta.env.DEV) {
    const safeProps = sanitizeAnalyticsProps(props);
    if (safeProps) {
      console.debug("[analytics]", event, safeProps);
      return;
    }

    console.debug("[analytics]", event);
  }
}
