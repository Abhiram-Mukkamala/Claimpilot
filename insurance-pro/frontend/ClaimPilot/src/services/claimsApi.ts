/**
 * ClaimPilot Centralized Dynamic API Client
 * Seamlessly bridges the React frontend to the FastAPI + Supabase backend.
 */

import type { Claim } from '../types/claim';

// Optional chaining keeps this module importable outside Vite (e.g. Node test runner).
export const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export async function apiRequest<T = any>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers: customHeaders, ...restOptions } = options;

  let url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  let token = '';
  try {
    const authUserStr = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
    if (authUserStr) {
      const parsed = JSON.parse(authUserStr);
      token = parsed.access_token || parsed.token || parsed.session?.access_token || '';
    }
    if (!token) {
      token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
    }
  } catch (e) {
    console.warn('[API CLIENT] Error parsing auth user from storage:', e);
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(customHeaders as Record<string, string>),
  };

  try {
    const response = await fetch(url, {
      ...restOptions,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        console.warn(`[API 401 UNAUTHORIZED] ${url}`);
        localStorage.removeItem('access_token');
        localStorage.removeItem('auth_user');
        sessionStorage.removeItem('access_token');
        sessionStorage.removeItem('auth_user');
        if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
        const err = new Error('Session expired. Please log in again.');
        (err as any).status = 401;
        throw err;
      }

      const errorJson = await response.json().catch(() => null);

      if (response.status === 422) {
        console.error('[FASTAPI 422 VALIDATION ERROR]:', errorJson?.detail);
      }

      let errorMessage = response.statusText || 'API Request Failed';
      if (errorJson?.detail) {
        if (typeof errorJson.detail === 'string') {
          errorMessage = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorMessage = errorJson.detail
            .map((err: any) => `${err.loc ? err.loc.join('.') : 'field'}: ${err.msg}`)
            .join(' | ');
        } else if (typeof errorJson.detail === 'object') {
          errorMessage = errorJson.detail.message || JSON.stringify(errorJson.detail);
        }
      }

      const apiError = new Error(errorMessage);
      (apiError as any).status = response.status;
      throw apiError;
    }

    return await response.json();
  } catch (error: any) {
    console.warn(`[API REQUEST NOTICE] ${options.method || 'GET'} ${url}:`, error.message);
    throw error;
  }
}

/**
 * Data Mapper: Transforms backend claims + evidence + ai_analysis into frontend Claim format
 */
