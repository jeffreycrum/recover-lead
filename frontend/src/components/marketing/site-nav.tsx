import { Link } from "react-router-dom";
import { siteCopy } from "@/lib/marketing-copy";
import { useTrackEvent } from "@/hooks/use-track-event";
import { CtaButton } from "./cta-button";

export function SiteNav() {
  const track = useTrackEvent();
  const handleSignInClick = () => {
    track("marketing.nav_cta.click", { destination: "sign-in" });
    track("marketing.signin_intent", { source: "nav" });
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border/40 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link to="/" className="text-lg font-bold tracking-tight">
          <span className="text-emerald">Recover</span>
          {siteCopy.brand.name.replace("Recover", "")}
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            to="/sign-in"
            onClick={handleSignInClick}
            className="text-sm font-medium text-foreground hover:text-emerald"
          >
            {siteCopy.nav.signIn}
          </Link>
          <CtaButton
            to="/sign-up"
            variant="primary"
            event="marketing.nav_cta.click"
            eventProps={{ destination: "sign-up" }}
            className="px-4 py-2 text-sm"
          >
            {siteCopy.nav.signUp}
          </CtaButton>
        </nav>
      </div>
    </header>
  );
}
