/**
 * Settlement decision failure-propagation tests.
 *
 * Runs on Node's built-in test runner (native TypeScript type stripping, Node >= 23.6):
 *   npm test
 *
 * Guarantees: HTTP 409/500, auth failures, network failures and unconfirmed 2xx
 * responses can never produce a success-shaped settlement result.
 */
import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  claimsApi,
  submitSettlementDecision,
  SettlementDecisionError,
} from '../src/services/claimsApi.ts';

type FetchCall = { url: string; init: RequestInit };

const originalFetch = globalThis.fetch;
const originalDescriptors = new Map<string, PropertyDescriptor | undefined>();
let calls: FetchCall[] = [];

function memoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    get length() { return store.size; },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    removeItem: (k: string) => { store.delete(k); },
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
  };
}

function setGlobal(name: string, value: unknown) {
  if (!originalDescriptors.has(name)) {
    originalDescriptors.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
  }
  Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
}

function mockFetch(responder: () => Response | Promise<Response>) {
  globalThis.fetch = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    calls.push({ url: String(input), init });
    return responder();
  }) as typeof fetch;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const ACCEPT_SUCCESS_BODY = {
  status: 'success',
  decision: 'ACCEPT',
  claim_id: 'claim-uuid-1',
  claim_number: 'CLM-0001',
  new_status: 'settlement_accepted',
  message: 'Settlement offer accepted. Direct electronic payout pipeline has been queued.',
};

const DISPUTE_SUCCESS_BODY = {
  status: 'disputed',
  decision: 'DISPUTE',
  claim_id: 'claim-uuid-1',
  claim_number: 'CLM-0001',
  new_status: 'disputed',
  message: 'Claim settlement disputed. Case re-queued to Agent Dashboard with High Priority escalation.',
};

async function assertDecisionFails(
  promise: Promise<unknown>,
  expected: { status?: number; kind?: string; requiresRefresh?: boolean }
) {
  let resolvedValue: unknown = undefined;
  let rejected: unknown = undefined;
  try {
    resolvedValue = await promise;
  } catch (err) {
    rejected = err;
  }
  assert.equal(resolvedValue, undefined, `expected rejection, but resolved with ${JSON.stringify(resolvedValue)}`);
  assert.ok(rejected instanceof SettlementDecisionError, `expected SettlementDecisionError, got ${String(rejected)}`);
  const err = rejected as SettlementDecisionError;
  if (expected.status !== undefined) assert.equal(err.status, expected.status);
  if (expected.kind !== undefined) assert.equal(err.kind, expected.kind);
  if (expected.requiresRefresh !== undefined) assert.equal(err.requiresRefresh, expected.requiresRefresh);
  assert.ok(err.message.length > 0, 'error must carry a user-facing message');
  assert.doesNotMatch(err.message, /settlement offer accepted|successfully|dispute submitted/i);
}

beforeEach(() => {
  calls = [];
  const session = memoryStorage();
  session.setItem('auth_user', JSON.stringify({ role: 'customer', access_token: 'test-token' }));
  setGlobal('sessionStorage', session);
  setGlobal('localStorage', memoryStorage());
  // pathname contains '/login' so the 401 handler does not attempt a navigation.
  setGlobal('window', { location: { pathname: '/login', href: '/login' } });
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  for (const [name, descriptor] of originalDescriptors) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else delete (globalThis as Record<string, unknown>)[name];
  }
  originalDescriptors.clear();
});

describe('submitSettlementDecision — HTTP failures never become success', () => {
  for (const decision of ['ACCEPT', 'DISPUTE'] as const) {
    test(`HTTP 409 rejects for ${decision}`, async () => {
      mockFetch(() => jsonResponse(409, { detail: { message: 'Claim status update returned no rows' } }));
      await assertDecisionFails(submitSettlementDecision('claim-uuid-1', decision, 'notes'), {
        status: 409,
        kind: 'http',
        requiresRefresh: true,
      });
    });

    test(`HTTP 500 rejects for ${decision}`, async () => {
      mockFetch(() => jsonResponse(500, { detail: { message: 'Failed to update claim status', error: 'Request ID: abc' } }));
      await assertDecisionFails(submitSettlementDecision('claim-uuid-1', decision, 'notes'), {
        status: 500,
        kind: 'http',
        requiresRefresh: false,
      });
    });
  }

  test('HTTP 401 rejects and clears the session', async () => {
    mockFetch(() => jsonResponse(401, { detail: 'Not authenticated' }));
    await assertDecisionFails(submitSettlementDecision('claim-uuid-1', 'ACCEPT'), { status: 401, kind: 'http' });
    assert.equal(sessionStorage.getItem('auth_user'), null);
  });

  test('HTTP 403 rejects', async () => {
    mockFetch(() => jsonResponse(403, { detail: { message: 'Not the claim owner' } }));
    await assertDecisionFails(submitSettlementDecision('claim-uuid-1', 'ACCEPT'), { status: 403, kind: 'http' });
  });

  test('HTTP 404 rejects and requires refresh', async () => {
    mockFetch(() => jsonResponse(404, { detail: { message: 'Claim not found' } }));
    await assertDecisionFails(submitSettlementDecision('claim-uuid-1', 'ACCEPT'), {
      status: 404,
      requiresRefresh: true,
    });
  });

  test('HTTP 500 with a non-JSON body still rejects', async () => {
    mockFetch(() => new Response('Internal Server Error', { status: 500, statusText: 'Internal Server Error' }));
    await assertDecisionFails(submitSettlementDecision('claim-uuid-1', 'ACCEPT'), { status: 500 });
  });
});

