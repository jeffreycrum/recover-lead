import { siteCopy } from "@/lib/marketing-copy";
import { ArrowRightIcon } from "./icons";

export function CountiesCoverage() {
  const { eyebrow, headline, subheadline, cta, proof, vizTitle, groups, pending } =
    siteCopy.counties;
  return (
    <section
      className="section"
      id="counties"
      style={{
        background: "var(--lt-bg-2)",
        borderTop: "1px solid var(--lt-line)",
        borderBottom: "1px solid var(--lt-line)",
      }}
    >
      <div className="wrap map-grid">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title" style={{ textAlign: "left" }}>
            {headline}
          </h2>
          <p
            className="section-sub"
            style={{ textAlign: "left", marginBottom: 24 }}
          >
            {subheadline}
          </p>
          <div
            style={{
              display: "flex",
              gap: 32,
              flexWrap: "wrap",
              marginBottom: 24,
            }}
          >
            {proof.map((p) => (
              <div className="proof" key={p.label}>
                <div className="num">{p.num}</div>
                <div className="lbl">{p.label}</div>
              </div>
            ))}
          </div>
          <a href="#pricing" className="btn btn-secondary">
            {cta} <ArrowRightIcon />
          </a>
        </div>
        <div className="map-viz">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 13, color: "var(--lt-text-muted)" }}>
              {vizTitle}
            </div>
            <div
              style={{
                display: "flex",
                gap: 14,
                fontSize: 11,
                color: "var(--lt-text-dim)",
              }}
            >
              <span
                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: "var(--lt-emerald)",
                    display: "inline-block",
                  }}
                />{" "}
                Active
              </span>
              <span
                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: "var(--lt-amber)",
                    display: "inline-block",
                  }}
                />{" "}
                Pending
              </span>
            </div>
          </div>
          <div className="county-state-groups">
            {groups.map((g) => (
              <div key={g.state} className="county-state-group">
                <div className="county-state-label">
                  {g.stateLabel}
                  <span className="county-state-count">{g.counties.length}</span>
                </div>
                <div className="county-chips">
                  {g.counties.map((c) => (
                    <span key={`${g.state}-${c}`} className="county-chip">
                      <span className="dot" />
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {pending.length > 0 && (
              <div className="county-state-group">
                <div className="county-state-label">
                  Pending outreach
                  <span className="county-state-count">{pending.length}</span>
                </div>
                <div className="county-chips">
                  {pending.map((p) => (
                    <span
                      key={`${p.state}-${p.name}`}
                      className="county-chip pending"
                    >
                      <span className="dot" />
                      {p.name}, {p.state}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
