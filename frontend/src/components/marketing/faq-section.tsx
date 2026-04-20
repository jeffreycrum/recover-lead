import { siteCopy } from "@/lib/marketing-copy";

export function FaqSection() {
  const { eyebrow, headline, items } = siteCopy.faq;
  return (
    <section className="section" id="faq">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title">{headline}</h2>
        </div>
        <div className="faq-grid">
          {items.map((item) => (
            <details className="faq" key={item.q} data-testid="faq-item">
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