describe('submitSettlementDecision — network and unconfirmed responses', () => {
  test('network failure (fetch TypeError) rejects as network error', async () => {
    mockFetch(() => { throw new TypeError('Failed to fetch'); });
    await assertDecisionFails(submitSettlementDecision('claim-uuid-1', 'ACCEPT'), { kind: 'network' });
  });

  const unconfirmedBodies: Array<[string, () => Response]> = [
    ['missing new_status', () => jsonResponse(200, { status: 'success', decision: 'ACCEPT' })],
    ['mismatched new_status', () => jsonResponse(200, { ...ACCEPT_SUCCESS_BODY, new_status: 'agent_approved' })],
    ['mismatched decision', () => jsonResponse(200, { ...ACCEPT_SUCCESS_BODY, decision: 'DISPUTE' })],
    ['explicit status=error', () => jsonResponse(200, { ...ACCEPT_SUCCESS_BODY, status: 'error' })],
    ['explicit success=false', () => jsonResponse(200, { ...ACCEPT_SUCCESS_BODY, success: false })],
    ['null body', () => jsonResponse(200, null)],
    ['array body', () => jsonResponse(200, [])],
    ['non-JSON 200 body', () => new Response('OK', { status: 200 })],
  ];

  for (const [label, responder] of unconfirmedBodies) {
    test(`2xx with ${label} rejects as unconfirmed`, async () => {
      mockFetch(responder);
      await assertDecisionFails(submitSettlementDecision('claim-uuid-1', 'ACCEPT'), {
        kind: 'unconfirmed',
        requiresRefresh: true,
      });
    });
  }

  test('missing claim id rejects without calling the API', async () => {
    mockFetch(() => jsonResponse(200, ACCEPT_SUCCESS_BODY));
    await assertDecisionFails(submitSettlementDecision('', 'ACCEPT'), { kind: 'invalid_request' });
    assert.equal(calls.length, 0);
  });
});

describe('submitSettlementDecision — confirmed success', () => {
  test('ACCEPT resolves only with backend-confirmed settlement_accepted', async () => {
    mockFetch(() => jsonResponse(200, ACCEPT_SUCCESS_BODY));
    const result = await submitSettlementDecision('claim-uuid-1', 'ACCEPT');
    assert.equal(result.newStatus, 'settlement_accepted');
    assert.equal(result.decision, 'ACCEPT');
    assert.equal(result.message, ACCEPT_SUCCESS_BODY.message);

    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /\/claims\/portal\/decision$/);
    assert.equal(calls[0].init.method, 'POST');
    assert.deepEqual(JSON.parse(String(calls[0].init.body)), {
      claim_id: 'claim-uuid-1',
      decision: 'ACCEPT',
      dispute_notes: '',
    });
    assert.equal((calls[0].init.headers as Record<string, string>).Authorization, 'Bearer test-token');
  });

  test('DISPUTE resolves only with backend-confirmed disputed and sends notes', async () => {
    mockFetch(() => jsonResponse(200, DISPUTE_SUCCESS_BODY));
    const result = await submitSettlementDecision('claim-uuid-1', 'DISPUTE', 'OEM parts cost more');
    assert.equal(result.newStatus, 'disputed');
    assert.deepEqual(JSON.parse(String(calls[0].init.body)), {
      claim_id: 'claim-uuid-1',
      decision: 'DISPUTE',
      dispute_notes: 'OEM parts cost more',
    });
  });
});

describe('claimsApi.updateClaimStatus (customer path) — delegates strictly', () => {
  for (const status of [409, 500]) {
    test(`HTTP ${status} rejects for ACCEPT via updateClaimStatus`, async () => {
      mockFetch(() => jsonResponse(status, { detail: { message: 'failure' } }));
      await assertDecisionFails(
        claimsApi.updateClaimStatus('claim-uuid-1', 'Settlement Accepted', { decision: 'ACCEPT' }),
        { status, kind: 'http' }
      );
      assert.match(calls[0].url, /\/claims\/portal\/decision$/);
    });

    test(`HTTP ${status} rejects for DISPUTE via updateClaimStatus`, async () => {
      mockFetch(() => jsonResponse(status, { detail: { message: 'failure' } }));
      await assertDecisionFails(
        claimsApi.updateClaimStatus('claim-uuid-1', 'Disputed', { decision: 'DISPUTE', dispute_notes: 'x' }),
        { status, kind: 'http' }
      );
    });
  }

  test('unknown decision is rejected without calling the API', async () => {
    mockFetch(() => jsonResponse(200, ACCEPT_SUCCESS_BODY));
    await assertDecisionFails(
      claimsApi.updateClaimStatus('claim-uuid-1', 'Settlement Accepted', { decision: 'MAYBE' }),
      { kind: 'invalid_request' }
    );
    assert.equal(calls.length, 0);
  });
});
