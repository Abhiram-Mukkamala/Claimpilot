import React, { useEffect, useRef } from 'react';
import { Card } from '../ui/Card';
import { AdvancedAnalysisData } from '../../services/advancedAnalysisApi';

export const SurfaceNormals: React.FC<{ data: AdvancedAnalysisData }> = ({ data }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Draw a vector field overlay
    // For a real app, you would sample the normal map image. 
    // Here we generate a mock vector field pointing outwards from the center of damage.
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const step = 20; // downsample: render vector every 20px
    const cx = width * 0.72; // approx center of damage based on mock bbox
    const cy = height * 0.4;

    for (let y = 0; y < height; y += step) {
      for (let x = 0; x < width; x += step) {
        // Only draw vectors inside an approximate damage radius
        const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
        if (dist < 100) {
          const angle = Math.atan2(y - cy, x - cx) + (Math.random() * 0.5 - 0.25);
          const length = 10;

          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + Math.cos(angle) * length, y + Math.sin(angle) * length);
          ctx.strokeStyle = '#00ffcc';
          ctx.lineWidth = 1.5;
          ctx.stroke();

          // Arrow head
          ctx.beginPath();
          ctx.arc(x + Math.cos(angle) * length, y + Math.sin(angle) * length, 1.5, 0, Math.PI * 2);
          ctx.fillStyle = '#00ffcc';
          ctx.fill();
        }
      }
    }
  }, [data]);

  return (
    <Card className="h-full flex flex-col">
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        DSINE — Surface Normal Vectors
      </h3>
      <div className="relative w-full rounded-md overflow-hidden border border-border bg-bg-secondary flex-1">
        <img src={data.dsine.normalMap} alt="Normal Map" className="w-full h-full object-cover absolute inset-0" />
        <canvas
          ref={canvasRef}
          width={400}
          height={300}
          className="w-full h-full absolute inset-0 pointer-events-none opacity-80"
          style={{ mixBlendMode: 'screen' }}
        />
        <div className="absolute bottom-2 left-2 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded">
          Surface orientation estimated from DSINE
        </div>
      </div>
    </Card>
  );
};
