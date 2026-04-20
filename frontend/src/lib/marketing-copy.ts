export const siteCopy = {
  brand: {
    name: "RecoverLead",
    tagline: "AI-powered surplus funds recovery",
  },
  nav: {
    signIn: "Sign in",
    signUp: "Start free",
  },
  hero: {
    eyebrow: "Surplus funds recovery, automated",
    headline:
      "Find, qualify, and close surplus claims in hours — not weeks.",
    subheadline:
      "RecoverLead ingests county data, qualifies claimants with AI, drafts outreach letters, and tracks every deadline so agents, attorneys, and heir search firms close more claims with less legwork.",
    primaryCta: "Start free",
    secondaryCta: "Sign in",
  },
  problemStatement: {
    eyebrow: "The surplus funds problem",
    headline: "Millions sit unclaimed. The work to find them is brutal.",
    cards: [
      {
        title: "Scattered county records",
        body: "Surplus funds notices live across hundreds of county sites, each with their own format, filing cadence, and document structure. Manual monitoring doesn't scale.",
      },
      {
        title: "Stale contact data",
        body: "Former owners move, change names, and slip off public rolls. Skip tracing without qualification wastes credits on leads that go nowhere.",
      },
      {
        title: "Missed deadlines",
        body: "Claim windows close fast. Miss a statutory deadline and the funds revert to the state — leaving rightful claimants with nothing.",
      },
    ],
  },
  howItWorks: {
    eyebrow: "How it works",
    headline: "Four steps from unclaimed surplus to closed claim.",
    steps: [
      {
        number: "01",
        title: "Ingest",
        body: "Automated scrapers pull new surplus notices from county court and treasurer sites every day, normalized into a single feed.",
      },
      {
        number: "02",
        title: "Qualify",
        body: "AI scores each lead on recoverability, surplus size, and claim complexity — so you spend credits only on claims worth pursuing.",
      },
      {
        number: "03",
        title: "Contact",
        body: "Generate personalized outreach letters with one click. Skip traces resolve current addresses, phone numbers, and email.",
      },
      {
        number: "04",
        title: "Close",
        body: "Track every deadline, contract, and correspondence in one place. Activities log automatically as claims move through the pipeline.",
      },
    ],
  },
  audienceWorkflows: {
    eyebrow: "Built for your workflow",
    headline: "One platform, three audiences.",
    audiences: [
      {
        id: "agents",
        label: "Agents",
        headline: "Volume-driven lead generation.",
        body: "Monitor dozens of counties without hiring a research team. RecoverLead surfaces qualified surplus leads daily so you can focus on closing, not hunting.",
        bullets: [
          "Daily lead feed across activated counties",
          "Quality scoring filters out dead-end claims",
          "Batch letter generation for outreach at scale",
        ],
      },
      {
        id: "attorneys",
        label: "Attorneys",
        headline: "Case-quality qualification.",
        body: "Evaluate claim complexity before you commit hours. Full document trails and statutory deadlines keep every matter audit-ready.",
        bullets: [
          "Original foreclosure documents attached to every lead",
          "Deadline tracker with statutory windows per jurisdiction",
          "Activity log captures every touchpoint for the file",
        ],
      },
      {
        id: "heir-search",
        label: "Heir Search",
        headline: "Decedent estates and heir outreach.",
        body: "Identify surplus tied to estate proceedings and resolve heirs with integrated skip tracing — without the stack of disparate tools.",
        bullets: [
          "Decedent and estate-flagged lead views",
          "Multi-subject skip tracing with credit controls",
          "Shared research across team accounts",
        ],
      },
    ],
  },
  featureGrid: {
    eyebrow: "What's inside",
    headline: "Every tool you need to run a surplus recovery pipeline.",
    features: [
      {
        title: "Automated ingestion",
        body: "Daily scraping across activated counties, with document parsing and dedup so the same lead never reappears.",
      },
      {
        title: "AI qualification",
        body: "Claude-powered scoring on recoverability, surplus size, and complexity. Quality scores 1–10 with reasoning you can audit.",
      },
      {
        title: "Skip tracing",
        body: "Resolve current phone, email, and address on demand. Shared results across your team so you never pay twice for the same subject.",
      },
      {
        title: "Letter generation",
        body: "Template library tuned for surplus outreach. Personalized in seconds, exported to PDF or sent via integrated mail providers.",
      },
      {
        title: "Deadline tracking",
        body: "Statutory claim windows per jurisdiction with reminders, so no matter slips through the cracks.",
      },
      {
        title: "Pipeline analytics",
        body: "See conversion from ingestion → qualification → contact → close. Know which counties and audiences perform for your firm.",
      },
    ],
  },
  socialProof: {
    eyebrow: "Trusted by recovery professionals",
    headline: "Join firms closing more claims with less overhead.",
    logos: [
      { name: "Logo placeholder 1" },
      { name: "Logo placeholder 2" },
      { name: "Logo placeholder 3" },
      { name: "Logo placeholder 4" },
      { name: "Logo placeholder 5" },
    ],
    testimonials: [
      {
        quote:
          "Testimonial placeholder — customer story coming soon. We're collecting firm results from the pilot cohort.",
        author: "Pilot customer",
        role: "Surplus recovery firm",
      },
      {
        quote:
          "Testimonial placeholder — attorney perspective on deadline tracking and document integrity.",
        author: "Pilot customer",
        role: "Attorney, estate & surplus practice",
      },
    ],
  },
  footer: {
    copyright: "© 2026 RecoverLead. All rights reserved.",
    links: [
      { label: "Contact", href: "mailto:hello@recoverlead.com" },
    ],
  },
} as const;
