import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";

const CHECKOUT_PLANS = new Set(["starter", "pro", "agency"]);
const CHECKOUT_INTERVALS = new Set(["monthly", "annual"]);

export const checkoutRedirect = {
  go(url: string) {
    window.location.assign(url);
  },
};

export function CheckoutHandoffPage() {
  const [searchParams] = useSearchParams();
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const plan = searchParams.get("plan");
  const interval = searchParams.get("interval") ?? "monthly";

  useEffect(() => {
    let isCancelled = false;

    async function startCheckout() {
      if (!plan || !CHECKOUT_PLANS.has(plan)) {
        setErrorMessage("Select a paid plan before continuing to checkout.");
        return;
      }

      if (!CHECKOUT_INTERVALS.has(interval)) {
        setErrorMessage("Choose a valid billing interval before checkout.");
        return;
      }

      try {
        const { checkout_url } = await api.createCheckout(plan, interval);

        if (!checkout_url) {
          throw new Error("Missing checkout URL");
        }

        if (isCancelled) {
          return;
        }

        setCheckoutUrl(checkout_url);
        checkoutRedirect.go(checkout_url);
      } catch (error) {
        console.error("checkout_handoff_failed", error);
        if (!isCancelled) {
          setErrorMessage("We couldn't start checkout right now. Try again from Settings.");
        }
      }
    }

    void startCheckout();

    return () => {
      isCancelled = true;
    };
  }, [interval, plan]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md space-y-4 px-6 text-center">
        <p className="text-muted-foreground">Redirecting to checkout…</p>
        {checkoutUrl ? (
          <a
            href={checkoutUrl}
            className="inline-flex text-sm font-medium text-emerald hover:underline"
          >
            Continue to checkout
          </a>
        ) : null}
        {errorMessage ? (
          <div className="space-y-3">
            <p className="text-sm text-destructive">{errorMessage}</p>
            <Link
              to="/settings"
              className="inline-flex text-sm font-medium text-emerald hover:underline"
            >
              Return to settings
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  );
}
