import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { claimsApi } from '../../services/claimsApi';
import { analysisApi } from '../../services/analysisApi';
import type { Claim } from '../../types/claim';
import type { DamageAnalysis, DamageArea } from '../../types/analysis';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { DamageViewer } from '../../components/ui/DamageViewer';
import { ArrowLeft, ShieldAlert, Zap, AlertTriangle, CheckCircle } from 'lucide-react';
import { useGSAP, animateFadeIn, animateStagger } from '../../lib/gsap';

export const ClaimAnalysis = () => {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [analysis, setAnalysis] = useState<DamageAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDamage, setSelectedDamage] = useState<DamageArea | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (id) {
      Promise.all([
        claimsApi.getClaimById(id),
        analysisApi.getDamageAnalysis(id)
      ]).then(([claimData, analysisData]) => {
        setClaim(claimData || null);
        setAnalysis(analysisData);
        if (claimData?.images?.length) {
          setSelectedImage(claimData.images[0]);
        } else if (analysisData?.imageUrl) {
          setSelectedImage(analysisData.imageUrl);
        }
        setLoading(false);
      });
    }
  }, [id]);

  useGSAP(() => {
    if (!loading && analysis) {
      animateFadeIn('.analysis-header', { y: 8, duration: 0.35 });
      animateStagger('.damage-card-item', { stagger: 0.05, y: 8, delay: 0.08 });
      animateFadeIn('.cost-estimate-block', { y: 6, delay: 0.15 });
    }
  }, { scope: containerRef, dependencies: [loading, !!analysis] });

  if (loading) return <div className="text-muted p-xl text-center">Loading claim details...</div>;
  if (!claim) return <div className="text-muted p-xl text-center">Claim not found.</div>;

  return (
    <div ref={containerRef} className="flex flex-col gap-lg max-w-5xl mx-auto" style={{ maxWidth: '1200px', marginRight: '0.1rem', paddingBottom: '4rem' }}>
      <div className="analysis-header flex items-center gap-md page-header mb-4">
        <Link to="/customer" className="btn-secondary btn-sm" style={{ padding: '0.5rem' }}>
          <ArrowLeft size={16} />
        </Link>
        <div>
          <div className="flex items-center gap-sm">
            <h2 className="text-2xl m-0">{claim.vehicle}</h2>
            <Badge variant="warning">{claim.status}</Badge>
          </div>
          <p className="text-muted text-sm mt-1">{claim.id} • {claim.claimType} • Submitted {new Date(claim.submittedAt).toLocaleDateString()}</p>
        </div>
      </div>

      <div className="flex gap-xl" style={{ flexWrap: 'wrap' }}>
        {/* Left Column: Analysis Visuals */}
        <div style={{ flex: '5', minWidth: '800px' }} className="flex flex-col gap-md">
          {analysis ? (
            <Card style={{ padding: '0.5rem' }}>
              <div className="p-md mb-2 flex justify-between items-center">
                <h3 className="text-lg font-bold flex items-center gap-sm"><Zap size={18} color="var(--accent-primary)" /> AI Damage Assessment</h3>
              </div>
              <DamageViewer
                analysis={{ ...analysis, imageUrl: selectedImage || analysis.imageUrl }}
                selectedDamageId={selectedDamage?.id}
                onSelectDamage={setSelectedDamage}
              />
              {/* Evidence Gallery Switcher */}
              {claim.images && claim.images.length > 0 && (
                <div className="p-md pt-3 border-t mt-3" style={{ borderColor: 'var(--border)' }}>
                  <p className="text-xs text-muted font-bold uppercase mb-2">Uploaded Photos ({claim.images.length})</p>
                  <div className="flex gap-sm overflow-x-auto">
                    {claim.images.map((img, i) => (
                      <img
                        key={i}
                        src={img}
                        alt={`Evidence ${i + 1}`}
                        onClick={() => setSelectedImage(img)}
                        style={{
                          width: '72px',
                          height: '54px',
                          objectFit: 'cover',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          border: (selectedImage === img || (!selectedImage && i === 0)) ? '2px solid var(--accent)' : '2px solid transparent',
                          opacity: (selectedImage === img || (!selectedImage && i === 0)) ? 1 : 0.5,
                          transition: 'all 0.15s ease-in-out',
                          flexShrink: 0
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
              {/* Video Evidence Section */}
              {claim.videos && claim.videos.length > 0 && (
                <div className="p-md pt-2">
                  <p className="text-xs text-muted font-bold uppercase mb-2">Uploaded Videos ({claim.videos.length})</p>
                  <div className="flex gap-sm overflow-x-auto">
                    {claim.videos.map((vid, i) => (
                      <video
                        key={i}
                        src={vid}
                        controls
                        style={{
                          height: '90px',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border)'
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </Card>
          ) : (
            <Card className="flex flex-col items-center justify-center gap-md text-muted" style={{ minHeight: '400px' }}>
              <ShieldAlert size={48} opacity={0.5} />
              <div className="text-center">
                <p className="font-bold text-lg text-primary">Analyzing your vehicle</p>
                <p className="text-sm">Reviewing uploaded images...</p>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Details */}
        <div style={{ flex: '3', minWidth: '300px' }} className="flex flex-col gap-md">
          <Card>
            <h3 className="text-sm text-muted uppercase font-bold mb-4">AI Assessment</h3>
            {analysis ? (
              <div className="flex flex-col gap-md">
                <p className="text-sm"><strong>{analysis.damages.length}</strong> damaged areas detected.</p>

                <div className="flex flex-col gap-sm">
                  {analysis.damages.map((dmg, idx) => (
                    <div
                      key={dmg.id}
                      onClick={() => setSelectedDamage(dmg)}
                      className="interactive-card damage-card-item p-3"
                      style={{
                        border: `1px solid ${selectedDamage?.id === dmg.id ? 'var(--warning)' : 'var(--border-color)'}`,
                        backgroundColor: selectedDamage?.id === dmg.id ? 'var(--bg-tertiary)' : 'var(--bg-primary)',
                      }}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-bold text-sm">
                          <span style={{ width: '16px', height: '16px', borderRadius: '50%', backgroundColor: 'var(--bg-secondary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', border: '1px solid var(--border-color)', marginRight: '6px' }}>{idx + 1}</span>
                          {dmg.type}
                        </span>
                        <Badge variant={dmg.severity === 'Severe' ? 'danger' : 'warning'}>{dmg.severity}</Badge>
                      </div>
                      <p className="text-xs text-muted ml-6">{dmg.location}</p>
                    </div>
                  ))}
                </div>

                <div className="cost-estimate-block mt-4 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                  <span className="text-muted block text-xs mb-1">
                    {claim.status === 'Approved' ? 'Claim Amount Approved' : 'Estimated Repair Cost'}
                  </span>
                  {claim.status === 'Approved' && claim.approvedAmount ? (
                    <div>
                      <span className="text-2xl font-bold" style={{ color: 'var(--success)' }}>₹{claim.approvedAmount.toLocaleString()}</span>
                      {claim.engineerEstimate ? (
                        <p className="text-xs text-muted mt-1">Engineer Estimate: ₹{claim.engineerEstimate.toLocaleString()}</p>
                      ) : null}
                    </div>
                  ) : (
                    <span className="text-2xl font-bold">₹{analysis.totalEstimatedCost.min.toLocaleString()} – ₹{analysis.totalEstimatedCost.max.toLocaleString()}</span>
                  )}
                  <p className="text-xs text-muted mt-2">
                    {claim.status === 'Approved' ? 'Final approved claim payout.' : '*AI-generated cost estimates are indicative and may vary following assessment and approval by a qualified engineer.'}
                  </p>
                </div>

                {claim.status === 'Approved' && (
                  <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                    <span className="font-bold block text-sm mb-1 flex items-center gap-sm" style={{ color: 'var(--success)' }}><CheckCircle size={14} /> Reason for Approved Amount</span>
                    <p className="text-sm p-3" style={{ backgroundColor: 'rgba(34, 197, 94, 0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--success)', color: 'var(--text-primary)' }}>
                      {claim.approveReason || 'The settlement amount has been approved based on the AI damage assessment and verified repair estimates.'}
                    </p>
                  </div>
                )}

                {claim.status === 'Rejected' && claim.rejectionReason && (
                  <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                    <span className="font-bold block text-sm mb-1 flex items-center gap-sm" style={{ color: 'var(--danger)' }}><ShieldAlert size={14} /> Claim Rejected</span>
                    <p className="text-sm p-3" style={{ backgroundColor: 'rgba(239, 68, 68, 0.05)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--danger)', color: 'var(--text-primary)' }}>
                      {claim.rejectionReason}
                    </p>
                  </div>
                )}

                {claim.requestInfoReason && (
                  <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                    <span className="font-bold block text-sm mb-1 flex items-center gap-sm" style={{ color: 'var(--warning)' }}><AlertTriangle size={14} /> Additional Info Needed by Reviewer</span>
                    <p className="text-sm p-3" style={{ backgroundColor: 'rgba(234, 179, 8, 0.08)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--warning)', color: 'var(--text-primary)' }}>
                      {claim.requestInfoReason}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted text-sm">Assessment not yet complete.</p>
            )}
          </Card>

          <Card>
            <h3 className="text-sm text-muted uppercase font-bold mb-4">Claim Summary</h3>
            <div className="flex flex-col gap-sm text-sm">
              <div className="flex justify-between">
                <span className="text-muted">Incident Date</span>
                <span>{claim.incidentDate}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Location</span>
                <span>{claim.location}</span>
              </div>
              {claim.hsrpNumber && (
                <div className="flex justify-between">
                  <span className="text-muted">HSRP Reg</span>
                  <span className="font-medium">{claim.hsrpNumber}</span>
                </div>
              )}
              {claim.driverLicenseNumber && (
                <div className="flex justify-between">
                  <span className="text-muted">Driver License</span>
                  <span className="font-medium">{claim.driverLicenseNumber}</span>
                </div>
              )}
              <div className="mt-2">
                <span className="text-muted block mb-1">Your Description</span>
                <p className="text-sm p-3" style={{ backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                  "{claim.description}"
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
