import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Zap, Info, ExternalLink, Box } from 'lucide-react';
import { analysisApi } from '../../services/analysisApi';
import type { DamageAnalysis } from '../../types/analysis';
import { DamageScene } from '../../components/three/DamageScene';
import './MeshViewerPage.css';

export const MeshViewerPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<DamageAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'extendview' | 'threejs'>('extendview');

  useEffect(() => {
    if (id) {
      analysisApi
        .getDamageAnalysis(id)
        .then((data) => {
          setAnalysis(data);
          setLoading(false);
        })
        .catch(() => {
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [id]);

  const getCustomerExtendViewUrl = (embed: boolean = true): string => {
    const baseUrl = (
      import.meta.env?.VITE_CUSTOMER_EXTENDVIEW_URL ||
      import.meta.env?.VITE_EXTENDVIEW_URL ||
      'http://localhost:8501'
    ).replace(/\/$/, '');
    let token = '';
    try {
      const authUserStr = sessionStorage.getItem('auth_user') || localStorage.getItem('auth_user');
      if (authUserStr) {
        const parsed = JSON.parse(authUserStr);
        token = parsed.access_token || parsed.token || parsed.session?.access_token || '';
      }
      if (!token) {
        token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
      }
    } catch {
      // ignore storage parse error
    }
    const params = new URLSearchParams({
      role: 'customer',
      claim_id: String(id || ''),
    });
    if (embed) params.set('embed', 'true');
    if (token) params.set('token', token);
    return `${baseUrl}/?${params.toString()}`;
  };

  return (
    <div className="mesh-viewer-container">
      <header
        className="mesh-viewer-header"
        style={{
          position: 'relative',
          background: 'rgba(14, 14, 20, 0.92)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '0.9rem 1.75rem',
          pointerEvents: 'auto',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <button onClick={() => navigate(-1)} className="mesh-btn-close">
            <ArrowLeft size={16} /> Back to Claim
          </button>
          <div>
            <h1 className="mesh-title" style={{ fontSize: '1.1rem' }}>
              Extended 3D Depth & Surface Inspection
            </h1>
            <p className="mesh-subtitle">
              <span className="mesh-badge">v3 Vision Pipeline</span>
              <span>Claim ID: {id}</span>
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', pointerEvents: 'auto' }}>
          <button
            onClick={() => setViewMode('extendview')}
            className="mesh-btn-close"
            style={{
              background: viewMode === 'extendview' ? 'rgba(5, 150, 105, 0.25)' : 'rgba(255, 255, 255, 0.06)',
              borderColor: viewMode === 'extendview' ? 'rgba(5, 150, 105, 0.6)' : 'rgba(255, 255, 255, 0.15)',
              color: viewMode === 'extendview' ? '#4ADE80' : '#E5E7EB',
              fontWeight: 600,
            }}
          >
            <Zap size={15} /> Full 2D/3D + DSINE Inspection
          </button>
          <button
            onClick={() => setViewMode('threejs')}
            className="mesh-btn-close"
            style={{
              background: viewMode === 'threejs' ? 'rgba(5, 150, 105, 0.25)' : 'rgba(255, 255, 255, 0.06)',
              borderColor: viewMode === 'threejs' ? 'rgba(5, 150, 105, 0.6)' : 'rgba(255, 255, 255, 0.15)',
              color: viewMode === 'threejs' ? '#4ADE80' : '#E5E7EB',
              fontWeight: 600,
            }}
          >
            <Box size={15} /> WebGL Surface Mesh
          </button>
          <a
            href={getCustomerExtendViewUrl(false)}
            target="_blank"
            rel="noopener noreferrer"
            className="mesh-btn-close"
            style={{ textDecoration: 'none' }}
            title="Open in full browser tab"
          >
            <ExternalLink size={15} /> Pop Out ↗
          </a>
        </div>
      </header>

      <div className="mesh-canvas-wrapper" style={{ position: 'relative', flex: 1, overflow: 'hidden' }}>
        {viewMode === 'extendview' ? (
          <iframe
            src={getCustomerExtendViewUrl(true)}
            title="ClaimPilot Customer 3D Extended Inspection"
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              backgroundColor: '#0E0E14',
            }}
            allow="fullscreen"
          />
        ) : loading ? (
          <div
            className="flex items-center justify-center h-full w-full"
            style={{ color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}
          >
            Loading 3D Mesh...
          </div>
        ) : (
          <>
            <DamageScene
              maxDeformationMm={analysis?.damages[0]?.depthMm || 45}
              imageUrl={analysis?.imageUrl}
            />
            <div className="mesh-controls-overlay">
              <div className="mesh-control-item">
                <Zap size={16} color="#ef4444" />
                <span>Detailed mesh deformation map</span>
              </div>
              <div
                className="mesh-control-item"
                style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '1.5rem' }}
              >
                <Info size={16} />
                <span>Drag to rotate, scroll to zoom</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
