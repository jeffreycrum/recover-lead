import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { siteCopy } from "@/lib/marketing-copy";
import { useTrackEvent } from "@/hooks/use-track-event";
import { ArrowRightIcon, BrandLogo } from "./icons";

const SECTION_IDS = siteCopy.nav.items.map((i) => i.id);

export function SiteNav() {
  const track = useTrackEvent();
  const [scrolled, setScrolled] = useState(false);
  const [active, setActive] = useState<string>(SECTION_IDS[0]);

  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 10);
      for (const id of SECTION_IDS) {
        const el = document.getElementById(id);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top < 120 && rect.bottom > 120) {
          setActive(id);
          break;
        }
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleSignInClick = () => {
    track("marketing.nav_cta.click", { destination: "sign-in" });
    track("marketing.signin_intent", { source: "nav" });
  };

  const handlePrimaryClick = () => {
    track("marketing.nav_cta.click", { destination: "sign-up" });
  };

  return (
    <header className={`nav ${scrolled ? "scrolled" : ""}`}>
      <div className="wrap nav-inner">
        <Link to="/" aria-label={siteCopy.brand.name}>
          <BrandLogo />
        </Link>
        <nav className="nav-pill" aria-label="Page sections">
          {siteCopy.nav.items.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              aria-current={active === item.id ? "true" : undefined}
              className={active === item.id ? "active" : ""}
            >
              {"liveDot" in item && item.liveDot && (
                <span className="dot" aria-hidden="true" />
              )}
              {item.label}
            </a>
          ))}
        </nav>
        <div className="nav-right">
          <Button
            nativeButton={false}
            render={<Link to="/sign-in" onClick={handleSignInClick} />}
            variant="ghost"
            className="btn btn-ghost"
          >
            {siteCopy.nav.signIn}
          </Button>
          <Button
            nativeButton={false}
            render={<Link to="/sign-up" onClick={handlePrimaryClick} />}
            className="btn btn-primary"
          >
            {siteCopy.nav.primaryCta}
            <ArrowRightIcon />
          </Button>
        </div>
      </div>
    </header>
  );
}
