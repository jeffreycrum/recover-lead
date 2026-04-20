import { LegalPage } from "./legal-layout";

export function TermsPage() {
  return (
    <LegalPage eyebrow="Legal" title="Terms of service" updated="April 2026">
      <h2>Agreement</h2>
      <p>
        By creating an account or using RecoverLead you agree to these terms.
        If you disagree with any part of these terms, do not use the service.
        RecoverLead is operated by RecoverLead, Inc.
      </p>

      <h2>Your account</h2>
      <p>
        You're responsible for keeping your credentials secure and for any
        activity under your account. You must be 18 or older and legally
        permitted to conduct surplus-funds recovery activities in your
        jurisdiction. You may not share your account with other users.
      </p>

      <h2>Permitted use</h2>
      <p>
        RecoverLead is a tool for professional surplus-funds recovery work.
        You may not:
      </p>
      <ul>
        <li>Use RecoverLead to contact parties in violation of state-level
          surplus-funds statutes or unfair-competition laws.
        </li>
        <li>
          Scrape, resell, or redistribute our proprietary qualification scores,
          letter templates, or county parsers.
        </li>
        <li>
          Share your account with other individuals or organizations.
        </li>
        <li>
          Use the service to send deceptive outreach or misrepresent your
          identity, affiliation, or fee structure.
        </li>
      </ul>

      <h2>No legal advice</h2>
      <p>
        RecoverLead is not a law firm. Our letters, qualification scores, and
        analytics are informational tools — not legal advice. You are
        responsible for final compliance review before mailing any letter or
        entering into any recovery contract.
      </p>

      <h2>Billing and cancellation</h2>
      <p>
        Plans renew automatically until cancelled. You can cancel anytime from
        Settings. Monthly plans are prorated to the end of the current billing
        cycle; annual plans refund within 14 days of renewal if cancelled.
      </p>

      <h2>Warranty and liability</h2>
      <p>
        The service is provided "as is." We do not warrant that every county
        scraper runs perfectly every night or that every qualification score is
        correct. Our total liability is limited to the amount you paid us in
        the preceding 12 months.
      </p>

      <h2>Changes</h2>
      <p>
        We may update these terms and will notify you by email when we make
        material changes. Continued use after an update constitutes acceptance
        of the revised terms.
      </p>

      <h2>Contact</h2>
      <p>
        Email <a href="mailto:legal@recoverlead.com">legal@recoverlead.com</a>.
      </p>
    </LegalPage>
  );
}
