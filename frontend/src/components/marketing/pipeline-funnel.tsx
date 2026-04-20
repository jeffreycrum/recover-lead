import { siteCopy } from "@/lib/marketing-copy";
import { ArrowRightIcon } from "./icons";

export function PipelineFunnel() {
  const { eyebrow, headline, subheadline, cta, caption, delta, rows } =
    siteCopy.pipeline;
  return (
    <section
      className="section"
      style={{
        background:
          "linear-gradient(180deg, transparent, rgba(16,185,129,0.02) 50%, transparent)",
      }}
    >
      <div className="wrap funnel-wrap">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title" style={{ textAlign: "left" }}>
            {headline}
          </h2>
          <p
            className="section-sub"
            style={{ textAlign: "left", maxWidth: 500, marginBottom: 28 }}
          >
            {subheadline}
          </p>
          <a href="#how" className="btn btn-secondary btn-lg">
            {cta} <ArrowRightIcon />
          </a>
        </div>
        <div
          style={{
            background: "var(--lt-surface)",
            border: "1px solid var(--lt-line)",
            borderRadius: 16,
            padding: 32,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: 24,
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "var(--lt-text-dim)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              {caption}
            </div>
            <div
              style={{
                fontFamily: "JetBrains Mono, ui-monospace, monospace",
                fontSize: 13,
                color: "var(--lt-emerald)",
              }}
            >
              {delta}
            </div>
          </div>
          <div className="funnel">
            {rows.map((row) => (
              <div className="funnel-row" key={row.name}>
                <div className="name">{row.name}</div>
                <div className="bar-wrap">
                  <div
                    className="bar"
                    style={{ width: `${row.widthPct}%`, opacity: row.opacity }}
                  >
                    {row.pct}
                  </div>
                </div>
                <div className="count">{row.count}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
