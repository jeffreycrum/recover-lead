import { Link } from "react-router-dom";
import { siteCopy } from "@/lib/marketing-copy";
import { useTrackEvent } from "@/hooks/use-track-event";
import { ArrowRightIcon, CheckIcon, MailIcon } from "./icons";

export function HeroSection() {
  const track = useTrackEvent();
  const {
    badge,
    headlineLead,
    headlineGradient,
    subheadline,
    primaryCta,
    secondaryCta,
    proof,
    productCard,
    callouts,
  } = siteCopy.hero;

  const firePrimary = () =>
    track("marketing.hero_cta.click", { variant: "primary", destination: "sign-up" });
  const fireSecondary = () =>
    track("marketing.hero_cta.click", { variant: "secondary", destination: "how" });

  return (
    <section className="hero" id="product">
      <div className="wrap hero-grid">
        <div>
          <div className="badge">
            <span className="chip">{badge.chip}</span>
            <span>{badge.label}</span>
          </div>
          <h1 className="hero-title">
            {headlineLead}{" "}
            <span className="gradient">{headlineGradient}</span>
          </h1>
          <p className="hero-sub">{subheadline}</p>
          <div className="hero-cta">
            <Link
              to="/sign-up"
              className="btn btn-primary btn-lg"
              onClick={firePrimary}
            >
              {primaryCta}
              <ArrowRightIcon />
            </Link>
            <a
              href="#how"
              className="btn btn-secondary btn-lg"
              onClick={fireSecondary}
            >
              {secondaryCta}
            </a>
          </div>
          <div className="hero-proof">
            {proof.map((p) => (
              <div className="proof" key={p.label}>
                <div className="num">{p.num}</div>
                <div className="lbl">{p.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ position: "relative" }}>
          <div className="product-card">
            <div className="pc-head">
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div className="pc-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="title">{productCard.title}</span>
              </div>
              <span
                className="mono"
                style={{ fontSize: 11, color: "var(--lt-text-dim)" }}
              >
                {productCard.meta}
              </span>
            </div>
            <div className="pc-body">
              {productCard.rows.map((row) => (
                <div
                  key={row.name}
                  className={`pc-row ${"highlight" in row && row.highlight ? "highlight" : ""}`}
                >
                  <div className="pc-owner">
                    <span className="name">{row.name}</span>
                    <span className="meta">{row.meta}</span>
                  </div>
                  <span className="pc-amount">{row.amount}</span>
                  <span className={`pc-score ${row.scoreHi ? "hi" : ""}`}>
                    {row.score}
                  </span>
                  <span
                    className={`pc-status ${row.qualified ? "qualified" : ""}`}
                  >
                    {row.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="callout callout-1">
            <div
              className="ico"
              style={{
                background: "var(--lt-emerald-dim)",
                color: "var(--lt-emerald)",
              }}
            >
              <CheckIcon />
            </div>
            <div>
              <strong>{callouts[0].title}</strong>
              <div className="sub">{callouts[0].sub}</div>
            </div>
          </div>
          <div className="callout callout-2">
            <div
              className="ico"
              style={{
                background: "rgba(59,130,246,0.15)",
                color: "#60a5fa",
              }}
            >
              <MailIcon />
            </div>
            <div>
              <strong>{callouts[1].title}</strong>
              <div className="sub">{callouts[1].sub}</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
