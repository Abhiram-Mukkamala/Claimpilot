import React, { useState } from 'react';
import { Card } from '../ui/Card';
import { AdvancedAnalysisData } from '../../services/advancedAnalysisApi';
import { DamageScene } from '../three/DamageScene';
import { RotateCcw } from 'lucide-react';

export const DamageDeformation3D: React.FC<{ data: AdvancedAnalysisData }> = ({ data }) => {
  const [activeTab, setActiveTab] = useState<'2d' | '3d'>('3d');
  // Simple key trick to force re-mount and reset camera
  const [resetKey, setResetKey] = useState(0);

  return (
    <Card className="h-full flex flex-col relative">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-bold flex items-center gap-2">
          Relative Damage Deformation (ΔZ)
        </h3>
        <div className="flex bg-bg-secondary rounded-md p-1 border border-border text-xs">
          <button
            className={`px-3 py-1 rounded-sm transition-colors ${activeTab === '2d' ? 'bg-accent-primary text-white' : 'text-muted hover:text-white'}`}
            onClick={() => setActiveTab('2d')}
          >
            2D Heatmap (ΔZ)
          </button>
          <button
            className={`px-3 py-1 rounded-sm transition-colors ${activeTab === '3d' ? 'bg-accent-primary text-white' : 'text-muted hover:text-white'}`}
            onClick={() => setActiveTab('3d')}
          >
            Interactive 3D Surface
          </button>
        </div>
      </div>

      <div className="text-xs text-muted mb-2 flex justify-between items-center">
        <span>Estimated deformation visualization</span>
        {activeTab === '3d' && (
          <button
            onClick={() => setResetKey(k => k + 1)}
            className="flex items-center gap-1 hover:text-white transition-colors"
          >
            <RotateCcw size={12} /> Reset View
          </button>
        )}
      </div>

      <div className="relative flex-1 min-h-[300px] rounded-md border border-border overflow-hidden">
        {activeTab === '2d' ? (
          <img src={data.deformation.depthMap} alt="2D Depth Map" className="w-full h-full object-cover" />
        ) : (
          <DamageScene key={resetKey} maxDeformationMm={data.deformation.maxMm} imageUrl={data.image} />
        )}

        {/* Color Legend Overlay */}
        <div className="absolute bottom-4 right-4 bg-black bg-opacity-80 p-2 rounded border border-border-light backdrop-blur-sm pointer-events-none">
          <p className="text-[10px] text-muted mb-1 font-bold text-center">ΔZ (mm)</p>
          <div className="flex items-center gap-2">
            <span className="text-xs">0</span>
            <div className="w-24 h-3 rounded" style={{
              background: 'linear-gradient(to right, #4299e1, #38b2ac, #ecc94b, #f56565)'
            }}></div>
            <span className="text-xs text-danger font-bold">{data.deformation.maxMm}</span>
          </div>
        </div>
      </div>
    </Card>
  );
};
