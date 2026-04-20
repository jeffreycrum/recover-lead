import { Link } from "react-router-dom";
import { siteCopy } from "@/lib/marketing-copy";
import { useTrackEvent } from "@/hooks/use-track-event";
import { ArrowRightIcon } from "./icons";

export function ClosingCta() {
  const track = useTrackEvent();
  const { headline, subheadline, primaryCta, secondaryCta } = siteCopy.closingCta;
  return (
    <section className="cta">
      <div className="wrap">
        <h2>{headline}</h2>
        <p>{subheadline}</p>
        <div
          style={{
            display: "flex",
            gap: 12,
            justifyContent: "center",
            flexWrap: "wrap",
          }}
        >
          <Link
            to="/sign-up"
            className="btn btn-primary btn-lg"
            onClick={() =>
              track("marketing.hero_cta.click", {
                variant: "primary",
                destination: "sign-up",
                source: "closing",
              })
            }
          >
            {primaryCta}
            <ArrowRightIcon />
          </Link>
          <a
            href="mailto:hello@recoverlead.com"
            className="btn btn-secondary btn-lg"
            onClick={() =>
              track("marketing.hero_cta.click", {
                variant: "secondary",
                destination: "demo",
                source: "closing",
              })
            }
          >
            {secondaryCta}
          </a>
        </div>
      </div>
    </section>
  );
}
