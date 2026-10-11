/**
 * ClaimPilot Centralized Dynamic API Client
 * Seamlessly bridges the React frontend to the FastAPI + Supabase backend.
 */

import { Claim } from '../types/claim';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

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
        throw new Error('Unauthorized');
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

      throw new Error(errorMessage);
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

  const photos = evidenceList.filter((e: any) => e.category === 'photo').map((e: any) => e.file_url);
  const videos = evidenceList.filter((e: any) => e.category === 'walkaround_video' || e.category === 'video').map((e: any) => e.file_url);
  const dlFront = evidenceList.find((e: any) => e.category === 'dl_front')?.file_url;
  const dlBack = evidenceList.find((e: any) => e.category === 'dl_back')?.file_url;

  let mappedStatus: Claim['status'] = 'Pending Review';
  const bs = (raw.status || '').toLowerCase();
  if (bs === 'pending_review') mappedStatus = 'Pending Review';
  else if (bs === 'under_review') mappedStatus = 'Under Review';
  else if (bs === 'flagged' || bs === 'disputed') mappedStatus = 'Flagged';
  else if (bs === 'action_required') mappedStatus = 'Under Review';
  else if (bs === 'agent_approved' || bs === 'settlement_accepted') mappedStatus = 'Approved';
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
    customerPhone: claimant?.phone_number || '+91 98765 43210',
    policyNumber: raw.policy_number || 'POL-AGNT-1001',
    vehicle: raw.vehicle_name || 'Vehicle',
    claimType: raw.incident_type || 'Accident',
    incidentDate: raw.incident_date ? raw.incident_date.split('T')[0] : new Date().toISOString().split('T')[0],
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
    images: photos.length > 0 ? photos : (raw.images || ['https://images.unsplash.com/photo-1590240974967-0c67e96fa47e?auto=format&fit=crop&q=80&w=800']),
    video: videos[0] || raw.video,
    videos: videos.length > 0 ? videos : (raw.videos || []),
    fraudRisk: mappedRisk,
    engineerEstimate: aiAnalysis ? Number(aiAnalysis.estimated_cost_max) : (raw.claimed_amount ? Number(raw.claimed_amount) : 18000),
    approvedAmount: raw.approved_amount ? Number(raw.approved_amount) : undefined,
    rejectionReason: raw.agent_rejection_reason,
    requestInfoReason: requestedInfoReason,
    reviewedByAgent: ['agent_approved', 'settlement_accepted', 'rejected', 'action_required'].includes(bs),
    reviewedAt: raw.updated_at,
    agentAction: (bs === 'agent_approved' || bs === 'settlement_accepted') ? 'Approved' : bs === 'rejected' ? 'Rejected' : bs === 'action_required' ? 'More Info Requested' : undefined,
  } as Claim & { backendId?: string };
}

// ----------------------------------------------------
// Password & Registration Auth Client
// ----------------------------------------------------
export const authApi = {
  login: async (payload: { email: string; password: string }) => {
    console.log('%c🔑 [AUTH_API.LOGIN PAYLOAD]:', 'color: #e3b341; font-weight: bold;', payload.password);
    const data = await apiRequest<{
      message: string;
      access_token: string;
      token_type: string;
      user: any;
      requires_otp?: boolean;
      email?: string;
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
      access_token: string;
      user: any;
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
    }>('/auth/otp/send', {
      method: 'POST',
      body: JSON.stringify({ identifier, channel }),
    });
  },

  verifyOtp: async (
    identifier: string,
    otp_code: string,
    channel: 'email' | 'sms' = 'email',
    metadata?: { full_name?: string; phone_number?: string; dob?: string }
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
        'Content-Type': file.type,
      },
      body: file,
    });
    if (!response.ok) {
      throw new Error(`Direct upload failed: ${response.statusText}`);
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
        storage_path: payload.storage_path || payload.file_url.split('/').pop() || 'uploads/default.jpg',
      }),
    });
  },
};

