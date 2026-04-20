import { MarketingLayout } from "@/components/marketing/marketing-layout";
import { HeroSection } from "@/components/marketing/hero-section";
import { ProblemStatement } from "@/components/marketing/problem-statement";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { AudienceWorkflows } from "@/components/marketing/audience-workflows";
import { FeatureGrid } from "@/components/marketing/feature-grid";
import { SocialProof } from "@/components/marketing/social-proof";

export function MarketingLandingPage() {
  return (
    <MarketingLayout>
      <HeroSection />
      <ProblemStatement />
      <HowItWorks />
      <AudienceWorkflows />
      <FeatureGrid />
      <SocialProof />
    </MarketingLayout>
  );
}
