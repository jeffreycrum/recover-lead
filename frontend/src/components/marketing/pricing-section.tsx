import { Link } from "react-router-dom";
import { siteCopy } from "@/lib/marketing-copy";
import { useTrackEvent } from "@/hooks/use-track-event";
import { CheckIcon } from "./icons";

export function PricingSection() {
  const track = useTrackEvent();
  const { eyebrow, headline, subheadline, plans } = siteCopy.pricing;
  return (
    <section className="section" id="pricing">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title">{headline}</h2>
          <p className="section-sub">{subheadline}</p>
        </div>
        <div className="price-grid">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`price-card ${p.featured ? "featured" : ""}`}
              data-testid="pricing-plan"
            >
              <div className="price-tier">{p.tier}</div>
              <div className="price-name">{p.name}</div>
              <div className="price-desc">{p.desc}</div>
              <div className="price-amt">
                <span className="n">${p.price}</span>
                <span className="p">/ month</span>
              </div>
              <ul className="price-feats">
                {p.feats.map((f, i) => (
                  <li key={i}>
                    <CheckIcon />
                    <span>
                      <b>{f.a}</b>
                      {f.b}
                    </span>
                  </li>
                ))}
              </ul>
              <Link
                to={`/checkout?plan=${p.name.toLowerCase()}`}
                className={`btn ${p.featured ? "btn-primary" : "btn-secondary"}`}
                style={{ justifyContent: "center" }}
                onClick={() =>
                  track("marketing.hero_cta.click", {
                    variant: p.featured ? "primary" : "secondary",
                    destination: "checkout",
                    plan: p.name,
                  })
                }
              >
                Start with {p.name}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
