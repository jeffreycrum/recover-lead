import * as Tabs from "@radix-ui/react-tabs";
import { siteCopy } from "@/lib/marketing-copy";

export function AudienceWorkflows() {
  const { eyebrow, headline, tabsAriaLabel, audiences } =
    siteCopy.audienceWorkflows;
  return (
    <section className="border-t border-border/40 bg-background">
      <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-emerald">
            {eyebrow}
          </p>
          <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
            {headline}
          </h2>
        </div>
        <Tabs.Root
          defaultValue={audiences[0].id}
          className="mt-12 flex flex-col items-center"
        >
          <Tabs.List
            aria-label={tabsAriaLabel}
            className="inline-flex rounded-md border border-border/60 bg-muted/40 p-1"
          >
            {audiences.map((aud) => (
              <Tabs.Trigger
                key={aud.id}
                value={aud.id}
                data-testid="audience-tab"
                className="rounded px-4 py-2 text-sm font-medium text-muted-foreground transition-colors data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm"
              >
                {aud.label}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <div className="mt-8 w-full">
            {audiences.map((aud) => (
              <Tabs.Content
                key={aud.id}
                value={aud.id}
                className="rounded-lg border border-border/60 bg-card p-8 shadow-sm"
              >
                <h3 className="text-xl font-semibold">{aud.headline}</h3>
                <p className="mt-3 text-muted-foreground">{aud.body}</p>
                <ul className="mt-5 space-y-2 text-sm">
                  {aud.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-2">
                      <span
                        aria-hidden="true"
                        className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-emerald"
                      />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              </Tabs.Content>
            ))}
          </div>
        </Tabs.Root>
      </div>
    </section>
  );
}
