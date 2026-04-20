import { LegalPage } from "./legal-layout";

export function PrivacyPage() {
  return (
    <LegalPage eyebrow="Legal" title="Privacy policy" updated="April 2026">
      <h2>Summary</h2>
      <p>
        RecoverLead helps agents, attorneys, and heir-search firms identify and
        pursue surplus funds from public foreclosure and tax-deed filings. We
        process public records data and a limited set of personal data you
        provide about yourself to operate the service. We do not sell your data
        and we do not use your data to train third-party AI models.
      </p>

      <h2>Data we collect</h2>
      <ul>
        <li>
          <strong>Account data:</strong> name, email, and authentication
          identifiers provided via Clerk when you sign up.
        </li>
        <li>
          <strong>Billing data:</strong> handled by Stripe. We store the last
          four digits of your card, plan, and invoice history — never full card
          numbers.
        </li>
        <li>
          <strong>Usage data:</strong> page views, feature clicks, and
          aggregated performance data so we can improve the product.
        </li>
        <li>
          <strong>Public-records data:</strong> county surplus filings, case
          numbers, parcel IDs, and related public information used to generate
          leads.
        </li>
      </ul>

      <h2>How we use it</h2>
      <p>
        To run and improve the service, process payments, send service emails,
        respond to support requests, and meet legal obligations. We do not
        share account data with third parties for their own marketing.
      </p>

      <h2>Sub-processors</h2>
      <p>
        Clerk (authentication), Stripe (payments), Anthropic (AI qualification
        and letter drafting), Lob (mail delivery), Resend (transactional email),
        and Railway (hosting). A current list with versions and regions is
        available on request.
      </p>

      <h2>Data retention and deletion</h2>
      <p>
        Account data is retained while your account is active and for 30 days
        after cancellation for account-recovery purposes. You can request
        deletion at any time by emailing{" "}
        <a href="mailto:privacy@recoverlead.com">privacy@recoverlead.com</a>.
      </p>

      <h2>Your rights</h2>
      <p>
        Depending on where you live, you may have rights to access, correct,
        export, or delete your data under laws like the CCPA, CPRA, or GDPR.
        Email{" "}
        <a href="mailto:privacy@recoverlead.com">privacy@recoverlead.com</a>{" "}
        and we'll respond within 30 days.
      </p>

      <h2>Contact</h2>
      <p>
        Questions? Email{" "}
        <a href="mailto:privacy@recoverlead.com">privacy@recoverlead.com</a>.
      </p>
    </LegalPage>
  );
}
