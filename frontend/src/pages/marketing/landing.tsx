import { MarketingLayout } from "@/components/marketing/marketing-layout";

export function MarketingLandingPage() {
  return (
    <MarketingLayout>
      <section className="min-h-screen flex items-center justify-center bg-gray-50 px-6">
        <div className="text-center max-w-2xl">
          <h1 className="text-4xl sm:text-5xl font-bold mb-4">
            <span className="text-emerald">Recover</span>Lead
          </h1>
          <p className="text-lg text-muted-foreground">
            AI-powered surplus funds recovery for agents, attorneys, and heir search firms.
          </p>
        </div>
      </section>
    </MarketingLayout>
  );
}