export function mapBackendClaimToFrontend(raw: any, evidenceList: any[] = [], claimant: any = null, aiAnalysis: any = null): Claim & { backendId?: string } {
  if (!raw) return raw;

  const photos = evidenceList.filter((e: any) => e.category === 'photo' || e.category === 'damage_photo').map((e: any) => e.file_url).filter(Boolean);
  const videos = evidenceList.filter((e: any) => e.category === 'walkaround_video' || e.category === 'video').map((e: any) => e.file_url).filter(Boolean);
  const dlFront = evidenceList.find((e: any) => e.category === 'dl_front')?.file_url || raw.driver_dl_front_photo || raw.driverLicenseFrontPhoto;
  const dlBack = evidenceList.find((e: any) => e.category === 'dl_back')?.file_url || raw.driver_dl_back_photo || raw.driverLicenseBackPhoto;

  let mappedStatus: Claim['status'] = 'Pending Review';
  const bs = (raw.status || '').toLowerCase();
  if (bs === 'pending_review') mappedStatus = 'Pending Review';
  else if (bs === 'under_review') mappedStatus = 'Under Review';
  else if (bs === 'flagged') mappedStatus = 'Flagged';
  else if (bs === 'disputed') mappedStatus = 'Disputed';
  else if (bs === 'action_required') mappedStatus = 'Action Required';
  else if (bs === 'agent_approved') mappedStatus = 'Approved';
  else if (bs === 'settlement_accepted') mappedStatus = 'Settlement Accepted';
  else if (bs === 'rejected') mappedStatus = 'Rejected';
  else if (raw.status) mappedStatus = raw.status;

  let mappedRisk: 'Low' | 'Medium' | 'High' = 'Low';
  const rl = (raw.risk_level || '').toLowerCase();
  if (rl.includes('high') || (raw.fraud_score && raw.fraud_score >= 65)) mappedRisk = 'High';
  else if (rl.includes('med') || (raw.fraud_score && raw.fraud_score >= 35)) mappedRisk = 'Medium';

  const requestedInfoReason = Array.isArray(raw.requested_info_notes) && raw.requested_info_notes.length > 0
    ? (raw.requested_info_notes[raw.requested_info_notes.length - 1]?.custom_notes ||
      (raw.requested_info_notes[raw.requested_info_notes.length - 1]?.items || []).join(', ') || '')
    : undefined;

  const backendId = raw.id || raw.claim_id;
  const claimDisplayId = raw.claim_number || raw.id || 'CLM-UNKNOWN';

  return {
    id: claimDisplayId,
    backendId: backendId,
    customerId: raw.user_id || 'cust-1',
    customerName: claimant?.full_name || raw.driver_name || 'Policyholder',
    customerPhone: claimant?.phone_number || '',
    policyNumber: raw.policy_number || '',
    vehicle: raw.vehicle_name || 'Vehicle',
    claimType: raw.incident_type || 'Accident',
    incidentDate: raw.incident_date ? raw.incident_date.split('T')[0] : '',
    location: raw.location_address || raw.location || '',
    description: raw.description || '',
    engineNumber: raw.engine_number,
    chassisNumber: raw.chassis_number,
    hsrpNumber: raw.hsrp_number,
    driverName: raw.driver_name,
    driverLicenseNumber: raw.driver_dl_number,
    driverLicenseFrontPhoto: dlFront,
    driverLicenseBackPhoto: dlBack,
    submittedAt: raw.created_at || new Date().toISOString(),
    status: mappedStatus,
    rawStatus: bs,
    images: photos.length > 0 ? photos : (Array.isArray(raw.images) ? raw.images : []),
    video: videos[0] || raw.video,
    videos: videos.length > 0 ? videos : (Array.isArray(raw.videos) ? raw.videos : []),
    fraudRisk: mappedRisk,
    fraudScore: typeof raw.fraud_score === 'number' ? raw.fraud_score : undefined,
    engineerEstimate: aiAnalysis?.estimated_cost_max ? Number(aiAnalysis.estimated_cost_max) : (raw.claimed_amount ? Number(raw.claimed_amount) : undefined),
    approvedAmount: raw.approved_amount ? Number(raw.approved_amount) : undefined,
    approveReason: raw.agent_custom_notes || raw.approve_reason,
    rejectionReason: raw.agent_rejection_reason,
    requestInfoReason: requestedInfoReason,
    disputeNotes: raw.dispute_notes,
    reviewedByAgent: ['agent_approved', 'settlement_accepted', 'rejected', 'action_required', 'disputed'].includes(bs),
    reviewedAt: raw.updated_at,
    agentAction: (bs === 'agent_approved' || bs === 'settlement_accepted') ? 'Approved' : bs === 'rejected' ? 'Rejected' : bs === 'action_required' ? 'More Info Requested' : undefined,
  } as Claim & { backendId?: string };
}

// ----------------------------------------------------
// Password & Registration Auth Client
// ----------------------------------------------------
export const authApi = {
  login: async (payload: { email: string; password: string }) => {
    const data = await apiRequest<{
      message: string;
      access_token?: string;
      token_type?: string;
      user?: any;
      requires_otp?: boolean;
      email?: string;
      challenge_id?: string;
      otp_details?: {
        message: string;
        identifier: string;
        channel: string;
        expires_in_minutes: number;
        challenge_id: string;
      };
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token);
      sessionStorage.setItem('access_token', data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));
      sessionStorage.setItem('auth_user', JSON.stringify(data.user));
    }
    return data;
  },

  register: async (payload: {
    full_name: string;
    email: string;
    phone_number: string;
    dob: string;
    role?: 'customer' | 'agent';
    password: string;
  }) => {
    const data = await apiRequest<{
      message: string;
      requires_otp?: boolean;
      otp_details?: {
        message: string;
        identifier: string;
        channel: string;
        expires_in_minutes: number;
        challenge_id: string;
      };
      access_token?: string;
      user?: any;
    }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token);
      sessionStorage.setItem('access_token', data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));
      sessionStorage.setItem('auth_user', JSON.stringify(data.user));
    }
    return data;
  },

  getCurrentUser: async () => {
    return apiRequest('/auth/me');
  }
};

