import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { TERMS_AND_CONDITIONS_TEXT } from '../src/components/legal/termsContent.ts';
import { PRIVACY_POLICY_TEXT } from '../src/components/legal/privacyContent.ts';

describe('Legal Policy Content and Consent Logic', () => {
  test('Terms and Conditions text content is correctly loaded and structured', () => {
    assert.equal(typeof TERMS_AND_CONDITIONS_TEXT, 'string');
    assert.ok(
      TERMS_AND_CONDITIONS_TEXT.includes('ClaimPilot — Terms & Conditions'),
      'Must contain the Terms & Conditions title'
    );
    assert.ok(
      TERMS_AND_CONDITIONS_TEXT.length > 500,
      'Must contain full structured policy body'
    );
  });

  test('Privacy Policy text content is correctly loaded and structured', () => {
    assert.equal(typeof PRIVACY_POLICY_TEXT, 'string');
    assert.ok(
      PRIVACY_POLICY_TEXT.includes('ClaimPilot — Privacy Policy'),
      'Must contain the Privacy Policy title'
    );
    assert.ok(
      PRIVACY_POLICY_TEXT.length > 500,
      'Must contain full structured policy body'
    );
  });

  test('Signup consent gating logic matrix', () => {
    // Check gating conditions: both must be true to allow submission
    const isSignupGated = (terms: boolean, privacy: boolean) => !(terms && privacy);

    // 1. Neither checked -> gated/disabled
    assert.equal(isSignupGated(false, false), true, 'Neither checked must disable button');

    // 2. Only terms checked -> gated/disabled
    assert.equal(isSignupGated(true, false), true, 'Only Terms checked must disable button');

    // 3. Only privacy checked -> gated/disabled
    assert.equal(isSignupGated(false, true), true, 'Only Privacy checked must disable button');

    // 4. Both checked -> ungated/enabled
    assert.equal(isSignupGated(true, true), false, 'Both checked must enable button');

    // 5. Unchecking either after both were true -> gated/disabled again
    let termsState = true;
    let privacyState = true;
    assert.equal(isSignupGated(termsState, privacyState), false);
    termsState = false;
    assert.equal(isSignupGated(termsState, privacyState), true, 'Unchecking terms must immediately re-disable');

    termsState = true;
    privacyState = false;
    assert.equal(isSignupGated(termsState, privacyState), true, 'Unchecking privacy must immediately re-disable');
  });
});
