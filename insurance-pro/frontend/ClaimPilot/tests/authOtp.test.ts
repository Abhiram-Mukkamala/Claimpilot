/**
 * OTP authentication response-contract tests.
 *
 * A session must not be created unless the backend explicitly confirms
 * verification and returns both an access token and a user object.
 */
import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { authOtpApi } from '../src/services/claimsApi.ts';

const originalFetch = globalThis.fetch;
const originalDescriptors = new Map<string, PropertyDescriptor | undefined>();
let localStore: Storage;
let sessionStore: Storage;
let responseBody: unknown;

function memoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() { return store.size; },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => { store.delete(key); },
    setItem: (key: string, value: string) => { store.set(key, String(value)); },
  };
}

function setGlobal(name: string, value: unknown) {
  if (!originalDescriptors.has(name)) {
    originalDescriptors.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  }
  Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  localStore = memoryStorage();
  sessionStore = memoryStorage();
  responseBody = undefined;
  setGlobal('localStorage', localStore);
  setGlobal('sessionStorage', sessionStore);
  globalThis.fetch = (async () => jsonResponse(responseBody)) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  for (const [name, descriptor] of originalDescriptors) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else Reflect.deleteProperty(globalThis, name);
  }
  originalDescriptors.clear();
});

const validResponse = () => ({
  message: 'OTP verified',
  is_verified: true,
  access_token: 'verified-test-token',
  token_type: 'bearer',
  user: { id: 'user-1', email: 'person@example.com', role: 'customer' },
});

describe('authOtpApi.verifyOtp — session establishment', () => {
  test('rejects an explicit is_verified=false even when a token is present', async () => {
    responseBody = { ...validResponse(), is_verified: false };

    await assert.rejects(
      authOtpApi.verifyOtp('person@example.com', '123456'),
      /verification code could not be confirmed/i,
    );
    assert.equal(localStore.getItem('access_token'), null);
    assert.equal(sessionStore.getItem('access_token'), null);
    assert.equal(localStore.getItem('auth_user'), null);
  });

  test('rejects a response with a missing verification flag', async () => {
    const { is_verified: _ignored, ...unverified } = validResponse();
    responseBody = unverified;

    await assert.rejects(
      authOtpApi.verifyOtp('person@example.com', '123456'),
      /verification code could not be confirmed/i,
    );
    assert.equal(localStore.getItem('access_token'), null);
  });

  test('rejects incomplete authenticated responses', async (t) => {
    const cases = [
      { ...validResponse(), access_token: '' },
      { ...validResponse(), user: null },
    ];
    for (const invalid of cases) {
      await t.test('does not persist an incomplete response', async () => {
        responseBody = invalid;
        await assert.rejects(
          authOtpApi.verifyOtp('person@example.com', '123456'),
          /verification code could not be confirmed/i,
        );
        assert.equal(localStore.getItem('access_token'), null);
        assert.equal(sessionStore.getItem('access_token'), null);
      });
    }
  });

  test('persists the session only for an explicitly verified complete response', async () => {
    responseBody = validResponse();

    const result = await authOtpApi.verifyOtp('person@example.com', '123456');

    assert.equal(result.is_verified, true);
    assert.equal(localStore.getItem('access_token'), 'verified-test-token');
    assert.equal(sessionStore.getItem('access_token'), 'verified-test-token');
    assert.equal(JSON.parse(localStore.getItem('auth_user') || 'null').id, 'user-1');
    assert.equal(JSON.parse(sessionStore.getItem('auth_user') || 'null').email, 'person@example.com');
  });
});
