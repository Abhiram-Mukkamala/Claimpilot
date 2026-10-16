export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface EstimatedCost {
  min: number;
  max: number;
}

export interface DamageArea {
  id: string;
  type: string;
  severity: string;
  confidence?: number;
  location: string;
  depthMm?: number;
  boundingBox: BoundingBox;
  estimatedRepairCost?: EstimatedCost;
}

export interface DamageAnalysis {
  imageId: string;
  imageUrl?: string;
  damages: DamageArea[];
  totalEstimatedCost: EstimatedCost;
  status?: 'loading' | 'available' | 'partial' | 'unavailable' | 'failed';
}

export interface FraudAnalysis {
  claimId: string;
  score?: number;
  riskLevel: 'LOW RISK' | 'MEDIUM RISK' | 'HIGH RISK';
  indicators: {
    passed: boolean;
    message: string;
  }[];
  status?: 'loading' | 'available' | 'unavailable' | 'failed';
}
