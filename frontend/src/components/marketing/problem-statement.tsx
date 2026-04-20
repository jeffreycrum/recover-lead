import { siteCopy } from "@/lib/marketing-copy";

export function ProblemStatement() {
  const { eyebrow, headline, cards } = siteCopy.problemStatement;
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
        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {cards.map((card) => (
            <div
              key={card.title}
              className="rounded-lg border border-border/60 bg-card p-6 shadow-sm"
            >
              <h3 className="text-lg font-semibold">{card.title}</h3>
              <p className="mt-3 text-sm text-muted-foreground">{card.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
