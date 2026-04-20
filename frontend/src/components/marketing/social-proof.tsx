import { siteCopy } from "@/lib/marketing-copy";

export function SocialProof() {
  const {
    eyebrow,
    headline,
    logosAriaLabel,
    logos,
    testimonialsAriaLabel,
    testimonialSkeletonLabel,
    testimonialSkeletonCount,
  } = siteCopy.socialProof;
  const skeletonIndexes = Array.from(
    { length: testimonialSkeletonCount },
    (_, i) => i,
  );
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
          aria-label={logosAriaLabel}
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
        <div
          aria-label={testimonialsAriaLabel}
          className="mt-16 grid gap-6 md:grid-cols-2"
        >
          {skeletonIndexes.map((i) => (
            <figure
              key={i}
              aria-label={testimonialSkeletonLabel}
              className="rounded-lg border border-border/60 bg-card p-6 shadow-sm"
            >
              <div
                aria-hidden="true"
                className="space-y-3"
                data-testid="testimonial-skeleton"
              >
                <div className="h-3 w-11/12 animate-pulse rounded bg-muted" />
                <div className="h-3 w-10/12 animate-pulse rounded bg-muted" />
                <div className="h-3 w-8/12 animate-pulse rounded bg-muted" />
              </div>
              <figcaption
                aria-hidden="true"
                className="mt-6 flex items-center gap-3"
              >
                <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />
                <div className="flex-1 space-y-2">
                  <div className="h-2.5 w-1/3 animate-pulse rounded bg-muted" />
                  <div className="h-2 w-1/2 animate-pulse rounded bg-muted" />
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
