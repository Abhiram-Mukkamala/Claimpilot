import React from 'react';

export const PrivacyPolicyContent: React.FC = () => {
  return (
    <article
      className="privacy-policy-content"
      style={{
        color: 'var(--text-primary)',
        fontSize: '0.9rem',
        lineHeight: 1.65,
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
      }}
    >
      <header style={{ borderBottom: '1px solid var(--border)', paddingBottom: '1rem', marginBottom: '0.5rem' }}>
        <h1
          id="privacy-policy-title"
          style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'var(--text-primary)',
            marginBottom: '0.5rem',
          }}
        >
          ClaimPilot — Privacy Policy
        </h1>
        <p
          style={{
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
            margin: 0,
          }}
        >
          <strong>Last Updated: [DATE]</strong>
        </p>
      </header>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          1. Introduction
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          ClaimPilot is an AI-assisted vehicle insurance claim assessment platform that helps users submit claim information, upload supporting evidence, and review claim progress.
        </p>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          This Privacy Policy explains what personal information ClaimPilot may collect, how it may be used, when it may be shared, and what choices you may have regarding your information.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          2. Information We Collect
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Depending on how you use ClaimPilot, we may collect the following information:
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Account information:</strong> Name, email address, phone number, date of birth, and authentication information, where required.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Vehicle information:</strong> Vehicle model, registration or HSRP number, engine number, and chassis number.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Claim information:</strong> Insurance policy details, accident date and location, incident description, and other information relevant to your claim.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Driver information:</strong> Driver's name, driving licence number, and licence images, where requested.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Photos and videos:</strong> Images of vehicle damage and other evidence you submit to support your claim.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Assessment and review information:</strong> AI-generated findings, possible damage classifications, indicative repair cost estimates, duplicate-evidence indicators, agent decisions, and related notes.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Technical information:</strong> Information required to operate, maintain, and troubleshoot the platform, where collected.
          </p>
        </div>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Please avoid uploading information that is unrelated to your claim.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          3. How We Use Your Information
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Your information may be used to:
        </p>
        <ul
          style={{
            paddingLeft: '1.25rem',
            margin: '0 0 0.75rem 0',
            color: 'var(--text-secondary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.375rem',
          }}
        >
          <li>Create and manage your account.</li>
          <li>Verify account access and communicate with you.</li>
          <li>Receive and process insurance claim submissions.</li>
          <li>Analyse submitted images and videos for visible vehicle damage.</li>
          <li>Generate indicative repair estimates and identify potentially duplicated evidence.</li>
          <li>Help authorised reviewers assess claims and record decisions.</li>
          <li>Respond to questions, investigate suspected misuse, and maintain the platform.</li>
        </ul>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          AI-generated assessments may be inaccurate or incomplete. They are intended to assist claim evaluation and should not be treated as a guarantee of claim approval, repair costs, or insurance payment.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          4. How Information May Be Shared
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Your information may be shared when necessary to provide ClaimPilot's services, including:
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.75rem' }}>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Authorised claim reviewers:</strong> To review claim details, supporting evidence, and assessment results.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Service providers:</strong> With hosting, storage, authentication, communication, or AI service providers where they are actually used to operate the platform.
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Legal authorities:</strong> Where disclosure is required by applicable law or valid legal process.
          </p>
        </div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Information shared with a service provider may be processed under that provider's applicable terms and privacy practices.
        </p>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          ClaimPilot does not intend to sell your personal information for third-party marketing. Any additional sharing practices must be accurately disclosed before this policy is published.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          5. AI and Automated Assessment
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          ClaimPilot may use AI-assisted tools to identify visible vehicle damage, analyse submitted evidence, estimate possible repair costs, and flag potentially duplicated images or inconsistencies.
        </p>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          These tools have limitations. Results may be incorrect, and a flagged item does not by itself establish fraud or wrongdoing. Claim decisions should be made through the applicable review process rather than relying solely on an automated result.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          6. Data Storage and Security
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          ClaimPilot uses technical and organisational measures intended to protect personal information against unauthorised access, loss, misuse, or disclosure.
        </p>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          However, no online platform can guarantee absolute security. Access to information and evidence should be restricted according to the platform's actual permissions and security configuration.
        </p>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Information may be processed or stored by third-party providers used to operate ClaimPilot. The hosting locations, applicable safeguards, and relevant providers must be confirmed before this policy is finalised.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          7. Data Retention and Deletion
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Personal information may be retained for as long as necessary to provide the service, manage claims, maintain relevant records, meet legal obligations, or resolve disputes.
        </p>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Actual retention periods and deletion procedures depend on the data involved and the platform's implemented practices. Where available, users may request access to, correction of, or deletion of their personal information, subject to applicable legal obligations.
        </p>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Specific retention periods and the account deletion process must be confirmed before publication.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          8. Your Privacy Choices and Rights
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          Depending on applicable law, you may have rights concerning your personal information, including requesting access, correction, deletion, or other available remedies.
        </p>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          To make a privacy-related request or ask how your information is handled, contact us using the details provided below.
        </p>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          Some information may need to be retained where required by law or necessary for legitimate operational purposes.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          9. Children's Privacy
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          ClaimPilot is intended for adults aged 18 and above. We do not knowingly seek to collect personal information from children. If you believe a child has provided personal information through the platform, please contact us so the matter can be reviewed.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          10. Changes to This Policy
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          This Privacy Policy may be updated as ClaimPilot's services, data practices, or legal requirements change. The latest revision date will be displayed at the top of this document. Where required, users will be notified of significant changes in accordance with applicable law.
        </p>
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
          11. Contact Us
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
          For questions, concerns, or requests regarding this Privacy Policy, contact:
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', marginBottom: '0.75rem' }}>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Platform/operator legal name:</strong> [LEGAL NAME]
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Email:</strong> [PRIVACY OR SUPPORT EMAIL]
          </p>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Address:</strong> [BUSINESS ADDRESS, IF APPLICABLE]
          </p>
        </div>
      </section>

      <footer style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginTop: '0.5rem' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', margin: 0, fontStyle: 'italic' }}>
          End of Claimpilot Privacy Policy
        </p>
      </footer>
    </article>
  );
};