// ----------------------------------------------------
// Dual OTP Authentication Client (SMS & Email)
// ----------------------------------------------------
export const authOtpApi = {
  sendOtp: async (identifier: string, channel: 'email' | 'sms' = 'email') => {
    return apiRequest<{
      message: string;
      identifier: string;
      channel: string;
      expires_in_minutes: number;
      challenge_id: string;
    }>('/auth/otp/send', {
      method: 'POST',
      body: JSON.stringify({ identifier, channel }),
    });
  },

  verifyOtp: async (
    identifier: string,
    otp_code: string,
    channel: 'email' | 'sms' = 'email',
    metadata?: { full_name?: string; phone_number?: string; dob?: string; password?: string },
    challenge_id?: string
  ) => {
    const data = await apiRequest<{
      message: string;
      is_verified: boolean;
      access_token: string;
      token_type: string;
      user: any;
    }>('/auth/otp/verify', {
      method: 'POST',
      body: JSON.stringify({
        identifier,
        otp_code,
        channel,
        ...(challenge_id ? { challenge_id } : {}),
        ...(metadata && { metadata }),
      }),
    });

    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token);
      sessionStorage.setItem('access_token', data.access_token);
      localStorage.setItem('auth_user', JSON.stringify(data.user));
      sessionStorage.setItem('auth_user', JSON.stringify(data.user));
    }
    return data;
  },
};

// ----------------------------------------------------
// Storage Presigned Upload Client
// ----------------------------------------------------
export const storageApi = {
  getPresignedUploadUrl: async (payload: {
    file_name: string;
    file_type: string;
    category: 'photo' | 'walkaround_video' | 'dl_front' | 'dl_back';
    file_size_bytes: number;
  }) => {
    return apiRequest<{
      upload_url: string;
      file_path: string;
      public_url: string;
      expires_in_seconds: number;
      category: string;
    }>('/storage/presigned-url', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  uploadFileDirectly: async (uploadUrl: string, file: File) => {
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type || 'application/octet-stream',
      },
      body: file,
    });
    if (!response.ok) {
      throw new Error(`Direct upload failed (${response.status}): ${response.statusText}`);
    }
    return response;
  },

  /**
   * Helper method to request a presigned URL and upload the file in one call
   */
  uploadFile: async (
    file: File,
    category: 'photo' | 'walkaround_video' | 'dl_front' | 'dl_back'
  ): Promise<{ public_url: string; file_path: string }> => {
    const presigned = await storageApi.getPresignedUploadUrl({
      file_name: file.name,
      file_type: file.type || 'application/octet-stream',
      category,
      file_size_bytes: file.size,
    });

    await storageApi.uploadFileDirectly(presigned.upload_url, file);

    return {
      public_url: presigned.public_url,
      file_path: presigned.file_path,
    };
  },

  catalogEvidence: async (payload: {
    claim_id: string;
    file_url: string;
    storage_path: string;
    file_type: string;
    category: string;
    file_name?: string;
    file_size_bytes?: number;
  }) => {
    return apiRequest('/storage/evidence', {
      method: 'POST',
      body: JSON.stringify({
        ...payload,
        storage_path: payload.storage_path || payload.file_url,
      }),
    });
  },
};

// ----------------------------------------------------
// Customer Settlement Decision Client
// ----------------------------------------------------
// A settlement decision is only reported as successful when the backend
// responds 2xx AND confirms the expected resulting claim status. Every other
// outcome (HTTP 4xx/5xx incl. 409 and 500, auth failures, network failures,
// malformed or unconfirmed responses) is thrown as a SettlementDecisionError.
// Never convert these failures into a success-shaped result.

export type SettlementDecision = 'ACCEPT' | 'DISPUTE';
export type SettlementDecisionStatus = 'settlement_accepted' | 'disputed';
export type SettlementDecisionErrorKind = 'http' | 'network' | 'unconfirmed' | 'invalid_request';

