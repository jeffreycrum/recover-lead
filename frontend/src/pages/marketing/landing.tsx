import { MarketingLayout } from "@/components/marketing/marketing-layout";
import { HeroSection } from "@/components/marketing/hero-section";
import { Ticker } from "@/components/marketing/ticker";
import { AudienceWorkflows } from "@/components/marketing/audience-workflows";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { PipelineFunnel } from "@/components/marketing/pipeline-funnel";
import { CountiesCoverage } from "@/components/marketing/counties-coverage";
import { PricingSection } from "@/components/marketing/pricing-section";
import { FaqSection } from "@/components/marketing/faq-section";
import { ClosingCta } from "@/components/marketing/closing-cta";

export function MarketingLandingPage() {
  return (
    <MarketingLayout>
      <HeroSection />
      <Ticker />
      <AudienceWorkflows />
      <HowItWorks />
      <PipelineFunnel />
      <CountiesCoverage />
      <PricingSection />
      <FaqSection />
      <ClosingCta />
    </MarketingLayout>
  );
}
