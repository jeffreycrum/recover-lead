import { useState } from "react";
import { siteCopy } from "@/lib/marketing-copy";
import { CheckIcon } from "./icons";

export function AudienceWorkflows() {
  const { eyebrow, headline, tabsAriaLabel, tabs } = siteCopy.audience;
  const [active, setActive] = useState<string>(tabs[0]?.id ?? "");
  const current = tabs.find((t) => t.id === active) ?? tabs[0];

  if (!current) {
    return null;
  }

  return (
    <section className="section">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title">{headline}</h2>
        </div>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <div
            className="aud-tabs"
            role="tablist"
            aria-label={tabsAriaLabel}
          >
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={active === tab.id}
                className={active === tab.id ? "active" : ""}
                onClick={() => setActive(tab.id)}
                data-testid="audience-tab"
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <div className="aud-grid">
          <div className="aud-bullets">
            {current.bullets.map((b) => (
              <div className="aud-bullet" key={b.t}>
                <div className="ico">
                  <CheckIcon />
                </div>
                <div>
                  <div className="t">{b.t}</div>
                  <div className="d">{b.d}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="product-card" style={{ transform: "none" }}>
            <div className="pc-head">
              <div
                style={{ display: "flex", alignItems: "center", gap: 12 }}
              >
                <div className="pc-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="title">{current.previewTitle}</span>
              </div>
            </div>
            <div className="pc-body" style={{ minHeight: 280 }}>
              <div className="step-visual" style={{ height: 260 }}>
                <span className="placeholder">
                  [ {current.id} workflow screenshot ]
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
