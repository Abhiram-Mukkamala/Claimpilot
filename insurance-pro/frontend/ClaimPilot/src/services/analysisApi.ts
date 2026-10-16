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
      const evidence = Array.isArray(res?.evidence) ? res.evidence : [];
      const primaryPhoto = evidence.find((e: any) => e.category === 'photo' || e.category === 'damage_photo')?.file_url;

      if (aiData) {
        const detectedDamages = Array.isArray(aiData.detected_damages) ? aiData.detected_damages : [];
        const costMin = Number(aiData.estimated_cost_min || 0);
        const costMax = Number(aiData.estimated_cost_max || 0);

        return {
          imageId: aiData.id || `img-${claimId}`,
          imageUrl: aiData.clahe_image_url || aiData.image_url || primaryPhoto || '',
          totalEstimatedCost: {
            min: costMin,
            max: costMax
          },
          damages: detectedDamages.map((d: any, idx: number) => {
            const rawConf = typeof d.confidence === 'number' ? d.confidence : undefined;
            const confidence = rawConf !== undefined
              ? Math.round(rawConf <= 1 ? rawConf * 100 : rawConf)
              : undefined;

            let boundingBox = { x: 0, y: 0, width: 0, height: 0 };
            if (d.boundingBox && typeof d.boundingBox.x === 'number') {
              boundingBox = {
                x: d.boundingBox.x,
                y: d.boundingBox.y,
                width: d.boundingBox.width,
                height: d.boundingBox.height
              };
            } else if (Array.isArray(d.bbox) && d.bbox.length === 4) {
              boundingBox = {
                x: d.bbox[0],
                y: d.bbox[1],
                width: d.bbox[2],
                height: d.bbox[3]
              };
            }

            let estimatedRepairCost = undefined;
            if (d.estimatedRepairCost && typeof d.estimatedRepairCost.min === 'number') {
              estimatedRepairCost = {
                min: Number(d.estimatedRepairCost.min),
                max: Number(d.estimatedRepairCost.max)
              };
            } else if (typeof d.estimated_cost === 'number' && d.estimated_cost > 0) {
              estimatedRepairCost = {
                min: Math.round(d.estimated_cost * 0.85),
                max: Math.round(d.estimated_cost * 1.15)
              };
            }

            return {
              id: d.id || `dmg-${idx + 1}`,
              type: d.type || d.class || d.part || 'Damage',
              severity: d.severity || (confidence && confidence > 80 ? 'Severe' : 'Moderate'),
              confidence,
              location: d.location || d.part || d.class || 'Detected damage area',
              depthMm: typeof d.depth_mm === 'number' ? d.depth_mm : typeof d.depthMm === 'number' ? d.depthMm : undefined,
              boundingBox,
              estimatedRepairCost
            };
          }),
          status: detectedDamages.length > 0 ? 'available' : (costMax > 0 ? 'partial' : 'unavailable')
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

      if (aiData?.fraud_analysis) {
        return {
          claimId,
          score: aiData.fraud_analysis.score,
          riskLevel: aiData.fraud_analysis.riskLevel,
          indicators: Array.isArray(aiData.fraud_analysis.indicators)
            ? aiData.fraud_analysis.indicators
            : [],
          status: 'available'
        };
      }

      if (claim || aiData) {
        const rawScore = typeof claim?.fraud_score === 'number' ? claim.fraud_score : (typeof aiData?.fraud_score === 'number' ? aiData.fraud_score : undefined);
        const rawRisk = claim?.risk_level || aiData?.risk_level || '';
        let riskLevel: 'LOW RISK' | 'MEDIUM RISK' | 'HIGH RISK' = 'LOW RISK';
        if (rawRisk.toUpperCase().includes('HIGH')) {
          riskLevel = 'HIGH RISK';
        } else if (rawRisk.toUpperCase().includes('MED')) {
          riskLevel = 'MEDIUM RISK';
        } else if (typeof rawScore === 'number') {
          riskLevel = rawScore >= 70 ? 'HIGH RISK' : rawScore >= 30 ? 'MEDIUM RISK' : 'LOW RISK';
        }

        const rawFlags = Array.isArray(aiData?.fraud_flags) ? aiData.fraud_flags : [];
        const indicators = rawFlags.map((f: any) => {
          if (typeof f === 'string') {
            const lower = f.toLowerCase();
            const passed = !lower.includes('inconsistent') && !lower.includes('duplicate') && !lower.includes('flag') && !lower.includes('frequent');
            return { passed, message: f };
          }
          return {
            passed: Boolean(f.passed),
            message: f.message || 'Validation Check'
          };
        });

        return {
          claimId,
          score: rawScore,
          riskLevel,
          indicators,
          status: rawScore !== undefined || indicators.length > 0 ? 'available' : 'unavailable'
        };
      }
    } catch (e) {
      console.warn(`[ANALYSIS API] Failed to fetch fraud analysis for ${claimId}:`, e);
      throw e;
    }

    return null;
  }
};