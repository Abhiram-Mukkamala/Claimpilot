import React from 'react';
import { Card } from '../ui/Card';
import { AdvancedAnalysisData } from '../../services/advancedAnalysisApi';

export const InputComparison: React.FC<{ data: AdvancedAnalysisData }> = ({ data }) => {
  return (
    <Card className="h-full flex flex-col">
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        Input + CLAHE
      </h3>

      <div className="flex gap-4 mb-4">
        <div className="flex-1">
          <p className="text-xs text-muted mb-2 uppercase font-bold">Raw Input</p>
          <img src={data.image} alt="Raw Input" className="w-full rounded-md border border-border" />
        </div>
        <div className="flex-1">
          <p className="text-xs text-muted mb-2 uppercase font-bold">CLAHE De-glared</p>
          <img src={data.clahe.image} alt="CLAHE" className="w-full rounded-md border border-border" />
        </div>
      </div>

      <div className="mt-auto">
        <p className="text-xs text-muted mb-2 font-bold">Specular Glare Distribution</p>
        <div className="h-24 w-full bg-bg-secondary rounded-md border border-border flex items-end p-2 gap-1">
          {/* Mock Histogram */}
          {[20, 30, 45, 60, 80, 50, 40, 25, 15, 10, 5, 12, 18, 30, 40, 20, 10, 5].map((val, i) => (
            <div key={i} className="flex-1 bg-accent-primary opacity-70 hover:opacity-100 transition-opacity rounded-t-sm" style={{ height: `${val}%` }}></div>
          ))}
        </div>
      </div>
    </Card>
  );
};
