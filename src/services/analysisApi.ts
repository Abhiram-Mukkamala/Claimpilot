import {  DamageAnalysis, FraudAnalysis  } from '../types/analysis';
import {  mockDamageAnalysis, mockFraudAnalysis  } from '../mock/analysis';

export const analysisApi = {
  getDamageAnalysis: async (claimId: string): Promise<DamageAnalysis | null> => {
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate analysis processing
    return mockDamageAnalysis[claimId] || null;
  },

  getFraudAnalysis: async (claimId: string): Promise<FraudAnalysis | null> => {
    await new Promise(resolve => setTimeout(resolve, 600));
    return mockFraudAnalysis[claimId] || null;
  }
};
