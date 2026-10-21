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
        const photo = evidence.find((e: any) => e.category === 'photo' || e.category === 'damage_photo')?.file_url || aiData?.clahe_image_url || aiData?.image_url || '';

        if (aiData) {
          const detections = Array.isArray(aiData.detected_damages) && aiData.detected_damages.length > 0
            ? aiData.detected_damages.map((d: any) => {
              const rawConf = typeof d.confidence === 'number' ? d.confidence : 0;
              const confNorm = rawConf > 1 ? rawConf / 100 : rawConf;
              let bbox: [number, number, number, number] = [0, 0, 0, 0];
              if (Array.isArray(d.bbox) && d.bbox.length === 4) {
                bbox = [d.bbox[0], d.bbox[1], d.bbox[2], d.bbox[3]];
              } else if (d.boundingBox) {
                bbox = [d.boundingBox.x ?? 0, d.boundingBox.y ?? 0, d.boundingBox.width ?? 0, d.boundingBox.height ?? 0];
              }
              return {
                class: d.class || d.type || d.part || 'damage',
                confidence: confNorm,
                bbox
              };
            })
            : [];

          return {
            image: photo,
            clahe: {
              image: aiData.clahe_image_url || photo
            },
            yolo: {
              detections
            },
            sam2: {
              mask: aiData.segmentation_masks?.mask || aiData.segmentation_masks?.mask_url || '',
              segmentedAreaPx: Number(aiData.surface_area_px || 0)
            },
            deformation: {
              minMm: 0,
              maxMm: Number(aiData.relative_deformation_z?.max_indentation_mm || aiData.relative_deformation_z?.max_depth_mm || 0),
              depthMap: aiData.relative_deformation_z?.depth_map_url || ''
            },
            dsine: {
              normalMap: aiData.dsine_vectors?.normal_map_url || ''
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