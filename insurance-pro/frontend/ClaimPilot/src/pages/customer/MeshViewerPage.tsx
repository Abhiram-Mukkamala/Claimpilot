import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Zap, Info } from 'lucide-react';
import { analysisApi } from '../../services/analysisApi';
import type { DamageAnalysis } from '../../types/analysis';
import { DamageScene } from '../../components/three/DamageScene';
import './MeshViewerPage.css';

export const MeshViewerPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<DamageAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      analysisApi.getDamageAnalysis(id).then((data) => {
        setAnalysis(data);
        setLoading(false);
      });
    }
  }, [id]);

  return (
    <div className="mesh-viewer-container">
      <header className="mesh-viewer-header">
        <button onClick={() => navigate(-1)} className="mesh-btn-close">
          <ArrowLeft size={16} /> Back to Claim
        </button>
        <div className="mesh-info text-right" style={{ textAlign: 'right' }}>
          <h1 className="mesh-title">3D Damage Assessment</h1>
          <p className="mesh-subtitle" style={{ justifyContent: 'flex-end' }}>
            <span className="mesh-badge">AI Verified</span>
            Claim ID: {id}
          </p>
        </div>
      </header>

      <div className="mesh-canvas-wrapper" style={{ position: 'relative' }}>
        {loading ? (
          <div className="flex items-center justify-center h-full w-full" style={{ color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            Loading 3D Mesh...
          </div>
        ) : (
          <DamageScene 
            maxDeformationMm={analysis?.damages[0]?.depthMm || 45} 
            imageUrl={analysis?.imageUrl} 
          />
        )}
      </div>

      <div className="mesh-controls-overlay">
        <div className="mesh-control-item">
          <Zap size={16} color="#ef4444" />
          <span>Detailed mesh deformation map</span>
        </div>
        <div className="mesh-control-item" style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '1.5rem' }}>
          <Info size={16} />
          <span>Drag to rotate, scroll to zoom</span>
        </div>
      </div>
    </div>
  );
};
