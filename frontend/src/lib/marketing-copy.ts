const currentYear = new Date().getFullYear();

export const siteCopy = {
  brand: {
    name: "RecoverLead",
  },
  nav: {
    signIn: "Sign in",
    primaryCta: "Start recovering",
    items: [
      { id: "product", label: "Product" },
      { id: "how", label: "How it works" },
      { id: "counties", label: "Counties", liveDot: true },
      { id: "pricing", label: "Pricing" },
      { id: "faq", label: "FAQ" },
    ],
  },
  hero: {
    badge: {
      chip: "New",
      label: "Now covering 33 Florida counties with daily updates",
    },
    headlineLead: "Find the surplus funds",
    headlineGradient: "others overlook.",
    subheadline:
      "RecoverLead is the AI platform that ingests tax-deed and foreclosure records from every active county clerk, qualifies each surplus, and drafts the compliant outreach letter — so agents, attorneys, and heir-search firms close more recoveries with fewer hours.",
    primaryCta: "Start free trial",
    secondaryCta: "See how it works",
    proof: [
      { num: "$127.4M", label: "Surplus indexed" },
      { num: "33", label: "FL counties live" },
      { num: "< 4 min", label: "Lead → letter" },
    ],
    productCard: {
      title: "Leads · Hillsborough County · Today",
      meta: "12 new",
      rows: [
        {
          name: "Marguerite Alvarez",
          meta: "2018 tax deed · 4132 Bayshore Blvd · Parcel 084623",
          amount: "$84,217",
          score: "9.4",
          scoreHi: true,
          status: "Qualified",
          qualified: true,
          highlight: true,
        },
        {
          name: "Estate of W. Harrington",
          meta: "2021 foreclosure · 717 Platt St · Case 21-CA-004218",
          amount: "$62,850",
          score: "8.7",
          scoreHi: true,
          status: "Qualified",
          qualified: true,
        },
        {
          name: "Daniel & Rosa Kline",
          meta: "2019 tax deed · 609 Rome Ave · Parcel 148992",
          amount: "$48,400",
          score: "7.2",
          scoreHi: false,
          status: "Scored",
          qualified: false,
        },
        {
          name: "JTL Holdings, LLC",
          meta: "2020 foreclosure · 3301 N Armenia Ave · Case 20-CA-009012",
          amount: "$31,120",
          score: "6.8",
          scoreHi: false,
          status: "Scored",
          qualified: false,
        },
        {
          name: "Consuela Whitfield",
          meta: "2022 tax deed · 1419 E 24th Ave · Parcel 057731",
          amount: "$22,605",
          score: "6.1",
          scoreHi: false,
          status: "Scored",
          qualified: false,
        },
      ],
    },
    callouts: [
      { title: "Qualified in 3.2s", sub: "Claude scored 9.4 / 10", tone: "emerald" as const },
      { title: "Letter drafted", sub: "FL tax-deed template", tone: "blue" as const },
    ],
  },
  ticker: {
    items: [
      { amt: "$84,217", loc: "Hillsborough, FL · tax deed" },
      { amt: "$62,850", loc: "Broward, FL · foreclosure" },
      { amt: "$127,004", loc: "Pinellas, FL · tax deed" },
      { amt: "$48,400", loc: "Volusia, FL · tax deed" },
      { amt: "$31,120", loc: "Polk, FL · foreclosure" },
      { amt: "$95,612", loc: "Lee, FL · tax deed" },
      { amt: "$22,605", loc: "Marion, FL · tax deed" },
      { amt: "$71,008", loc: "Collier, FL · foreclosure" },
      { amt: "$44,980", loc: "Columbia, FL · tax deed" },
      { amt: "$58,332", loc: "Leon, FL · tax deed" },
    ],
  },
  audience: {
    eyebrow: "Built for specialists",
    headline: "One platform. Three recovery workflows.",
    tabsAriaLabel: "Audience workflows",
    tabs: [
      {
        id: "agents",
        label: "Agents",
        previewTitle: "Batch letter generation",
        bullets: [
          {
            t: "Bulk qualify thousands of leads",
            d: "Claude scores every surplus in minutes, not hours. Batch-qualify a whole county with one click.",
          },
          {
            t: "Auto-drafted FL-compliant letters",
            d: "Tax-deed, foreclosure, and excess-proceeds templates — all state-specific, all reviewed by counsel.",
          },
          {
            t: "One-click Lob mailing",
            d: "Approve the letter and mail goes out the same day. Tracking and delivery webhooks included.",
          },
        ],
      },
      {
        id: "attorneys",
        label: "Attorneys",
        previewTitle: "Qualification reasoning",
        bullets: [
          {
            t: "Evidence-first qualification",
            d: "Every score comes with the reasoning chain — case number, statute, owner clarity, and confidence.",
          },
          {
            t: "Contract generator",
            d: "Template-driven contracts with Claude filling case-specific fields. E-sign ready.",
          },
          {
            t: "Referral marketplace",
            d: "Accept matched referrals from agents. Track referral fees per closed deal.",
          },
        ],
      },
      {
        id: "heir",
        label: "Heir-search firms",
        previewTitle: "Skip trace results",
        bullets: [
          {
            t: "Skip-trace integration",
            d: "SkipSherpa and Tracerfy built in. Pay-per-hit pricing, results auto-attached to the lead.",
          },
          {
            t: "Multi-state parsers",
            d: "FL, CA, GA, TX, OH county parsers live. More added monthly.",
          },
          {
            t: "Deal outcome tracking",
            d: '"Mark paid" flow closes the feedback loop — use real outcomes to retrain qualification models.',
          },
        ],
      },
    ],
  },
  howItWorks: {
    eyebrow: "How it works",
    headline: "From county records to signed recovery, on rails.",
    subheadline:
      "Three steps, all automated where it matters, with you firmly in control where it counts.",
    steps: [
      {
        num: "STEP 01",
        title: "Ingest every county",
        desc: "Nightly scrapers pull tax-deed, foreclosure, and excess-proceeds filings from 33 FL county clerks. Dedup, normalize, embed.",
        placeholder: "county scraper dashboard",
      },
      {
        num: "STEP 02",
        title: "Qualify with Claude",
        desc: "Each surplus is scored 1 – 10 on recoverability. Claude reviews owner clarity, amount, age, and county-specific statutes.",
        placeholder: "qualification timeline",
      },
      {
        num: "STEP 03",
        title: "Draft & mail",
        desc: "Approve, edit, and mail compliant outreach letters through Lob. Skip-trace, pipeline status, and deal outcome all tracked.",
        placeholder: "letter editor + mail dialog",
      },
    ],
  },
  pipeline: {
    eyebrow: "Your pipeline",
    headline: "A 7-stage funnel, tuned for recovery economics.",
    subheadline:
      "Every lead moves through New → Qualified → Contacted → Signed → Filed → Paid → Closed. See conversion rates per stage, average days to close, and ROI per county — at a glance.",
    cta: "See the dashboard",
    caption: "Last 90 days",
    delta: "+18% vs prev",
    rows: [
      { name: "New", count: "1,284", pct: "100%", widthPct: 100, opacity: 1 },
      { name: "Qualified", count: "742", pct: "58%", widthPct: 92, opacity: 1 },
      { name: "Contacted", count: "486", pct: "38%", widthPct: 64, opacity: 0.92 },
      { name: "Signed", count: "312", pct: "24%", widthPct: 48, opacity: 0.84 },
      { name: "Filed", count: "214", pct: "17%", widthPct: 34, opacity: 0.76 },
      { name: "Paid", count: "148", pct: "12%", widthPct: 22, opacity: 0.68 },
      { name: "Closed", count: "96", pct: "7%", widthPct: 14, opacity: 0.6 },
    ],
  },
  counties: {
    eyebrow: "Coverage",
    headline: "33 Florida counties active. More added monthly.",
    subheadline:
      "We run nightly ingestion against every scrapable FL county clerk, plus active parsers for California, Georgia, Texas, and Ohio. If a county changes its website, we fix the scraper — not you.",
    cta: "View full county map",
    proof: [
      { num: "33", label: "Live in FL" },
      { num: "4", label: "Pending outreach" },
      { num: "Daily", label: "Refresh cadence" },
    ],
    vizTitle: "Florida coverage",
    legend: [
      { label: "Active", color: "emerald" as const },
      { label: "Pending", color: "amber" as const },
    ],
    active: [
      "Volusia","Hillsborough","Pinellas","Broward","Polk","Lee","Collier","Columbia",
      "Marion","Martin","Leon","Miami-Dade","Orange","Duval","Palm Beach","Alachua",
      "Charlotte","Citrus","Clay","Escambia","Flagler","Hernando","Lake","Monroe",
      "Nassau","St. Johns","Sarasota","Seminole","St. Lucie","Brevard","Manatee","Osceola","Pasco",
    ],
    pending: ["Bay", "Okaloosa", "Santa Rosa", "Walton"],
  },
  pricing: {
    eyebrow: "Pricing",
    headline: "Priced for the economics of recovery.",
    subheadline: "One signed deal typically covers 6-12 months. Annual plans save 2 months.",
    plans: [
      {
        tier: "Starter",
        name: "Starter",
        desc: "Solo agents getting serious about recovery.",
        price: 79,
        featured: false,
        feats: [
          { a: "200", b: " qualifications / mo" },
          { a: "100", b: " letters / mo" },
          { a: "25", b: " skip traces / mo" },
          { a: "All", b: " FL counties" },
          { a: "Lob mail", b: " integration" },
        ],
      },
      {
        tier: "Pro",
        name: "Pro",
        desc: "Growing firms running multiple counties.",
        price: 199,
        featured: true,
        feats: [
          { a: "1,000", b: " qualifications / mo" },
          { a: "500", b: " letters / mo" },
          { a: "100", b: " skip traces / mo" },
          { a: "Priority", b: " qualification queue" },
          { a: "Batch letter generation", b: "" },
          { a: "ROI dashboard", b: "" },
        ],
      },
      {
        tier: "Agency",
        name: "Agency",
        desc: "Heir-search firms and law offices.",
        price: 499,
        featured: false,
        feats: [
          { a: "5,000", b: " qualifications / mo" },
          { a: "2,000", b: " letters / mo" },
          { a: "500", b: " skip traces / mo" },
          { a: "Referral marketplace", b: "" },
          { a: "Contract generation", b: "" },
          { a: "Priority support", b: "" },
        ],
      },
    ],
  },
  faq: {
    eyebrow: "FAQ",
    headline: "Questions, answered.",
    items: [
      {
        q: "Is the outreach compliant?",
        a: "All letter templates are written against Florida statutes (§197.582 for tax deeds, §45.032 for foreclosure surplus) and reviewed by counsel. State-specific templates exist for CA, GA, TX, and OH.",
      },
      {
        q: "How fresh is the data?",
        a: "Active counties are scraped nightly. Status and last-scraped timestamps are visible per county in-app. If a scraper breaks, we're alerted via Sentry and typically fix within 24 hours.",
      },
      {
        q: "Do I need a skip-trace subscription?",
        a: "No. Skip-trace is metered per hit ($0.10/hit via Tracerfy/SkipSherpa, built in). You pay for results, not searches.",
      },
      {
        q: "Can I bring my own letter templates?",
        a: "Pro and Agency plans support custom Jinja2 templates. We review for compliance before activating.",
      },
      {
        q: "Is there a free tier?",
        a: "Yes — 15 qualifications and 10 letters per month, any single FL county. Good for evaluating the platform end-to-end.",
      },
      {
        q: "What about refunds?",
        a: "Monthly plans: cancel anytime. Annual: pro-rated refund if you cancel within 14 days.",
      },
    ],
  },
  closingCta: {
    headline: "Recover what's already yours to find.",
    subheadline: "Start free. No credit card until your first qualified lead.",
    primaryCta: "Start free trial",
    secondaryCta: "Book a demo",
  },
  footer: {
    copyright: `© ${currentYear} RecoverLead, Inc.`,
    links: [
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
      { label: "Security", href: "/security" },
      { label: "Status", href: "/status" },
      { label: "Contact", href: "mailto:hello@recoverlead.com" },
    ],
  },
} as const;
