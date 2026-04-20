import { siteCopy } from "@/lib/marketing-copy";

export function HowItWorks() {
  const { eyebrow, headline, subheadline, steps } = siteCopy.howItWorks;
  return (
    <section className="section" id="how">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title">{headline}</h2>
          <p className="section-sub">{subheadline}</p>
        </div>
        <div className="hiw-grid">
          {steps.map((s) => (
            <div
              className="step-card"
              key={s.num}
              data-testid="how-it-works-step"
            >
              <div className="step-num">{s.num}</div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
              <div className="step-visual">
                <span className="placeholder">[ {s.placeholder} ]</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
