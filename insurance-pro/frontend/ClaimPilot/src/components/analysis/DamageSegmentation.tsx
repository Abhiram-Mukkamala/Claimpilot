import React from 'react';
import { Card } from '../ui/Card';
import { AdvancedAnalysisData } from '../../services/advancedAnalysisApi';

export const DamageSegmentation: React.FC<{ data: AdvancedAnalysisData }> = ({ data }) => {
  return (
    <Card className="h-full flex flex-col">
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        SAM2 / YOLO Segmentation
      </h3>
      <div className="relative w-full rounded-md overflow-hidden border border-border bg-bg-secondary mb-4 flex-1">
        <img src={data.image} alt="Vehicle" className="w-full h-full object-cover absolute inset-0" />

        {/* SAM2 Mask Overlay - using CSS blend modes or just absolute positioning with opacity */}
        <img src={data.sam2.mask} alt="SAM2 Mask" className="w-full h-full object-cover absolute inset-0 opacity-50 mix-blend-screen" />

        {/* YOLO Bounding Boxes */}
        {data.yolo.detections.map((det, idx) => (
          <div
            key={idx}
            className="absolute border-2 border-warning bg-warning bg-opacity-20"
            style={{
              left: `${det.bbox[0]}%`,
              top: `${det.bbox[1]}%`,
              width: `${det.bbox[2]}%`,
              height: `${det.bbox[3]}%`
            }}
          >
            <div className="absolute -top-6 -left-0.5 bg-warning text-black text-xs font-bold px-1 whitespace-nowrap">
              {det.class} {Math.round(det.confidence * 100)}%
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-bg-secondary p-3 rounded-md border border-border">
          <p className="text-xs text-muted">Detected damage</p>
          <p className="font-bold text-sm">Front-end deformation</p>
        </div>
        <div className="bg-bg-secondary p-3 rounded-md border border-border">
          <p className="text-xs text-muted">Segmented area</p>
          <p className="font-bold text-sm">{data.sam2.segmentedAreaPx.toLocaleString()} px²</p>
        </div>
      </div>
    </Card>
  );
};
