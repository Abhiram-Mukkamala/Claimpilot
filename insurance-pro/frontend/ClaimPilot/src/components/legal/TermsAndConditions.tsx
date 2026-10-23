import React from 'react';
import { TERMS_AND_CONDITIONS_TEXT } from './termsContent';

export { TERMS_AND_CONDITIONS_TEXT };

export const TermsAndConditions: React.FC = () => {
  return (
    <div className="legal-doc-container">
      <div className="legal-doc-header">
        <h1 className="legal-doc-main-title">ClaimPilot — Terms &amp; Conditions</h1>
        <span className="legal-doc-badge">Last Updated: 20th October, 2026</span>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">Introduction</h2>
        <p className="legal-paragraph">
          Welcome to ClaimPilot. These Terms &amp; Conditions (“Terms”) govern your use of the ClaimPilot website and application (“Platform”). By creating an account or using the Platform, you agree to these Terms. If you do not agree, please do not use the Platform.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">1. About ClaimPilot</h2>
        <p className="legal-paragraph">
          ClaimPilot is a technology platform designed to help users submit and track vehicle insurance claims, upload supporting evidence, and view AI-assisted vehicle damage assessments. The Platform may also support claim reviews by authorized reviewers.
        </p>
        <p className="legal-paragraph">
          ClaimPilot helps organize claim information and supports the assessment process. It does not guarantee insurance coverage, claim approval, or payment.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">2. Account Registration and Security</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">2.1 Eligibility</h3>
          <p className="legal-paragraph">
            You must be at least 18 years old to create an account, unless applicable law permits otherwise. You must provide accurate information when registering and update it when necessary.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">2.2 Account Information</h3>
          <p className="legal-paragraph">
            Depending on the registration process, you may be asked to provide your name, email address, phone number, date of birth, and login credentials.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">2.3 Account Security</h3>
          <p className="legal-paragraph">
            You are responsible for taking reasonable steps to keep your login credentials secure and for notifying the Platform operator if you suspect unauthorized access to your account. Do not access another person's account or share information that you are not authorized to use.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">3. Claim Submissions</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">3.1 Information Required</h3>
          <p className="legal-paragraph">
            When submitting a claim, you may be asked to provide relevant information such as:
          </p>
          <ul className="legal-list">
            <li>Insurance policy details.</li>
            <li>Vehicle model, registration or HSRP details, engine number, and chassis number.</li>
            <li>Driver information and driving licence details.</li>
            <li>Accident date, location, incident description, and supporting evidence.</li>
          </ul>
          <p className="legal-paragraph">
            The information requested may depend on the claim and the features available on the Platform.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">3.2 Accuracy of Information</h3>
          <p className="legal-paragraph">
            You are responsible for ensuring that the information and documents you submit are accurate and complete to the best of your knowledge. You must correct material errors when you become aware of them.
          </p>
          <p className="legal-paragraph">
            Submitting intentionally false, misleading, fabricated, or fraudulent information is prohibited and may result in account restrictions or other action permitted by law.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">3.3 Claim Eligibility and Processing</h3>
          <p className="legal-paragraph">
            Submitting a claim through ClaimPilot does not guarantee that it will be accepted or processed by an insurer. Claim eligibility and outcomes may depend on the applicable policy, the information provided, the insurer's procedures, and applicable law.
          </p>
          <p className="legal-paragraph">
            A claim reference or status displayed on the Platform is intended to help you track the submission. It is not, by itself, proof of insurance coverage or a payment commitment.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">4. Evidence Uploads</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">4.1 Supporting Evidence</h3>
          <p className="legal-paragraph">
            You may be able to upload photographs, videos, documents, and other evidence relevant to your claim. Such evidence may include images of vehicle damage, vehicle identifiers, or driver documentation.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">4.2 Your Responsibilities</h3>
          <p className="legal-paragraph">
            You must have the right or necessary permission to submit the evidence you upload. Do not upload material that is knowingly false, unlawfully obtained, misleadingly altered, or used to misrepresent an incident.
          </p>
          <p className="legal-paragraph">
            You must not reuse another person's evidence or images from an unrelated incident to mislead a reviewer.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">4.3 Evidence Review</h3>
          <p className="legal-paragraph">
            Submitted evidence may be examined by AI-assisted tools and made available to authorized reviewers for claim assessment, subject to the Platform's actual access arrangements and Privacy Policy.
          </p>
          <p className="legal-paragraph">
            Automated systems may flag potentially duplicated or inconsistent evidence. Such a flag is an indicator for further consideration, not conclusive proof of fraud.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">4.4 Upload Requirements</h3>
          <p className="legal-paragraph">
            File types, size limits, and upload availability may depend on the features currently provided by the Platform. Follow the requirements displayed during upload.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">5. AI-Assisted Assessment</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">5.1 How AI May Be Used</h3>
          <p className="legal-paragraph">
            ClaimPilot may use artificial intelligence to help identify visible vehicle damage, analyze submitted images, identify potentially reused images, and produce preliminary assessment findings or indicative repair-cost estimates.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">5.2 Limitations</h3>
          <p className="legal-paragraph">
            AI-generated results are supporting information only. They may be incomplete, inaccurate, delayed, or unavailable. The system may miss damage, misclassify it, or produce an estimate that differs from an actual repair quotation or insurer assessment.
          </p>
          <p className="legal-paragraph">
            Any repair-cost estimate is indicative and is not a guaranteed repair cost, insurance valuation, settlement offer, or payout amount.
          </p>
          <p className="legal-paragraph">
            Automated risk indicators do not establish that fraud has occurred. A reviewer or other authorized decision-maker must consider the relevant circumstances and evidence.
          </p>
          <p className="legal-paragraph">
            You should not rely solely on AI-generated results as a substitute for a qualified vehicle inspection, professional advice, or an insurer's assessment.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">6. Claim Review and Decisions</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">6.1 Review Process</h3>
          <p className="legal-paragraph">
            Claim information and supporting evidence may be reviewed by authorized personnel. Reviewers may assess submitted information, consider available assessment results, record a decision, or request additional information where the Platform supports those actions.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">6.2 Possible Outcomes</h3>
          <p className="legal-paragraph">
            Depending on the available workflow, a claim may be pending review, under review, approved, rejected, or awaiting additional information. The labels displayed by the Platform are intended to communicate the recorded status of the claim.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">6.3 Approval Does Not Guarantee Payment</h3>
          <p className="legal-paragraph">
            A claim marked as approved on ClaimPilot does not, by itself, establish that an insurer has accepted liability under a policy or initiated or completed a payout.
          </p>
          <p className="legal-paragraph">
            Final insurance decisions and payments are subject to the applicable policy, insurer procedures, and applicable law. ClaimPilot does not guarantee a particular decision, settlement amount, or payment date.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">6.4 Questions About a Decision</h3>
          <p className="legal-paragraph">
            If you disagree with a claim decision or believe information has been recorded incorrectly, use the review or support options made available to you. You may also contact the relevant insurer through its official channels when the matter concerns your policy or insurance decision.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">7. Notifications</h2>
        <p className="legal-paragraph">
          The Platform may provide account or claim-related notifications where these features are available. Delivery may be affected by incorrect contact information, technical problems, or third-party service interruptions.
        </p>
        <p className="legal-paragraph">
          You are responsible for keeping your contact details up to date and checking the Platform for relevant claim information. Do not assume that a notification has been delivered unless delivery is confirmed.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">8. Acceptable Use</h2>
        <p className="legal-paragraph">You agree not to:</p>
        <ul className="legal-list">
          <li>Submit fraudulent, fabricated, or intentionally misleading claim information or evidence.</li>
          <li>Impersonate another person or use an account without authorization.</li>
          <li>Access another user's claims, account, or evidence without permission.</li>
          <li>Attempt to bypass authentication or access restrictions.</li>
          <li>Interfere with the Platform, introduce malicious files, or misuse its features.</li>
          <li>Attempt to manipulate automated assessments for a deceptive purpose.</li>
          <li>Use the Platform in violation of applicable law or the rights of others.</li>
        </ul>
        <p className="legal-paragraph">
          Where reasonably necessary and permitted by law, suspected misuse may result in an investigation, access restrictions, account suspension, or referral to the appropriate authorities.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">9. Intellectual Property and Submitted Content</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">9.1 Platform Ownership</h3>
          <p className="legal-paragraph">
            The ClaimPilot name, branding, software, interface, and other Platform materials are owned by or licensed to their respective rights holders. You may not copy, redistribute, or commercially exploit protected materials without permission, except where permitted by law.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">9.2 Your Content</h3>
          <p className="legal-paragraph">
            You retain the rights you hold in the photographs, videos, documents, and other content you submit. You grant the Platform operator permission to host, store, process, analyze, and display that content as reasonably necessary to provide the requested claim-related services and operate the Platform, subject to applicable law and the Privacy Policy.
          </p>
          <p className="legal-paragraph">
            This permission does not transfer ownership of your content to ClaimPilot. Any additional use of personal information or submitted content must be addressed in the Privacy Policy and comply with applicable law.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">10. Privacy and Personal Information</h2>
        <p className="legal-paragraph">
          ClaimPilot may process account details, vehicle information, driver information, claim descriptions, uploaded evidence, and assessment results to provide its features.
        </p>
        <p className="legal-paragraph">
          The separate ClaimPilot Privacy Policy explains the Platform's data practices, including how information is collected, used, stored, shared, retained, and handled in response to privacy requests.
        </p>
        <p className="legal-paragraph">
          Please read the Privacy Policy alongside these Terms. Where required by law, consent or another appropriate legal basis will be obtained for the relevant processing.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">11. Availability and Disclaimers</h2>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">11.1 Service Availability</h3>
          <p className="legal-paragraph">
            The Platform and its features may occasionally be unavailable, delayed, changed, or discontinued. AI processing, notifications, uploads, and third-party services may experience interruptions.
          </p>
          <p className="legal-paragraph">
            We will make reasonable efforts to maintain the Platform, but uninterrupted or error-free operation cannot be guaranteed.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">11.2 No Guarantee of Outcomes</h3>
          <p className="legal-paragraph">
            ClaimPilot provides technology-assisted claim management and assessment features. Unless expressly stated otherwise, the Platform does not act as your insurer and does not guarantee claim approval, coverage, repair costs, settlement amounts, or insurance payments.
          </p>
        </div>
        <div className="legal-subsection">
          <h3 className="legal-subsection-title">11.3 Limitation of Liability</h3>
          <p className="legal-paragraph">
            To the extent permitted by applicable law, the Platform operator will not be liable for indirect or consequential losses arising from use of, or inability to use, the Platform.
          </p>
          <p className="legal-paragraph">
            Nothing in these Terms excludes or restricts liability, consumer protections, or other rights that cannot lawfully be excluded or restricted. Any limitation of liability is subject to applicable law.
          </p>
        </div>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">12. Suspension and Termination</h2>
        <p className="legal-paragraph">
          You may stop using ClaimPilot at any time.
        </p>
        <p className="legal-paragraph">
          Where reasonably necessary and permitted by law, the Platform operator may suspend or restrict access for suspected fraud, unauthorized access, misuse, security concerns, or material violations of these Terms.
        </p>
        <p className="legal-paragraph">
          Where appropriate, notice or an opportunity to address the issue may be provided. Handling of personal information after account closure or termination is governed by the Privacy Policy and applicable law.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">13. Changes to These Terms</h2>
        <p className="legal-paragraph">
          These Terms may be updated to reflect changes to the Platform, its features, or applicable legal requirements. The latest version should display its effective or last-updated date.
        </p>
        <p className="legal-paragraph">
          Where required by law, users will be notified of material changes or asked to provide renewed consent. Updated Terms will not remove rights that applicable law does not permit us to remove.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">14. Governing Law and Disputes</h2>
        <p className="legal-paragraph">
          These Terms shall be governed by the laws of India, subject to applicable mandatory laws and legal protections.
        </p>
        <p className="legal-paragraph">
          Subject to applicable law, the competent courts in Pune, Maharashtra, India, shall have jurisdiction over disputes arising out of or in connection with these Terms, to the extent such courts are legally competent to hear those disputes.
        </p>
        <p className="legal-paragraph">
          Nothing in this section limits any mandatory consumer rights, statutory remedies, or other legal protections available under applicable law.
        </p>
      </div>

      <div className="legal-section">
        <h2 className="legal-section-title">15. Contact</h2>
        <p className="legal-paragraph">For questions about these Terms or the Platform:</p>
        <div className="legal-contact-card">
          <div><strong>Platform operator:</strong> Claimpilot</div>
          <div><strong>Email:</strong> <a href="mailto:claimpilotofficial@gmail.com" style={{ color: 'var(--text-primary)', textDecoration: 'underline' }}>claimpilotofficial@gmail.com</a></div>
          <div><strong>Address:</strong> Pune, Maharashtra, India</div>
        </div>
      </div>

      <div className="legal-doc-footer-notice">
        End of ClaimPilot Terms &amp; Conditions.
      </div>
    </div>
  );
};
