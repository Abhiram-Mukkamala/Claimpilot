/**
 * Builds the authenticated Streamlit Extended View URL for either the Customer
 * (`customer_app.py`, default port 8501) or the Agent/Adjuster (`agent_app.py`, default port 8502).
 */
export function buildExtendViewUrl(claimId: string, role: 'customer' | 'agent'): string {
  const defaultBase = role === 'customer' ? 'http://localhost:8501' : 'http://localhost:8502';
  const envBase =
    role === 'customer'
      ? (import.meta.env?.VITE_CUSTOMER_EXTENDVIEW_URL || import.meta.env?.VITE_EXTENDVIEW_URL)
      : (import.meta.env?.VITE_AGENT_EXTENDVIEW_URL || import.meta.env?.VITE_EXTENDVIEW_URL);

  const baseUrl = (envBase || defaultBase).replace(/\/+$/, '');

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
  } catch {
    // Ignore storage parsing errors
  }

  const params = new URLSearchParams();
  if (claimId) {
    params.set('claim_id', claimId);
  }
  params.set('role', role);
  if (token) {
    params.set('token', token);
  }

  return `${baseUrl}/?${params.toString()}`;
}
