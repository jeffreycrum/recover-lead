import { siteCopy } from "@/lib/marketing-copy";
import { CtaButton } from "./cta-button";

export function HeroSection() {
  const { eyebrow, headline, subheadline, primaryCta, secondaryCta } =
    siteCopy.hero;

  return (
    <section className="relative overflow-hidden">
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-emerald/10 via-background to-background"
        aria-hidden="true"
      />
      <div className="relative mx-auto flex max-w-4xl flex-col items-center px-6 py-24 text-center sm:py-32">
        <p className="text-sm font-semibold uppercase tracking-widest text-emerald">
          {eyebrow}
        </p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
          {headline}
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
          {subheadline}
        </p>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <CtaButton
            to="/sign-up"
            variant="primary"
            event="marketing.hero_cta.click"
            eventProps={{ variant: "primary", destination: "sign-up" }}
          >
            {primaryCta}
          </CtaButton>
          <CtaButton
            to="/sign-in"
            variant="secondary"
            event="marketing.hero_cta.click"
            eventProps={{ variant: "secondary", destination: "sign-in" }}
          >
            {secondaryCta}
          </CtaButton>
        </div>
      </div>
    </section>
  );
}
