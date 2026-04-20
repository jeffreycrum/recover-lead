import { siteCopy } from "@/lib/marketing-copy";

export function SocialProof() {
  const { eyebrow, headline, logos, testimonials } = siteCopy.socialProof;
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
        <div
          aria-label="Customer logos"
          className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5"
        >
          {logos.map((logo) => (
            <div
              key={logo.name}
              role="img"
              aria-label={logo.name}
              className="flex h-16 items-center justify-center rounded-md border border-dashed border-border/60 bg-muted/30 text-xs text-muted-foreground"
            >
              {logo.name}
            </div>
          ))}
        </div>
        <div className="mt-16 grid gap-6 md:grid-cols-2">
          {testimonials.map((t) => (
            <figure
              key={t.author + t.role}
              className="rounded-lg border border-border/60 bg-card p-6 shadow-sm"
            >
              <blockquote className="text-sm text-muted-foreground">
                “{t.quote}”
              </blockquote>
              <figcaption className="mt-4 text-sm">
                <span className="font-semibold">{t.author}</span>
                <span className="text-muted-foreground"> — {t.role}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