const EXPECTED_SETTLEMENT_STATUS: Record<SettlementDecision, SettlementDecisionStatus> = {
  ACCEPT: 'settlement_accepted',
  DISPUTE: 'disputed',
};

export interface SettlementDecisionResult {
  decision: SettlementDecision;
  claimId: string;
  claimNumber?: string;
  newStatus: SettlementDecisionStatus;
  message: string;
}

export class SettlementDecisionError extends Error {
  kind: SettlementDecisionErrorKind;
  status?: number;
  serverMessage?: string;

  constructor(message: string, kind: SettlementDecisionErrorKind, status?: number, serverMessage?: string) {
    super(message);
    this.name = 'SettlementDecisionError';
    this.kind = kind;
    this.status = status;
    this.serverMessage = serverMessage;
  }

  /** True when the claim state may have changed or is unknown server-side; the UI should reload before retrying. */
  get requiresRefresh(): boolean {
    return this.kind === 'unconfirmed' || this.status === 409 || this.status === 404;
  }
}

const UNCONFIRMED_DECISION_MESSAGE =
  'The server did not confirm your settlement decision, so it may not have been recorded. Please refresh the claim to check its current status before trying again.';

export function toSettlementDecisionError(error: unknown): SettlementDecisionError {
  if (error instanceof SettlementDecisionError) return error;

  const status = typeof (error as any)?.status === 'number' ? (error as any).status as number : undefined;
  const serverMessage = typeof (error as any)?.message === 'string' ? (error as any).message as string : undefined;

  if (status !== undefined) {
    let message: string;
    if (status === 401) {
      message = 'Your session has expired. Please log in again. Your settlement decision was not recorded.';
    } else if (status === 403) {
      message = 'You are not authorized to make a settlement decision on this claim. Your decision was not recorded.';
    } else if (status === 404) {
      message = 'This claim could not be found. Your settlement decision was not recorded.';
    } else if (status === 409) {
      message = 'Your settlement decision could not be recorded because the claim could not be updated in its current state. Please refresh the claim to see its latest status before trying again.';
    } else if (status >= 500) {
      message = 'The server failed to record your settlement decision. Your decision was not confirmed — please try again in a moment.';
    } else {
      message = serverMessage
        ? `Your settlement decision was not recorded: ${serverMessage}`
        : `Your settlement decision was not recorded (HTTP ${status}).`;
    }
    return new SettlementDecisionError(message, 'http', status, serverMessage);
  }

  // fetch() rejects with a TypeError when the network request itself fails.
  if (error instanceof TypeError) {
    return new SettlementDecisionError(
      'Could not reach the ClaimPilot server. Check your connection and try again — your settlement decision was not confirmed.',
      'network',
      undefined,
      serverMessage
    );
  }

  // Anything else (e.g. an unparseable 2xx body) means we cannot confirm the outcome.
  return new SettlementDecisionError(UNCONFIRMED_DECISION_MESSAGE, 'unconfirmed', undefined, serverMessage);
}

/**
 * Validates a 2xx backend body for /claims/portal/decision. Throws unless the
 * backend explicitly confirms the claim moved to the expected status.
 */
export function confirmSettlementDecisionResponse(
  response: unknown,
  decision: SettlementDecision
): SettlementDecisionResult {
  if (!response || typeof response !== 'object' || Array.isArray(response)) {
    throw new SettlementDecisionError(UNCONFIRMED_DECISION_MESSAGE, 'unconfirmed');
  }

  const body = response as Record<string, unknown>;
  const reportedStatus = typeof body.status === 'string' ? body.status.toLowerCase() : '';
  if (body.success === false || body.error || ['error', 'failed', 'failure'].includes(reportedStatus)) {
    const serverMessage = typeof body.message === 'string' ? body.message : undefined;
    throw new SettlementDecisionError(UNCONFIRMED_DECISION_MESSAGE, 'unconfirmed', undefined, serverMessage);
  }

  const expectedStatus = EXPECTED_SETTLEMENT_STATUS[decision];
  if (body.new_status !== expectedStatus) {
    throw new SettlementDecisionError(UNCONFIRMED_DECISION_MESSAGE, 'unconfirmed');
  }

  if (body.decision !== undefined && String(body.decision).toUpperCase() !== decision) {
    throw new SettlementDecisionError(UNCONFIRMED_DECISION_MESSAGE, 'unconfirmed');
  }

  return {
    decision,
    claimId: typeof body.claim_id === 'string' ? body.claim_id : '',
    claimNumber: typeof body.claim_number === 'string' ? body.claim_number : undefined,
    newStatus: expectedStatus,
    message: typeof body.message === 'string' && body.message.trim()
      ? body.message
      : decision === 'ACCEPT'
        ? 'Settlement offer accepted.'
        : 'Settlement dispute submitted.',
  };
}

