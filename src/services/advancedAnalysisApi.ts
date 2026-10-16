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

export const mockAdvancedAnalysis: AdvancedAnalysisData = {
  image: "https://images.unsplash.com/photo-1590240974967-0c67e96fa47e?auto=format&fit=crop&q=80&w=800",
  clahe: {
    image: "https://images.unsplash.com/photo-1590240974967-0c67e96fa47e?auto=format&fit=crop&q=80&w=800&sat=150&con=150"
  },
  yolo: {
    detections: [
      {
        class: "front_damage",
        confidence: 0.94,
        bbox: [65, 30, 20, 20] // approx position of the red area in SVG
      },
      {
        class: "bumper_damage",
        confidence: 0.89,
        bbox: [40, 50, 20, 10]
      }
    ]
  },
  sam2: {
    mask: "/mock/damage-mask.svg",
    segmentedAreaPx: 20034
  },
  deformation: {
    minMm: 0,
    maxMm: 18.7,
    depthMap: "/mock/depth-map.svg"
  },
  dsine: {
    normalMap: "/mock/normal-map.svg"
  }
};

/**
 * Expected future endpoint:
 * POST /api/analyze
 * Input:
 * - vehicle image
 * - optional incident narrative
 * Output: AdvancedAnalysisData
 */
export const advancedAnalysisApi = {
  getAnalysis: async (): Promise<AdvancedAnalysisData> => {
    // Simulate network delay
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(mockAdvancedAnalysis);
      }, 1500);
    });
  }
};
