import type { ReactNode } from "react";
import { MarketingLayout } from "@/components/marketing/marketing-layout";

type LegalPageProps = {
  eyebrow: string;
  title: string;
  updated: string;
  children: ReactNode;
};

export function LegalPage({ eyebrow, title, updated, children }: LegalPageProps) {
  return (
    <MarketingLayout>
      <section className="section">
        <div className="wrap legal-wrap">
          <span className="eyebrow">{eyebrow}</span>
          <h1 className="section-title" style={{ textAlign: "left" }}>
            {title}
          </h1>
          <p
            className="section-sub"
            style={{
              textAlign: "left",
              marginTop: 4,
              fontSize: 13,
              color: "var(--lt-text-dim)",
            }}
          >
            Last updated {updated}
          </p>
          <div className="legal-body">{children}</div>
        </div>
      </section>
    </MarketingLayout>
  );
}