/**
 * Submits a customer settlement decision. Resolves only on a confirmed backend
 * success; rejects with SettlementDecisionError on every failure.
 */
export async function submitSettlementDecision(
  claimId: string,
  decision: SettlementDecision,
  disputeNotes = ''
): Promise<SettlementDecisionResult> {
  if (!claimId) {
    throw new SettlementDecisionError('Missing claim reference. Your settlement decision was not submitted.', 'invalid_request');
  }
  if (decision !== 'ACCEPT' && decision !== 'DISPUTE') {
    throw new SettlementDecisionError('Unsupported settlement decision. Nothing was submitted.', 'invalid_request');
  }

  let response: unknown;
  try {
    response = await apiRequest<unknown>('/claims/portal/decision', {
      method: 'POST',
      body: JSON.stringify({
        claim_id: claimId,
        decision,
        dispute_notes: decision === 'DISPUTE' ? disputeNotes : '',
      }),
    });
  } catch (error) {
    throw toSettlementDecisionError(error);
  }

  return confirmSettlementDecisionResponse(response, decision);
}

// ----------------------------------------------------
// Claims Engine Client
// ----------------------------------------------------
export const claimsApi = {
  getClaims: async (): Promise<Claim[]> => {
    const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
    const user = storedUser ? JSON.parse(storedUser) : null;
    const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

    const endpoint = isAgent ? '/agent/claims' : '/claims';
    const data = await apiRequest<{ claims: any[] }>(endpoint);

    if (data && Array.isArray(data.claims)) {
      return data.claims.map(raw => mapBackendClaimToFrontend(raw));
    }
    return [];
  },

  getClaimById: async (id: string): Promise<Claim | null> => {
    const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
    const user = storedUser ? JSON.parse(storedUser) : null;
    const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

    const endpoint = isAgent ? `/agent/claims/${id}` : `/claims/${id}`;
    const res = await apiRequest<any>(endpoint);

    if (res && res.claim) {
      return mapBackendClaimToFrontend(res.claim, res.evidence || [], res.claimant || null, res.ai_analysis || null);
    } else if (res && (res.id || res.claim_number)) {
      return mapBackendClaimToFrontend(res);
    }
    return null;
  },

  getAgentClaimDetail: async (id: string): Promise<any> => {
    return await apiRequest(`/agent/claims/${id}`, {
      method: 'GET',
    });
  },

  createClaim: async (claimData: any): Promise<Claim & { backendId?: string }> => {
    const policy_number = (claimData.policy_number || claimData.policyNumber || '').trim().toUpperCase();
    if (!policy_number) {
      throw new Error('Policy number is required to file a claim.');
    }

    const rawType = claimData.incident_type || claimData.claimType || 'Accident';
    let incident_type = 'Accident';
    const normalized = String(rawType).toLowerCase().trim();
    if (normalized.includes('theft')) incident_type = 'Theft';
    else if (normalized.includes('fire')) incident_type = 'Fire';
    else if (normalized.includes('natural')) incident_type = 'Natural Event';
    else incident_type = 'Accident';

    const location_address = (claimData.location_address || claimData.location || '').trim();
    if (location_address.length < 5) {
      throw new Error('Incident location address must be at least 5 characters.');
    }

    const rawDl = (claimData.driver_dl_number || claimData.driverLicenseNumber || '').replace(/[-\s]/g, '').toUpperCase();
    if (!rawDl) {
      throw new Error('Driver license number is required.');
    }

    const vehicle_name = (claimData.vehicle_name || claimData.vehicle || '').trim();
    if (!vehicle_name) {
      throw new Error('Vehicle name is required.');
    }

    const hsrp_number = (claimData.hsrp_number || claimData.hsrpNumber || '').trim().toUpperCase();
    if (!hsrp_number) {
      throw new Error('HSRP registration number is required.');
    }

    const engine_number = (claimData.engine_number || claimData.engineNumber || '').trim();
    if (!engine_number) {
      throw new Error('Engine number is required.');
    }

    const chassis_number = (claimData.chassis_number || claimData.chassisNumber || '').trim();
    if (!chassis_number) {
      throw new Error('Chassis number is required.');
    }

    const driver_name = (claimData.driver_name || claimData.driverName || '').trim();
    if (!driver_name) {
      throw new Error('Driver name is required.');
    }

    const description = (claimData.description || '').trim();
    if (!description) {
      throw new Error('Incident description is required.');
    }

    const incident_date = String(claimData.incident_date || claimData.incidentDate || '').trim();
    if (!incident_date) {
      throw new Error('Incident date is required.');
    }

    const payload = {
      policy_number,
      incident_type,
      vehicle_name,
      hsrp_number,
      engine_number,
      chassis_number,
      incident_date,
      location_address,
      description,
      driver_name,
      driver_dl_number: rawDl,
      claimed_amount: claimData.claimed_amount || 0.00,
    };

    const res = await apiRequest<any>('/claims', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    const rawClaim = res.claim || (Array.isArray(res.claims) ? res.claims[0] : res);
    if (!rawClaim.id && res.claim_id) rawClaim.id = res.claim_id;
    if (!rawClaim.claim_number && res.claim_number) rawClaim.claim_number = res.claim_number;

    return mapBackendClaimToFrontend(rawClaim, [], null, null);
  },

  updateClaimStatus: async (id: string, status: string, payload: any = {}): Promise<any> => {
    const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
    const user = storedUser ? JSON.parse(storedUser) : null;
    const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

    if (isAgent) {
      let action = 'APPROVE';
      if (status === 'Rejected') action = 'REJECT';
      if (status === 'Under Review' || status === 'Action Required' || payload.requestInfoReason) action = 'REQUEST_INFO';

      let requestedItems: string[] = [];
      if (action === 'REQUEST_INFO' && payload.requestInfoReason) {
        const text = payload.requestInfoReason.toLowerCase();
        if (text.includes('photo') || text.includes('image') || text.includes('picture')) requestedItems.push('photo');
        if (text.includes('video') || text.includes('footage')) requestedItems.push('walkaround_video');
        if (text.includes('document') || text.includes('report') || text.includes('fir') || text.includes('receipt')) requestedItems.push('document');
        if (text.includes('license') || text.includes('dl') || text.includes('driving')) requestedItems.push('dl_front');
        if (requestedItems.length === 0) requestedItems.push('document');
      }

      return await apiRequest(`/agent/claims/${id}/action`, {
        method: 'POST',
        body: JSON.stringify({
          action,
          reason: payload.rejectionReason || payload.approveReason || payload.reason || '',
          requested_items: requestedItems.length > 0 ? requestedItems : undefined,
          custom_notes: payload.requestInfoReason || payload.custom_notes || '',
          approved_amount: payload.approvedAmount || payload.approved_amount || undefined,
        })
      });
    } else {
      let decision: SettlementDecision;
      const requested = typeof payload.decision === 'string' ? payload.decision.toUpperCase() : '';
      if (requested === 'ACCEPT') decision = 'ACCEPT';
      else if (requested === 'DISPUTE' || requested === 'REJECT') decision = 'DISPUTE';
      else if (requested) {
        throw new SettlementDecisionError('Unsupported settlement decision. Nothing was submitted.', 'invalid_request');
      } else if (status === 'Disputed' || status === 'Flagged' || status === 'Rejected') decision = 'DISPUTE';
      else decision = 'ACCEPT';

      const claimId = payload.claimId || payload.claim_id || payload.backendId || id;
      // Delegates to the strict submitter: failures always reject, never resolve as success.
      return await submitSettlementDecision(claimId, decision, payload.dispute_notes || payload.disputeNotes || '');
    }
  },

  submitSettlementDecision,
};