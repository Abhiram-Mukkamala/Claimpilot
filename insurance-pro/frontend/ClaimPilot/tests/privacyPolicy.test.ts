import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Privacy Policy Content & Integrity', () => {
  const contentPath = path.resolve(__dirname, '../src/components/legal/PrivacyPolicyContent.tsx');
  const fileContent = fs.readFileSync(contentPath, 'utf-8');

  test('PrivacyPolicyContent file exists and contains the exact title', () => {
    assert.ok(fileContent.includes('ClaimPilot — Privacy Policy'));
  });

  test('contains last updated placeholder [DATE]', () => {
    assert.ok(fileContent.includes('Last Updated: [DATE]'));
  });

  test('contains all 11 required section titles and numbering', () => {
    const requiredSections = [
      '1. Introduction',
      '2. Information We Collect',
      '3. How We Use Your Information',
      '4. How Information May Be Shared',
      '5. AI and Automated Assessment',
      '6. Data Storage and Security',
      '7. Data Retention and Deletion',
      '8. Your Privacy Choices and Rights',
      '9. Children\'s Privacy',
      '10. Changes to This Policy',
      '11. Contact Us',
    ];

    for (const section of requiredSections) {
      assert.ok(
        fileContent.includes(section),
        `Missing expected section: ${section}`
      );
    }
  });

  test('contains required placeholders unmodified', () => {
    const requiredPlaceholders = [
      '[DATE]',
      '[LEGAL NAME]',
      '[PRIVACY OR SUPPORT EMAIL]',
      '[BUSINESS ADDRESS, IF APPLICABLE]',
    ];

    for (const placeholder of requiredPlaceholders) {
      assert.ok(
        fileContent.includes(placeholder),
        `Missing expected placeholder: ${placeholder}`
      );
    }
  });

  test('contains the policy conclusion marker', () => {
    assert.ok(fileContent.includes('End of Claimpilot Privacy Policy'));
  });

  test('Customer login page integrates the Privacy Policy link and modal', () => {
    const loginPath = path.resolve(__dirname, '../src/pages/Login.tsx');
    const loginContent = fs.readFileSync(loginPath, 'utf-8');

    assert.ok(loginContent.includes('Privacy Policy'), 'Login page must have a visible Privacy Policy link');
    assert.ok(loginContent.includes('PrivacyPolicyModal'), 'Login page must render PrivacyPolicyModal');
    assert.ok(loginContent.includes('showPrivacyPolicy'), 'Login page must have state for opening the modal');
  });
});
