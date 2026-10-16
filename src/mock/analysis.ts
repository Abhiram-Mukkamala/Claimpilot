import { DamageAnalysis, FraudAnalysis } from '../types/analysis';

export const mockDamageAnalysis: Record<string, DamageAnalysis> = {
  'CLM-1024': {
    imageId: 'img-1',
    imageUrl: 'https://images.unsplash.com/photo-1590240974967-0c67e96fa47e?auto=format&fit=crop&q=80&w=800',
    totalEstimatedCost: { min: 18000, max: 24000 },
    damages: [
      {
        id: 'dmg-1',
        type: 'Front Bumper',
        severity: 'Moderate',
        confidence: 91,
        location: 'Crack / Deformation',
        boundingBox: { x: 20, y: 60, width: 60, height: 25 },
        estimatedRepairCost: { min: 12000, max: 16000 }
      },
      {
        id: 'dmg-2',
        type: 'Left Headlight',
        severity: 'Broken',
        confidence: 87,
        location: 'Front Left',
        boundingBox: { x: 70, y: 40, width: 15, height: 15 },
        estimatedRepairCost: { min: 6000, max: 8000 }
      }
    ]
  },
  'CLM-1025': {
    imageId: 'img-2',
    imageUrl: 'https://images.unsplash.com/photo-1563223771-5f8f8b6f3a38?auto=format&fit=crop&q=80&w=800',
    totalEstimatedCost: { min: 25000, max: 35000 },
    damages: [
      {
        id: 'dmg-3',
        type: 'Rear Door',
        severity: 'Severe',
        confidence: 94,
        location: 'Dent and Scratch',
        boundingBox: { x: 30, y: 40, width: 40, height: 40 },
        estimatedRepairCost: { min: 15000, max: 20000 }
      },
      {
        id: 'dmg-4',
        type: 'Rear Bumper',
        severity: 'Moderate',
        confidence: 82,
        location: 'Crack',
        boundingBox: { x: 20, y: 80, width: 60, height: 15 },
        estimatedRepairCost: { min: 10000, max: 15000 }
      }
    ]
  },
  'CLM-1026': {
    imageId: 'img-3',
    imageUrl: 'https://images.unsplash.com/photo-1542282088-fe8426682b8f?auto=format&fit=crop&q=80&w=800',
    totalEstimatedCost: { min: 8000, max: 12000 },
    damages: [
      {
        id: 'dmg-5',
        type: 'Headlight',
        severity: 'Moderate',
        confidence: 95,
        location: 'Broken',
        boundingBox: { x: 60, y: 50, width: 20, height: 20 },
        estimatedRepairCost: { min: 8000, max: 12000 }
      }
    ]
  }
};

export const mockFraudAnalysis: Record<string, FraudAnalysis> = {
  'CLM-1024': {
    claimId: 'CLM-1024',
    score: 22,
    riskLevel: 'LOW RISK',
    indicators: [
      { passed: true, message: 'No duplicate claim detected' },
      { passed: true, message: 'Damage is consistent with description' },
      { passed: true, message: 'Image evidence is unique' },
      { passed: true, message: 'No suspicious claim history detected' }
    ]
  },
  'CLM-1025': {
    claimId: 'CLM-1025',
    score: 55,
    riskLevel: 'MEDIUM RISK',
    indicators: [
      { passed: true, message: 'No duplicate claim detected' },
      { passed: false, message: 'Slight inconsistency in incident date' },
      { passed: true, message: 'Image evidence is unique' }
    ]
  },
  'CLM-1026': {
    claimId: 'CLM-1026',
    score: 78,
    riskLevel: 'HIGH RISK',
    indicators: [
      { passed: false, message: 'Similar image detected in previous claim' },
      { passed: false, message: 'Damage description does not match detected damage' },
      { passed: false, message: 'Multiple claims associated with vehicle' }
    ]
  }
};
