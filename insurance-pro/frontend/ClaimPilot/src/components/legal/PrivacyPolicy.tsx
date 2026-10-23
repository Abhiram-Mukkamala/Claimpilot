import React from 'react';
import { PRIVACY_POLICY_TEXT } from './privacyContent';

export { PRIVACY_POLICY_TEXT };

export const PrivacyPolicy: React.FC = () => {
  return (
    <div className="legal-doc-container">
      <div className="legal-doc-header">
        <h1 className="legal-doc-main-title">ClaimPilot — Privacy Policy</h1>
        <span className="legal-doc-badge">Last Updated: 20th October, 2026</span>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">1. Introduction</h2>
        <p className="legal-paragraph">
          ClaimPilot is an AI-assisted vehicle insurance claim assessment platform that helps users submit claim information, upload supporting evidence, and review claim progress.
        </p>
        <p className="legal-paragraph">
          This Privacy Policy explains what personal information ClaimPilot may collect, how it may be used, when it may be shared, and what choices you may have regarding your information.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">2. Information We Collect</h2>
        <p className="legal-paragraph">
          Depending on how you use ClaimPilot, we may collect the following information:
        </p>
        <ul className="legal-list">
          <li><strong>Account information:</strong> Name, email address, phone number, date of birth, and authentication information, where required.</li>
          <li><strong>Vehicle information:</strong> Vehicle model, registration or HSRP number, engine number, and chassis number.</li>
          <li><strong>Claim information:</strong> Insurance policy details, accident date and location, incident description, and other information relevant to your claim.</li>
          <li><strong>Driver information:</strong> Driver's name, driving licence number, and licence images, where requested.</li>
          <li><strong>Photos and videos:</strong> Images of vehicle damage and other evidence you submit to support your claim.</li>
          <li><strong>Assessment and review information:</strong> AI-generated findings, possible damage classifications, indicative repair cost estimates, duplicate-evidence indicators, agent decisions, and related notes.</li>
          <li><strong>Technical information:</strong> Information required to operate, maintain, and troubleshoot the platform, where collected.</li>
        </ul>
        <p className="legal-paragraph">
          Please avoid uploading information that is unrelated to your claim.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">3. How We Use Your Information</h2>
        <p className="legal-paragraph">Your information may be used to:</p>
        <ul className="legal-list">
          <li>Create and manage your account.</li>
          <li>Verify account access and communicate with you.</li>
          <li>Receive and process insurance claim submissions.</li>
          <li>Analyse submitted images and videos for visible vehicle damage.</li>
          <li>Generate indicative repair estimates and identify potentially duplicated evidence.</li>
          <li>Help authorised reviewers assess claims and record decisions.</li>
          <li>Respond to questions, investigate suspected misuse, and maintain the platform.</li>
        </ul>
        <p className="legal-paragraph">
          AI-generated assessments may be inaccurate or incomplete. They are intended to assist claim evaluation and should not be treated as a guarantee of claim approval, repair costs, or insurance payment.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">4. How Information May Be Shared</h2>
        <p className="legal-paragraph">
          Your information may be shared when necessary to provide ClaimPilot's services, including:
        </p>
        <ul className="legal-list">
          <li><strong>Authorised claim reviewers:</strong> To review claim details, supporting evidence, and assessment results.</li>
          <li><strong>Service providers:</strong> With hosting, storage, authentication, communication, or AI service providers where they are actually used to operate the platform.</li>
          <li><strong>Legal authorities:</strong> Where disclosure is required by applicable law or valid legal process.</li>
        </ul>
        <p className="legal-paragraph">
          Information shared with a service provider may be processed under that provider's applicable terms and privacy practices.
        </p>
        <p className="legal-paragraph">
          ClaimPilot does not intend to sell your personal information for third-party marketing. Any additional sharing practices must be accurately disclosed before this policy is published.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">5. AI and Automated Assessment</h2>
        <p className="legal-paragraph">
          ClaimPilot may use AI-assisted tools to identify visible vehicle damage, analyse submitted evidence, estimate possible repair costs, and flag potentially duplicated images or inconsistencies.
        </p>
        <p className="legal-paragraph">
          These tools have limitations. Results may be incorrect, and a flagged item does not by itself establish fraud or wrongdoing. Claim decisions should be made through the applicable review process rather than relying solely on an automated result.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">6. Data Storage and Security</h2>
        <p className="legal-paragraph">
          ClaimPilot uses technical and organisational measures intended to protect personal information against unauthorised access, loss, misuse, or disclosure.
        </p>
        <p className="legal-paragraph">
          However, no online platform can guarantee absolute security. Access to information and evidence should be restricted according to the platform's actual permissions and security configuration.
        </p>
        <p className="legal-paragraph">
          Information may be processed or stored by third-party providers used to operate ClaimPilot. The hosting locations, applicable safeguards, and relevant providers must be confirmed before this policy is finalised.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">7. Data Retention and Deletion</h2>
        <p className="legal-paragraph">
          Personal information may be retained for as long as necessary to provide the service, manage claims, maintain relevant records, meet legal obligations, or resolve disputes.
        </p>
        <p className="legal-paragraph">
          Actual retention periods and deletion procedures depend on the data involved and the platform's implemented practices. Where available, users may request access to, correction of, or deletion of their personal information, subject to applicable legal obligations.
        </p>
        <p className="legal-paragraph">
          Specific retention periods and the account deletion process must be confirmed before publication.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">8. Your Privacy Choices and Rights</h2>
        <p className="legal-paragraph">
          Depending on applicable law, you may have rights concerning your personal information, including requesting access, correction, deletion, or other available remedies.
        </p>
        <p className="legal-paragraph">
          To make a privacy-related request or ask how your information is handled, contact us using the details provided below.
        </p>
        <p className="legal-paragraph">
          Some information may need to be retained where required by law or necessary for legitimate operational purposes.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">9. Children's Privacy</h2>
        <p className="legal-paragraph">
          ClaimPilot is intended for adults aged 18 and above. We do not knowingly seek to collect personal information from children. If you believe a child has provided personal information through the platform, please contact us so the matter can be reviewed.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">10. Changes to This Policy</h2>
        <p className="legal-paragraph">
          This Privacy Policy may be updated as ClaimPilot's services, data practices, or legal requirements change. The latest revision date will be displayed at the top of this document. Where required, users will be notified of significant changes in accordance with applicable law.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">11. Contact Us</h2>
        <p className="legal-paragraph">
          For questions, concerns, or requests regarding this Privacy Policy, contact:
        </p>
        <div className="legal-contact-card">
          <div><strong>Platform/operator legal name:</strong> Claimpilot</div>
          <div><strong>Email:</strong> <a href="mailto:claimpilotofficial@gmail.com" style={{ color: 'var(--text-primary)', textDecoration: 'underline' }}>claimpilotofficial@gmail.com</a></div>
          <div><strong>Address:</strong> Pune, Maharashtra, India</div>
        </div>
      </div>

      <div className="legal-doc-footer-notice">
        End of Claimpilot Privacy Policy
      </div>
    </div>
  );
};
