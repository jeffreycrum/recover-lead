import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { siteCopy } from "@/lib/marketing-copy";
import { CheckIcon } from "./icons";

export function AudienceWorkflows() {
  const { eyebrow, headline, tabsAriaLabel, tabs } = siteCopy.audience;
  const defaultTabId = tabs[0]?.id;

  if (!defaultTabId) {
    return null;
  }

  return (
    <section className="section">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{eyebrow}</span>
          <h2 className="section-title">{headline}</h2>
        </div>
        <Tabs defaultValue={defaultTabId} className="contents">
          <div style={{ display: "flex", justifyContent: "center" }}>
            <TabsList
              className="aud-tabs"
              aria-label={tabsAriaLabel}
            >
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.id}
                  value={tab.id}
                  data-testid="audience-tab"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {tabs.map((tab) => (
            <TabsContent key={tab.id} value={tab.id} className="mt-0">
              <div className="aud-grid">
                <div className="aud-bullets">
                  {tab.bullets.map((bullet) => (
                    <div className="aud-bullet" key={bullet.t}>
                      <div className="ico">
                        <CheckIcon />
                      </div>
                      <div>
                        <div className="t">{bullet.t}</div>
                        <div className="d">{bullet.d}</div>
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
                      <span className="title">{tab.previewTitle}</span>
                    </div>
                  </div>
                  <div className="pc-body" style={{ minHeight: 280 }}>
                    <div className="step-visual" style={{ height: 260 }}>
                      <span className="placeholder">
                        [ {tab.id} workflow screenshot ]
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </section>
  );
}
