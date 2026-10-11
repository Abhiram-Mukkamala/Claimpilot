import { apiRequest } from './claimsApi';

export interface AdvancedAnalysisData {
  image: string;
  clahe: {
    image: string;
  };
  yolo: {
    detections: Array<{
      class: string;
      confidence: number;
      bbox: [number, number, number, number]; // x, y, w, h percentages
    }>;
  };
  sam2: {
    mask: string;
    segmentedAreaPx: number;
  };
  deformation: {
    minMm: number;
    maxMm: number;
    depthMap: string;
  };
  dsine: {
    normalMap: string;
  };
}

export const advancedAnalysisApi = {
  getAnalysis: async (claimId?: string): Promise<AdvancedAnalysisData> => {
    if (claimId) {
      try {
        const storedUser = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
        const user = storedUser ? JSON.parse(storedUser) : null;
        const isAgent = user?.role === 'agent' || window.location.pathname.startsWith('/agent');

        const endpoint = isAgent ? `/agent/claims/${claimId}` : `/claims/${claimId}`;
        const res = await apiRequest<any>(endpoint);
        const aiData = res?.ai_analysis;
        const evidence = res?.evidence || [];
        const photo = evidence.find((e: any) => e.category === 'photo')?.file_url || aiData?.image_url || "https://images.unsplash.com/photo-1590240974967-0c67e96fa47e?auto=format&fit=crop&q=80&w=800";

        if (aiData) {
          return {
            image: photo,
            clahe: {
              image: aiData.clahe_image_url || photo
            },
            yolo: {
              detections: Array.isArray(aiData.detected_damages) && aiData.detected_damages.length > 0
                ? aiData.detected_damages.map((d: any) => ({
                  class: d.class || d.type || d.part || 'damage',
                  confidence: d.confidence || 0.9,
                  bbox: d.bbox || [d.boundingBox?.x || 30, d.boundingBox?.y || 30, d.boundingBox?.width || 20, d.boundingBox?.height || 20]
                }))
                : []
            },
            sam2: {
              mask: aiData.segmentation_masks?.mask || aiData.segmentation_masks?.mask_url || "/mock/damage-mask.svg",
              segmentedAreaPx: aiData.surface_area_px || 20034
            },
            deformation: {
              minMm: 0,
              maxMm: aiData.relative_deformation_z?.max_indentation_mm || 18.7,
              depthMap: aiData.relative_deformation_z?.depth_map_url || "/mock/depth-map.svg"
            },
            dsine: {
              normalMap: aiData.dsine_vectors?.normal_map_url || "/mock/normal-map.svg"
            }
          };
        }
      } catch (e) {
        console.warn('[ADVANCED ANALYSIS API] Dynamic fetch failed:', e);
        throw e;
      }
    }
    throw new Error('claimId is required to fetch advanced analysis');
  }
};