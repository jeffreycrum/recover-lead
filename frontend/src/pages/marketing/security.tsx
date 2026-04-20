import { LegalPage } from "./legal-layout";

export function SecurityPage() {
  return (
    <LegalPage eyebrow="Trust" title="Security" updated="April 2026">
      <h2>Our approach</h2>
      <p>
        RecoverLead processes public-records data and business contact
        information for professional recovery work. We treat your account, your
        pipeline, and your outreach history as confidential, and we take a
        layered, defense-in-depth approach to protecting it.
      </p>

      <h2>Authentication and access</h2>
      <ul>
        <li>
          <strong>Clerk-managed auth</strong> with support for password, OAuth,
          and MFA. We never store your password.
        </li>
        <li>
          <strong>Row-level tenancy:</strong> every query is scoped by account
          ID at the database layer so one firm's leads, letters, and contacts
          are never visible to another.
        </li>
        <li>
          <strong>Least-privilege access</strong> for employees. Production
          database access requires SSO, MFA, and is logged.
        </li>
      </ul>

      <h2>Data protection</h2>
      <ul>
        <li>All traffic is encrypted in transit with TLS 1.2+.</li>
        <li>
          Data at rest is encrypted using our hosting provider's managed
          keys.
        </li>
        <li>
          Secrets are managed via environment variables and never committed to
          source control.
        </li>
        <li>
          Structured logs are scrubbed of email, phone, and address data before
          being written.
        </li>
      </ul>

      <h2>Payments</h2>
      <p>
        Payments are processed by Stripe. RecoverLead never sees your full
        card number — only the last four digits and brand, for display on
        receipts.
      </p>

      <h2>Uptime and monitoring</h2>
      <p>
        We monitor scraper health, job queues, and API latency via Sentry and
        our hosting provider's metrics. When a scraper breaks or an endpoint
        degrades we're alerted and triage within business hours; most
        scraper-level incidents are resolved within 24 hours.
      </p>

      <h2>Reporting a vulnerability</h2>
      <p>
        If you believe you've found a security issue, please email{" "}
        <a href="mailto:security@recoverlead.com">security@recoverlead.com</a>{" "}
        with reproduction steps. We'll acknowledge within two business days.
        We ask that you give us a reasonable window to fix the issue before
        publicly disclosing.
      </p>
    </LegalPage>
  );
}
