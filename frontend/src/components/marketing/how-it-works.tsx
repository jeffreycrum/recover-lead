import { siteCopy } from "@/lib/marketing-copy";

export function HowItWorks() {
  const { eyebrow, headline, steps } = siteCopy.howItWorks;
  return (
    <section className="border-t border-border/40 bg-muted/30">
      <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-emerald">
            {eyebrow}
          </p>
          <h2 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
            {headline}
          </h2>
        </div>
        <ol
          data-testid="how-it-works-steps"
          className="mt-14 grid gap-8 sm:grid-cols-2 lg:grid-cols-4"
        >
          {steps.map((step) => (
            <li
              key={step.number}
              data-testid="how-it-works-step"
              className="relative rounded-lg border border-border/60 bg-background p-6 shadow-sm"
            >
              <span className="text-sm font-mono font-semibold text-emerald">
                {step.number}
              </span>
              <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