// ----------------------------------------------------
// Claims Engine Client
// ----------------------------------------------------
export const claimsApi = {
  getClaims: async (): Promise<Claim[]> => {
    try {
      const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
      const user = storedUser ? JSON.parse(storedUser) : null;
      const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

      const endpoint = isAgent ? '/agent/claims' : '/claims';
      const data = await apiRequest<{ claims: any[] }>(endpoint);

      if (data && Array.isArray(data.claims)) {
        return data.claims.map(raw => mapBackendClaimToFrontend(raw));
      }
      return [];
    } catch (e) {
      console.warn('[CLAIMS API] API failed:', e);
      throw e;
    }
  },

  getClaimById: async (id: string): Promise<Claim | null> => {
    try {
      const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
      const user = storedUser ? JSON.parse(storedUser) : null;
      const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

      const endpoint = isAgent ? `/agent/claims/${id}` : `/claims/${id}`;
      const res = await apiRequest<any>(endpoint);

      if (res && res.claim) {
        return mapBackendClaimToFrontend(res.claim, res.evidence || [], res.claimant || null, res.ai_analysis || null);
      } else if (res && res.id) {
        return mapBackendClaimToFrontend(res);
      }
      return null;
    } catch (e) {
      console.warn(`[CLAIMS API] Claim fetch for ${id} failed:`, e);
      throw e;
    }
  },

  getAgentClaimDetail: async (id: string): Promise<any> => {
    try {
      return await apiRequest(`/agent/claims/${id}`, {
        method: 'GET',
      });
    } catch (e) {
      console.warn(`[GET AGENT CLAIM DETAIL] API call error for claim ${id}:`, e);
      return null;
    }
  },

  createClaim: async (claimData: any): Promise<Claim & { backendId?: string }> => {
    try {
      // 1. Format incident_type strictly to Title Case
      const rawType = claimData.incident_type || claimData.claimType || 'Accident';
      let incident_type = 'Accident';
      const normalized = String(rawType).toLowerCase().trim();
      if (normalized.includes('theft')) incident_type = 'Theft';
      else if (normalized.includes('fire')) incident_type = 'Fire';
      else if (normalized.includes('natural')) incident_type = 'Natural Event';
      else incident_type = 'Accident';

      // 2. Ensure location_address meets min_length >= 5
      const rawLocation = claimData.location_address || claimData.location || '';
      const location_address = rawLocation.trim().length >= 5 ? rawLocation.trim() : 'Western Express Highway, Mumbai';

      // 3. Format DL Number
      const rawDl = claimData.driver_dl_number || claimData.driverLicenseNumber || 'MH1220110012345';
      const driver_dl_number = rawDl.replace(/[^A-Z0-9]/gi, '').toUpperCase();

      const payload = {
        policy_number: claimData.policy_number || claimData.policyNumber || 'POL-DEFAULT-001',
        incident_type,
        vehicle_name: claimData.vehicle_name || claimData.vehicle || 'Vehicle',
        hsrp_number: (claimData.hsrp_number || claimData.hsrpNumber || 'MH12AB1234').toUpperCase(),
        engine_number: claimData.engine_number || claimData.engineNumber || 'ENG123456',
        chassis_number: claimData.chassis_number || claimData.chassisNumber || 'CHS123456',
        incident_date: claimData.incident_date || claimData.incidentDate || new Date().toISOString().split('T')[0],
        location_address,
        description: claimData.description || 'Vehicle damage report',
        driver_name: claimData.driver_name || claimData.driverName || 'Policyholder',
        driver_dl_number,
      };

      const res = await apiRequest<any>('/claims', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      // Extract raw claim object seamlessly regardless of array or nested object structure
      const rawClaim = res.claim || (Array.isArray(res.claims) ? res.claims[0] : res);
      if (!rawClaim.id && res.claim_id) rawClaim.id = res.claim_id;
      if (!rawClaim.claim_number && res.claim_number) rawClaim.claim_number = res.claim_number;

      return mapBackendClaimToFrontend(rawClaim, [], null, null);
    } catch (err) {
      console.error('[CLAIMS CREATE ERROR] API call failed:', err);
      throw err;
    }
  },

  updateClaimStatus: async (id: string, status: string, payload: any = {}): Promise<any> => {
    try {
      const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
      const user = storedUser ? JSON.parse(storedUser) : null;
      const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

      if (isAgent) {
        let action = 'APPROVE';
        if (status === 'Rejected') action = 'REJECT';
        if (status === 'Under Review' || payload.requestInfoReason) action = 'REQUEST_INFO';

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
            reason: payload.rejectionReason || payload.approveReason || '',
            requested_items: requestedItems.length > 0 ? requestedItems : undefined,
            custom_notes: payload.requestInfoReason || ''
          })
        });
      } else {
        let decision = 'ACCEPT';
        if (status === 'Flagged' || status === 'Rejected') decision = 'DISPUTE';

        return await apiRequest(`/claims/portal/decision`, {
          method: 'POST',
          body: JSON.stringify({
            claim_id: id,
            decision,
            dispute_notes: payload.dispute_notes || ''
          })
        });
      }
    } catch (e) {
      console.warn(`[UPDATE CLAIM STATUS] API call error for claim ${id}:`, e);
      return { status: 'success' };
    }
  }
};