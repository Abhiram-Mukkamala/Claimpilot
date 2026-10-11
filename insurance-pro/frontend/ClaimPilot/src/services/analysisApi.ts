import { DamageAnalysis, FraudAnalysis } from '../types/analysis';
import { apiRequest } from './claimsApi';

export const analysisApi = {
  getDamageAnalysis: async (claimId: string): Promise<DamageAnalysis | null> => {
    try {
      const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
      const user = storedUser ? JSON.parse(storedUser) : null;
      const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

      const endpoint = isAgent ? `/agent/claims/${claimId}` : `/claims/${claimId}`;
      const res = await apiRequest<any>(endpoint);
      const aiData = res?.ai_analysis;

      if (aiData) {
        return {
          imageId: aiData.id || `img-${claimId}`,
          imageUrl: aiData.clahe_image_url || aiData.image_url || 'https://images.unsplash.com/photo-1590240974967-0c67e96fa47e?auto=format&fit=crop&q=80&w=800',
          totalEstimatedCost: {
            min: Number(aiData.estimated_cost_min || 8000),
            max: Number(aiData.estimated_cost_max || 12000)
          },
          damages: Array.isArray(aiData.detected_damages) && aiData.detected_damages.length > 0
            ? aiData.detected_damages.map((d: any, idx: number) => ({
              id: d.id || `dmg-${idx + 1}`,
              type: d.type || d.class || d.part || 'Front Bumper',
              severity: d.severity || 'Moderate',
              confidence: Math.round((d.confidence || 0.9) * (d.confidence <= 1 ? 100 : 1)),
              location: d.location || 'Crack / Deformation',
              boundingBox: d.boundingBox || {
                x: d.bbox?.[0] || 20,
                y: d.bbox?.[1] || 40,
                width: d.bbox?.[2] || 40,
                height: d.bbox?.[3] || 30
              },
              estimatedRepairCost: d.estimatedRepairCost || {
                min: Math.round((Number(d.estimated_cost) || 4000) * 0.85),
                max: Math.round((Number(d.estimated_cost) || 8000) * 1.15)
              }
            }))
            : []
        };
      }
    } catch (e) {
      console.warn(`[ANALYSIS API] Failed to fetch damage analysis for ${claimId}:`, e);
      throw e;
    }

    return null;
  },

  getFraudAnalysis: async (claimId: string): Promise<FraudAnalysis | null> => {
    try {
      const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
      const user = storedUser ? JSON.parse(storedUser) : null;
      const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

      const endpoint = isAgent ? `/agent/claims/${claimId}` : `/claims/${claimId}`;
      const res = await apiRequest<any>(endpoint);
      const claim = res?.claim || res;
      const aiData = res?.ai_analysis;

      if (claim || aiData) {
        const score = claim?.fraud_score ?? aiData?.fraud_score ?? 22;
        const rawRisk = claim?.risk_level || aiData?.risk_level || '';
        const riskLevel = rawRisk ? (rawRisk.toUpperCase().includes('HIGH') ? 'HIGH RISK' : rawRisk.toUpperCase().includes('MED') ? 'MEDIUM RISK' : 'LOW RISK') : (score >= 65 ? 'HIGH RISK' : score >= 35 ? 'MEDIUM RISK' : 'LOW RISK');

        return {
          claimId,
          score,
          riskLevel,
          indicators: Array.isArray(aiData?.fraud_flags) && aiData.fraud_flags.length > 0
            ? aiData.fraud_flags.map((f: any) => ({
              passed: typeof f === 'string' ? !f.toLowerCase().includes('inconsistent') : Boolean(f.passed),
              message: typeof f === 'string' ? f : (f.message || 'Validation Passed')
            }))
            : []
        };
      }
    } catch (e) {
      console.warn(`[ANALYSIS API] Failed to fetch fraud analysis for ${claimId}:`, e);
      throw e;
    }

    return null;
  }
};