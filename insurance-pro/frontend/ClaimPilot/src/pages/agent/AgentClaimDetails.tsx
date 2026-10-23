import { useEffect, useState, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { claimsApi } from '../../services/claimsApi';
import { analysisApi } from '../../services/analysisApi';
import type { Claim } from '../../types/claim';
import type { DamageAnalysis, FraudAnalysis, DamageArea } from '../../types/analysis';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { DamageViewer } from '../../components/ui/DamageViewer';
import { ArrowLeft, User, Phone, CheckCircle, XCircle, AlertTriangle, ShieldCheck, Box, Clock, Layers, Video } from 'lucide-react';
import { advancedAnalysisApi, AdvancedAnalysisData } from '../../services/advancedAnalysisApi';
import { AgentEvidenceViewer } from '../../components/agent/AgentEvidenceViewer';
import { InputComparison } from '../../components/analysis/InputComparison';
import { DamageSegmentation } from '../../components/analysis/DamageSegmentation';
import { DamageDeformation3D } from '../../components/analysis/DamageDeformation3D';
import { SurfaceNormals } from '../../components/analysis/SurfaceNormals';
import { gsap, useGSAP, animateFadeIn, animateStagger } from '../../lib/gsap';

export const AgentClaimDetails = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [damageAnalysis, setDamageAnalysis] = useState<DamageAnalysis | null>(null);
  const [fraudAnalysis, setFraudAnalysis] = useState<FraudAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [damageStatus, setDamageStatus] = useState<'loading' | 'available' | 'failed' | 'unavailable'>('loading');
  const [fraudStatus, setFraudStatus] = useState<'loading' | 'available' | 'failed' | 'unavailable'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mainImage, setMainImage] = useState<string | undefined>();

  const [activeTab, setActiveTab] = useState<'overview' | 'evidence' | 'damage' | '3d-analysis' | 'fraud'>('overview');
  const [analysisViewMode, setAnalysisViewMode] = useState<'embedded' | 'cards'>('embedded');
  const [selectedDamage, setSelectedDamage] = useState<DamageArea | null>(null);
  const [advancedData, setAdvancedData] = useState<AdvancedAnalysisData | null>(null);
  const tabPaneRef = useRef<HTMLDivElement>(null);
  const fraudBarRef = useRef<HTMLDivElement>(null);
  const fraudScoreRef = useRef<HTMLSpanElement>(null);

  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showRequestInfoModal, setShowRequestInfoModal] = useState(false);
  const [engineerEstimate, setEngineerEstimate] = useState<string>('');
  const [approvedAmount, setApprovedAmount] = useState<string>('');
  const [approveReason, setApproveReason] = useState<string>('');
  const [rejectionReason, setRejectionReason] = useState<string>('');
  const [requestInfoReason, setRequestInfoReason] = useState<string>('');

  const isApproveValid = engineerEstimate.trim() !== '' && approvedAmount.trim() !== '' && !isNaN(Number(engineerEstimate)) && !isNaN(Number(approvedAmount)) && Number(engineerEstimate) > 0 && Number(approvedAmount) > 0 && approveReason.trim().length > 0;
  const isRejectValid = rejectionReason.trim().length > 0;
  const isRequestInfoValid = requestInfoReason.trim().length > 0;

  const approveModalRef = useRef<HTMLDivElement>(null);
  const rejectModalRef = useRef<HTMLDivElement>(null);
  const requestInfoModalRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (tabPaneRef.current) {
      animateFadeIn(tabPaneRef.current, { y: 6, duration: 0.22 });
      if (activeTab === 'fraud') {
        animateStagger('.fraud-indicator-item', { stagger: 0.05, y: 8, delay: 0.05 });

        // Animate the score bar fill
        if (fraudBarRef.current && fraudAnalysis && typeof fraudAnalysis.score === 'number') {
          gsap.fromTo(
            fraudBarRef.current,
            { width: '0%' },
            { width: `${Math.min(100, Math.max(0, fraudAnalysis.score))}%`, duration: 0.9, ease: 'power2.out', delay: 0.08 }
          );
        }

        // Animate the score counter
        if (fraudScoreRef.current && fraudAnalysis && typeof fraudAnalysis.score === 'number') {
          const obj = { val: 0 };
          gsap.to(obj, {
            val: fraudAnalysis.score,
            duration: 0.9,
            ease: 'power2.out',
            delay: 0.08,
            onUpdate: () => {
              if (fraudScoreRef.current) {
                fraudScoreRef.current.textContent = Math.round(obj.val).toString();
              }
            },
          });
        }
      }
    }
  }, { scope: tabPaneRef, dependencies: [activeTab, fraudAnalysis] });

  useGSAP(() => {
    if (showApproveModal && approveModalRef.current) {
      gsap.fromTo(approveModalRef.current, { opacity: 0, scale: 0.95, y: 10 }, { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: 'back.out(1.5)' });
    }
  }, { scope: approveModalRef, dependencies: [showApproveModal] });

  useGSAP(() => {
    if (showRejectModal && rejectModalRef.current) {
      gsap.fromTo(rejectModalRef.current, { opacity: 0, scale: 0.95, y: 10 }, { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: 'back.out(1.5)' });
    }
  }, { scope: rejectModalRef, dependencies: [showRejectModal] });

  useGSAP(() => {
    if (showRequestInfoModal && requestInfoModalRef.current) {
      gsap.fromTo(requestInfoModalRef.current, { opacity: 0, scale: 0.95, y: 10 }, { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: 'back.out(1.5)' });
    }
  }, { scope: requestInfoModalRef, dependencies: [showRequestInfoModal] });

  useEffect(() => {
    let isMounted = true;
    if (id) {
      setLoading(true);
      Promise.allSettled([
        claimsApi.getClaimById(id),
        analysisApi.getDamageAnalysis(id),
        analysisApi.getFraudAnalysis(id),
        advancedAnalysisApi.getAnalysis(id)
      ]).then(([claimRes, damageRes, fraudRes, advRes]) => {
        if (!isMounted) return;

        const claimData = claimRes.status === 'fulfilled' ? claimRes.value : null;
        const damageData = damageRes.status === 'fulfilled' ? damageRes.value : null;
        const fraudData = fraudRes.status === 'fulfilled' ? fraudRes.value : null;
        const advData = advRes.status === 'fulfilled' ? advRes.value : null;

        if (claimRes.status === 'rejected' && (claimRes.reason?.status === 401 || claimRes.reason?.statusCode === 401)) {
          navigate('/login', { replace: true });
          return;
        }
        if (claimRes.status === 'rejected') setErrorMessage('Unable to load this claim. Please try again.');
        setClaim(claimData || null);
        if (claimData?.images && claimData.images.length > 0) {
          setMainImage(claimData.images[0]);
        }
        setDamageAnalysis(damageData);
        setFraudAnalysis(fraudData);
        setDamageStatus(damageRes.status === 'fulfilled' ? (damageData ? 'available' : 'unavailable') : 'failed');
        setFraudStatus(fraudRes.status === 'fulfilled' ? (fraudData ? 'available' : 'unavailable') : 'failed');
        setAdvancedData(advData);

        setLoading(false);
      });
    } else {
      setLoading(false);
    }

    return () => {
      isMounted = false;
    };
  }, [id, navigate]);

  const submitAction = async (status: Claim['status'], additionalData?: Partial<Claim>) => {
    if (!claim) return;
    try {
      setSubmitting(true);
      setActionError(null);
      setErrorMessage(null);
      await claimsApi.updateClaimStatus(claim.backendId || claim.id, status, {
        ...additionalData,
        reviewedByAgent: true,
        reviewedAt: new Date().toISOString()
      });
      setShowApproveModal(false);
      setShowRejectModal(false);
      setShowRequestInfoModal(false);
      navigate('/agent/claims');
    } catch (err) {
      console.error('Error updating claim status:', err);
      if ((err as { status?: number }).status === 401 || (err as { statusCode?: number }).statusCode === 401) {
        navigate('/login', { replace: true });
      } else {
        const message = err instanceof Error ? err.message : 'We could not save this decision. Please try again.';
        setActionError(message);
        setErrorMessage(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const isClaimDecided = Boolean(
    claim?.status === 'Approved' ||
    claim?.status === 'Rejected' ||
    claim?.requestInfoReason ||
    claim?.agentAction === 'More Info Requested'
  );

  const imagesList = claim?.images && claim.images.length > 0 ? claim.images : (mainImage ? [mainImage] : []);
  const safeFraudScore = fraudAnalysis && typeof fraudAnalysis.score === 'number' && Number.isFinite(fraudAnalysis.score) ? Math.min(100, Math.max(0, fraudAnalysis.score)) : 0;
  const analysisMessage = (status: typeof damageStatus | typeof fraudStatus) =>
    status === 'loading' ? 'Analyzing... This may take a few moments.' :
      status === 'failed' ? 'Analysis failed, sent for manual review.' :
        status === 'unavailable' ? 'Not yet available.' : '';

  const getAgentExtendViewUrl = (embed: boolean = false): string => {
    const baseUrl = (
      import.meta.env?.VITE_AGENT_EXTENDVIEW_URL ||
      import.meta.env?.VITE_EXTENDVIEW_URL ||
      'http://localhost:8502'
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
    const targetClaimId = (claim as any)?.backendId || id || claim?.id || '';
    const params = new URLSearchParams({ role: 'agent', claim_id: String(targetClaimId) });
    if (embed) params.set('embed', 'true');
    if (token) params.set('token', token);
    return `${baseUrl}/?${params.toString()}`;
  };

  const openExtendedViewInApp = () => {
    setActiveTab('3d-analysis');
    setAnalysisViewMode('embedded');
  };

  const extendedViewBtnStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.35rem',
    borderColor: 'rgba(5, 150, 105, 0.45)',
    color: 'var(--text-primary)',
  } as const;

  if (loading) return <div className="text-muted p-xl text-center">Loading workspace...</div>;
  if (!claim) return <div className="text-muted p-xl text-center">Claim not found.</div>;

  return (
    <div className="flex flex-col gap-lg" style={{ paddingBottom: '4rem' }}>
      {errorMessage && (
        <div role="alert" style={{ padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--danger)', color: 'var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
          {errorMessage}
        </div>
      )}
      {/* Header Panel */}
      <div className="flex justify-between items-start page-header" style={{ marginBottom: 0, paddingBottom: '1.5rem' }}>
        <div className="flex items-start gap-md">
          <Link to="/agent/claims" className="btn-secondary btn-sm mt-1">
            <ArrowLeft size={16} />
          </Link>
          <div>
            <div className="flex items-center gap-sm">
              <h2 className="text-2xl m-0">{claim.id}</h2>
              <Badge variant={claim.status === 'Approved' ? 'success' : claim.status === 'Flagged' || claim.status === 'Rejected' ? 'danger' : 'warning'}>{claim.status}</Badge>
            </div>
            <p className="text-muted text-sm mt-1">{claim.vehicle} • Submitted {claim.submittedAt ? new Date(claim.submittedAt).toLocaleDateString() : 'N/A'}</p>
          </div>
        </div>
        {!isClaimDecided ? (
          <div className="flex gap-sm" style={{ flexWrap: 'wrap' }}>
            <button type="button" onClick={openExtendedViewInApp} className="btn-secondary agent-action-btn" style={extendedViewBtnStyle}>
              <Box size={15} /> Extended View (In-App)
            </button>
            <button className="btn-secondary agent-action-btn" onClick={() => { setActionError(null); setShowRequestInfoModal(true); }}>
              Request Info
            </button>
            <button className="btn-danger agent-action-btn" onClick={() => { setActionError(null); setShowRejectModal(true); }}>
              <XCircle size={16} /> Reject
            </button>
            <button className="btn-success agent-action-btn" onClick={() => { setActionError(null); setShowApproveModal(true); }}>
              <CheckCircle size={16} /> Approve
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
            <button type="button" onClick={openExtendedViewInApp} className="btn-secondary agent-action-btn" style={extendedViewBtnStyle}>
              <Box size={15} /> Extended View (In-App)
            </button>
            {claim.status === 'Approved' && (
              <Badge variant="success" style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <CheckCircle size={16} /> Approved {claim.approvedAmount ? `· ₹${claim.approvedAmount.toLocaleString()}` : ''}
              </Badge>
            )}
            {claim.status === 'Rejected' && (
              <Badge variant="danger" style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <XCircle size={16} /> Claim Rejected
              </Badge>
            )}
            {claim.status !== 'Approved' && claim.status !== 'Rejected' && claim.requestInfoReason && (
              <Badge variant="warning" style={{ padding: '0.5rem 1rem', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <Clock size={16} /> More Info Requested
              </Badge>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-xl">
        {/* Main Workspace */}
        <div style={{ flex: '3', minWidth: '0' }} className="flex flex-col">
          {/* Tabs */}
          <div className="tab-nav">
            <button
              className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              Overview
            </button>
            <button
              className={`tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
              onClick={() => setActiveTab('evidence')}
            >
              <Layers size={14} /> Client Evidence ({(claim.evidence || []).length})
            </button>
            <button
              className={`tab-btn ${activeTab === 'damage' ? 'active' : ''}`}
              onClick={() => setActiveTab('damage')}
            >
              Evidence & Damage
            </button>

            <button
              className={`tab-btn ${activeTab === '3d-analysis' ? 'active' : ''}`}
              onClick={() => setActiveTab('3d-analysis')}
            >
              <Box size={14} /> 3D Advanced Analysis
            </button>

            <button
              className={`tab-btn ${activeTab === 'fraud' ? 'active tab-danger' : ''}`}
              onClick={() => setActiveTab('fraud')}
            >
              <AlertTriangle size={14} /> Fraud Analysis
            </button>
            <a
              href={getAgentExtendViewUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="tab-btn"
              style={{ marginLeft: 'auto', color: 'var(--accent)', fontWeight: 600, textDecoration: 'none' }}
              title="Open Full 2D Heatmaps, DSINE Surface Normals & Telemetry Graphs in Extended View"
            >
              <Box size={14} /> Extended View (DSINE &amp; 3D Graphs) ↗
            </a>
          </div>

          {/* Tab Content */}
          <div ref={tabPaneRef} key={activeTab}>
            {activeTab === 'overview' && (
              <div className="flex flex-col gap-md">
                {isClaimDecided && (
                  <div style={{
                    padding: '1rem 1.25rem',
                    borderRadius: 'var(--radius-md)',
                    border: claim.status === 'Approved' ? '1px solid var(--success)' : claim.status === 'Rejected' ? '1px solid var(--danger)' : '1px solid var(--warning)',
                    backgroundColor: claim.status === 'Approved' ? 'rgba(34, 197, 94, 0.06)' : claim.status === 'Rejected' ? 'rgba(239, 68, 68, 0.06)' : 'rgba(234, 179, 8, 0.08)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.375rem'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, fontSize: '0.875rem', color: claim.status === 'Approved' ? 'var(--success)' : claim.status === 'Rejected' ? 'var(--danger)' : 'var(--warning)' }}>
                      {claim.status === 'Approved' && <><CheckCircle size={16} /> Claim Approved</>}
                      {claim.status === 'Rejected' && <><XCircle size={16} /> Claim Rejected</>}
                      {claim.status !== 'Approved' && claim.status !== 'Rejected' && claim.requestInfoReason && <><Clock size={16} /> Additional Information Requested</>}
                    </div>
                    {claim.status === 'Approved' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                          Approved Payout: <strong>₹{claim.approvedAmount?.toLocaleString() || 'N/A'}</strong>
                          {claim.engineerEstimate ? ` · Engineer Estimate: ₹${claim.engineerEstimate.toLocaleString()}` : ''}
                        </p>
                        {claim.approveReason && (
                          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                            <strong>Reason:</strong> {claim.approveReason}
                          </p>
                        )}
                      </div>
                    )}
                    {claim.status === 'Rejected' && claim.rejectionReason && (
                      <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                        <strong>Rejection Reason:</strong> {claim.rejectionReason}
                      </p>
                    )}
                    {claim.requestInfoReason && (
                      <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                        <strong>Required Information:</strong> {claim.requestInfoReason}
                      </p>
                    )}
                  </div>
                )}
                <div className="flex gap-md" style={{ flexWrap: 'wrap' }}>
                  <Card style={{ flex: 1, minWidth: '250px' }}>
                    <h3 className="text-sm text-muted uppercase font-bold flex items-center gap-sm mb-4"><User size={14} /> Customer & Driver</h3>
                    <div className="flex flex-col gap-sm text-sm">
                      <div>
                        <span className="text-muted block text-xs">Customer Name</span>
                        <span className="font-bold">{claim.customerName || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-muted block text-xs">Policy</span>
                        <span>{claim.policyNumber || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-muted block text-xs">Contact</span>
                        <span className="flex items-center gap-xs"><Phone size={12} /> {claim.customerPhone || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-muted block text-xs">Vehicle</span>
                        <span>{claim.vehicle || 'N/A'}</span>
                        {(claim.engineNumber || claim.chassisNumber) && (
                          <div style={{ marginTop: '0.25rem', display: 'flex', gap: '0.75rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            {claim.engineNumber && <span>ENG: {claim.engineNumber}</span>}
                            {claim.chassisNumber && <span>VIN: {claim.chassisNumber}</span>}
                          </div>
                        )}
                      </div>
                      <div className="mt-2 pt-2 border-t" style={{ borderColor: 'var(--border-color)' }}>
                        <span className="text-muted block text-xs mb-1">Driver Details</span>
                        {claim.driverName ? (
                          <>
                            <div className="flex justify-between items-center text-xs">
                              <span className="font-bold">{claim.driverName}</span>
                              <span className="font-mono text-muted">{claim.driverLicenseNumber || ''}</span>
                            </div>
                            <div className="flex gap-xs mt-2">
                              {claim.driverLicenseFrontPhoto && (
                                <img src={claim.driverLicenseFrontPhoto} alt="Front" style={{ width: '40px', height: '26px', objectFit: 'cover', borderRadius: '4px', border: '1px solid var(--border-color)', cursor: 'pointer' }} onClick={() => window.open(claim.driverLicenseFrontPhoto, '_blank')} title="View Front" />
                              )}
                              {claim.driverLicenseBackPhoto && (
                                <img src={claim.driverLicenseBackPhoto} alt="Back" style={{ width: '40px', height: '26px', objectFit: 'cover', borderRadius: '4px', border: '1px solid var(--border-color)', cursor: 'pointer' }} onClick={() => window.open(claim.driverLicenseBackPhoto, '_blank')} title="View Back" />
                              )}
                            </div>
                          </>
                        ) : (
                          <span className="text-xs text-muted italic">No driver info provided</span>
                        )}
                      </div>
                    </div>
                  </Card>

                  <Card style={{ flex: 1, minWidth: '250px' }}>
                    <h3 className="text-sm text-muted uppercase font-bold mb-4">Incident</h3>
                    <div className="flex flex-col gap-sm text-sm">
                      <div>
                        <span className="text-muted block text-xs">Date</span>
                        <span>{claim.incidentDate || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-muted block text-xs">Location</span>
                        <span>{claim.location || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-muted block text-xs">Type</span>
                        <span>{claim.claimType || 'N/A'}</span>
                      </div>
                      <div className="mt-2">
                        <span className="text-muted block text-xs mb-1">Customer Description</span>
                        <p style={{ backgroundColor: 'var(--bg-primary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                          {claim.description || 'No description provided.'}
                        </p>
                      </div>
                    </div>
                  </Card>

                  <Card style={{ flex: 1, minWidth: '250px' }}>
                    <h3 className="text-sm text-muted uppercase font-bold flex items-center gap-sm mb-4"><ShieldCheck size={14} /> AI Summary</h3>
                    {damageAnalysis && damageStatus === 'available' ? (
                      <div className="flex flex-col gap-sm text-sm">
                        <div>
                          <span className="text-muted block text-xs">Damage Areas</span>
                          <span className="font-bold">{(damageAnalysis.damages || []).length} detected</span>
                        </div>
                        <div>
                          <span className="text-muted block text-xs">Highest Severity</span>
                          <Badge variant={(damageAnalysis.damages || []).some(d => d.severity === 'Severe') ? 'danger' : 'warning'}>
                            {(damageAnalysis.damages || []).some(d => d.severity === 'Severe') ? 'Severe' : 'Moderate'}
                          </Badge>
                        </div>
                        <div className="mt-2 p-3" style={{ backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)' }}>
                          <span className="text-muted block text-xs mb-1">Estimated Repair Cost</span>
                          <span className="text-xl font-bold">
                            ₹{damageAnalysis.totalEstimatedCost?.min?.toLocaleString() ?? 0} – ₹{damageAnalysis.totalEstimatedCost?.max?.toLocaleString() ?? 0}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-md h-full justify-center">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 2s infinite' }} />
                          <span className="font-bold" style={{ color: 'var(--text-secondary)' }}>{analysisMessage(damageStatus)}</span>
                        </div>
                        <div style={{ height: '24px', width: '100%', backgroundColor: 'var(--bg-hover)', borderRadius: '4px', border: '1px solid var(--border)' }} />
                        <div style={{ height: '24px', width: '70%', backgroundColor: 'var(--bg-hover)', borderRadius: '4px', border: '1px solid var(--border)' }} />
                      </div>
                    )}
                  </Card>
                </div>

                {/* Client Uploaded Evidence Summary Card */}
                <Card style={{ marginTop: '0.5rem', border: '1px solid var(--border)' }}>
                  <div className="flex justify-between items-center mb-3">
                    <div className="flex items-center gap-sm">
                      <h3 className="text-sm text-muted uppercase font-bold m-0 flex items-center gap-xs">
                        <Layers size={14} /> Uploaded Client Evidence
                      </h3>
                      <Badge variant="neutral">{(claim.evidence || []).length} items</Badge>
                    </div>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
                      onClick={() => setActiveTab('evidence')}
                    >
                      Open Full Evidence Gallery &rarr;
                    </button>
                  </div>

                  {(claim.evidence && claim.evidence.length > 0) ? (
                    <div className="flex gap-sm overflow-x-auto pb-2">
                      {claim.evidence.map((item, idx) => {
                        const isVid = (item.category || '').includes('video');
                        return (
                          <div
                            key={item.id || idx}
                            onClick={() => setActiveTab('evidence')}
                            style={{
                              flexShrink: 0,
                              width: '110px',
                              cursor: 'pointer',
                              borderRadius: 'var(--radius-sm)',
                              overflow: 'hidden',
                              border: '1px solid var(--border)',
                              backgroundColor: 'var(--bg-primary)',
                              transition: 'transform 0.15s ease',
                            }}
                            title={`Click to inspect ${item.category || 'evidence'}`}
                          >
                            <div style={{ height: '70px', position: 'relative', backgroundColor: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              {isVid ? (
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
                                  <Video size={20} color="var(--accent)" />
                                  <span style={{ fontSize: '0.625rem', color: '#fff' }}>Video</span>
                                </div>
                              ) : (
                                <img src={item.file_url} alt="Evidence" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                              )}
                            </div>
                            <div style={{ padding: '0.375rem 0.5rem', fontSize: '0.6875rem', color: 'var(--text-secondary)', textTransform: 'capitalize', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {(item.category || 'Photo').replace(/_/g, ' ')}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-muted m-0 italic">No evidence uploaded for this claim yet.</p>
                  )}
                </Card>
              </div>
            )}

            {activeTab === 'evidence' && (
              <AgentEvidenceViewer
                evidence={claim.evidence || []}
                claimId={claim.id}
                claimVehicle={claim.vehicle}
                customerName={claim.customerName}
                onOpenDamageAnalysis={() => setActiveTab('damage')}
              />
            )}

            {activeTab === 'damage' && (
              <div className="flex flex-col gap-md">
                <div style={{
                  padding: '0.625rem 1rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-secondary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.8125rem'
                }}>
                  <span className="text-muted" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    <Layers size={14} color="var(--accent)" />
                    Viewing AI damage segmentation. Client submitted <strong>{(claim.evidence || []).length} total evidence files</strong> (including walkaround videos and ID).
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
                    onClick={() => setActiveTab('evidence')}
                  >
                    View All Client Evidence &rarr;
                  </button>
                </div>

                <div className="flex gap-lg">
                <div style={{ flex: 2 }}>
                  <Card style={{ padding: '0.5rem' }}>
                    {damageAnalysis && damageStatus === 'available' ? (
                      <DamageViewer
                        analysis={{ ...damageAnalysis, imageUrl: mainImage || damageAnalysis.imageUrl || '' }}
                        selectedDamageId={selectedDamage?.id}
                        onSelectDamage={setSelectedDamage}
                      />
                    ) : (
                      <div style={{ position: 'relative', width: '100%', borderRadius: 'var(--radius-sm)', overflow: 'hidden', backgroundColor: 'var(--bg-hover)' }}>
                        <img src={mainImage || ''} alt="Evidence" style={{ width: '100%', opacity: 0.5, filter: 'grayscale(50%) blur(2px)' }} />
                        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
                          <span style={{ display: 'inline-block', width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 2s infinite', marginBottom: '0.75rem' }} />
                          <p style={{ fontWeight: 600, color: 'var(--text-primary)', textShadow: '0 2px 4px rgba(0,0,0,0.8)' }}>{analysisMessage(damageStatus)}</p>
                          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', textShadow: '0 1px 2px rgba(0,0,0,0.8)' }}>{damageStatus === 'loading' ? 'Detecting damage boundaries...' : 'An agent can review the evidence manually.'}</p>
                        </div>
                      </div>
                    )}
                  </Card>

                  {/* Thumbnail Gallery */}
                  <div className="flex gap-sm mt-4">
                    {imagesList.map((img, i) => (
                      <img
                        key={i}
                        src={img}
                        alt="thumbnail"
                        onClick={() => setMainImage(img)}
                        style={{
                          width: '80px', height: '60px', objectFit: 'cover',
                          borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                          border: mainImage === img ? '2px solid var(--accent-primary)' : '2px solid transparent',
                          opacity: mainImage === img ? 1 : 0.6,
                          transition: 'all 0.2s'
                        }}
                      />
                    ))}
                  </div>
                </div>

                <div style={{ flex: 1 }} className="flex flex-col gap-md">
                  <Card>
                    <h3 className="text-sm text-muted uppercase font-bold mb-4">Estimated Repair Cost</h3>
                    {damageAnalysis && damageStatus === 'available' ? (
                      <div>
                        <div className="text-2xl font-bold mb-1">
                          ₹{damageAnalysis.totalEstimatedCost?.min?.toLocaleString() ?? 0} – ₹{damageAnalysis.totalEstimatedCost?.max?.toLocaleString() ?? 0}
                        </div>
                        <p className="text-xs text-muted mb-4">Based on detected damage. Not a guaranteed payout.</p>

                        <div className="flex flex-col gap-xs text-sm">
                          {(damageAnalysis.damages || []).map(dmg => (
                            <div key={dmg.id} className="flex justify-between items-center py-2 border-b" style={{ borderColor: 'var(--border-color)' }}>
                              <span>{dmg.type}</span>
                              <span className="text-muted">
                                ₹{dmg.estimatedRepairCost?.min?.toLocaleString() ?? 0} – ₹{dmg.estimatedRepairCost?.max?.toLocaleString() ?? 0}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-sm">
                        <p className="text-muted text-sm italic">Waiting for damage segmentation to complete before estimating parts and labor...</p>
                        <div style={{ height: '32px', width: '60%', backgroundColor: 'var(--bg-hover)', borderRadius: '4px', border: '1px solid var(--border)' }} />
                      </div>
                    )}
                  </Card>

                  <Card style={{ flex: 1, overflowY: 'auto', maxHeight: '400px' }}>
                    <h3 className="text-sm text-muted uppercase font-bold mb-4">Detected Damage</h3>
                    {damageAnalysis && damageStatus === 'available' ? (
                      <div className="flex flex-col gap-sm">
                        {(damageAnalysis.damages || []).map((dmg, idx) => (
                          <div
                            key={dmg.id}
                            onClick={() => setSelectedDamage(dmg)}
                            className="interactive-card text-sm p-3"
                            style={{
                              border: `1px solid ${selectedDamage?.id === dmg.id ? 'var(--warning)' : 'var(--border-color)'}`,
                              backgroundColor: selectedDamage?.id === dmg.id ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
                            }}
                          >
                            <div className="flex justify-between items-center mb-1">
                              <span className="font-bold flex items-center gap-xs">
                                <span style={{ width: '16px', height: '16px', borderRadius: '50%', backgroundColor: 'var(--bg-primary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', border: '1px solid var(--border-color)' }}>{idx + 1}</span>
                                {dmg.type}
                              </span>
                              <Badge variant={dmg.severity === 'Severe' ? 'danger' : 'warning'}>{dmg.severity}</Badge>
                            </div>
                            <p className="text-muted text-xs ml-5">{dmg.location}</p>
                            <p className="text-muted text-xs ml-5 mt-1 font-bold">{dmg.confidence}% conf</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-col gap-sm">
                        <div style={{ height: '70px', width: '100%', backgroundColor: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }} />
                        <div style={{ height: '70px', width: '100%', backgroundColor: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }} />
                      </div>
                    )}
                  </Card>
                </div>
              </div>
              </div>
            )}

            {activeTab === '3d-analysis' && (
              <div className="flex flex-col gap-lg">
                <div className="flex justify-between items-center bg-bg-secondary p-4 rounded-md border border-border" style={{ gap: '1rem', flexWrap: 'wrap' }}>
                  <div>
                    <div className="flex items-center gap-sm mb-1">
                      <h2 className="text-xl font-bold m-0">Advanced 3D Damage &amp; DSINE Telemetry</h2>
                      <Badge variant="success">v3 Vision Pipeline</Badge>
                    </div>
                    <p className="text-sm text-muted m-0">
                      Deep learning outputs (YOLOv11m + Depth Anything V2 + SAM2 + DSINE) with 2D ΔZ heatmaps, interactive 3D mesh, CLAHE histograms, and per-instance telemetry.
                    </p>
                  </div>
                  <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={() => setAnalysisViewMode('embedded')}
                      className={analysisViewMode === 'embedded' ? 'btn-success agent-action-btn' : 'btn-secondary agent-action-btn'}
                      style={{ padding: '0.45rem 0.95rem' }}
                    >
                      Interactive Extended Workbench (Embedded)
                    </button>
                    <button
                      type="button"
                      onClick={() => setAnalysisViewMode('cards')}
                      className={analysisViewMode === 'cards' ? 'btn-success agent-action-btn' : 'btn-secondary agent-action-btn'}
                      style={{ padding: '0.45rem 0.95rem' }}
                    >
                      Summary Cards
                    </button>
                    <a
                      href={getAgentExtendViewUrl(false)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-secondary agent-action-btn"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', textDecoration: 'none', padding: '0.45rem 0.95rem' }}
                    >
                      <Box size={15} /> Open Full Tab ↗
                    </a>
                  </div>
                </div>

                {analysisViewMode === 'embedded' ? (
                  <div
                    style={{
                      width: '100%',
                      height: '860px',
                      borderRadius: 'var(--radius-md)',
                      overflow: 'hidden',
                      border: '1px solid var(--border-color)',
                      backgroundColor: '#0E0E14',
                    }}
                  >
                    <iframe
                      src={getAgentExtendViewUrl(true)}
                      title="ClaimPilot Adjuster 3D & DSINE Extended Workbench"
                      style={{ width: '100%', height: '100%', border: 'none', backgroundColor: '#0E0E14' }}
                      allow="fullscreen"
                    />
                  </div>
                ) : advancedData ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem', minHeight: '600px' }}>
                    <div className="flex flex-col gap-lg h-full">
                      <div className="flex-1 min-h-[300px]">
                        <InputComparison data={advancedData} />
                      </div>
                      <div className="flex-1 min-h-[400px]">
                        <DamageDeformation3D data={advancedData} />
                      </div>
                    </div>
                    <div className="flex flex-col gap-lg h-full">
                      <div className="flex-1 min-h-[300px]">
                        <DamageSegmentation data={advancedData} />
                      </div>
                      <div className="flex-1 min-h-[300px]">
                        <SurfaceNormals data={advancedData} />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-muted">
                    <span style={{ display: 'inline-block', width: '24px', height: '24px', borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 1.5s infinite', marginBottom: '1rem' }} />
                    <p>Loading deep learning analysis...</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'fraud' && (
              <div className="flex gap-lg">
                <div style={{ flex: 2 }} className="flex flex-col gap-md">
                  <Card>
                    <h3 className="text-sm text-muted uppercase font-bold mb-6">AI Fraud Assessment</h3>
                    {fraudAnalysis && fraudStatus === 'available' ? (
                      <div>
                        {/* Fraud Risk Bar */}
                        <div className="flex flex-col mb-8">
                          <div className="flex justify-between items-end mb-3">
                            <span className="text-3xl font-bold">
                              <span ref={fraudScoreRef}>{safeFraudScore}</span>
                              <span className="text-lg text-muted font-normal"> / 100</span>
                            </span>
                            <span className="font-bold" style={{ color: fraudAnalysis.riskLevel === 'HIGH RISK' ? 'var(--danger)' : fraudAnalysis.riskLevel === 'MEDIUM RISK' ? 'var(--warning)' : 'var(--success)' }}>
                              {fraudAnalysis.riskLevel === 'HIGH RISK' || fraudAnalysis.riskLevel === 'MEDIUM RISK' || fraudAnalysis.riskLevel === 'LOW RISK' ? fraudAnalysis.riskLevel : 'LOW RISK'}
                            </span>
                          </div>

                          {/* Track */}
                          <div style={{ position: 'relative', width: '100%', height: '10px', borderRadius: '5px', backgroundColor: 'var(--bg-primary)', overflow: 'hidden' }}>
                            {/* Zone markers inside track */}
                            <div style={{ position: 'absolute', left: '33%', top: 0, bottom: 0, width: '2px', backgroundColor: 'var(--bg-secondary)', zIndex: 1 }} />
                            <div style={{ position: 'absolute', left: '66%', top: 0, bottom: 0, width: '2px', backgroundColor: 'var(--bg-secondary)', zIndex: 1 }} />
                            {/* Animated fill */}
                            <div
                              ref={fraudBarRef}
                              style={{
                                position: 'absolute',
                                left: 0,
                                top: 0,
                                bottom: 0,
                                width: `${safeFraudScore}%`,
                                borderRadius: '5px',
                                backgroundColor:
                                  safeFraudScore > 66
                                    ? 'var(--danger)'
                                    : safeFraudScore > 33
                                      ? 'var(--warning)'
                                      : 'var(--success)',
                              }}
                            />
                          </div>

                          <div className="flex justify-between text-xs text-muted mt-2">
                            <span>Low (0–33)</span>
                            <span>Medium (34–66)</span>
                            <span>High (67–100)</span>
                          </div>
                        </div>

                        <h4 className="text-sm font-bold mb-4">Risk Indicators</h4>
                        <div className="flex flex-col gap-sm">
                          {(fraudAnalysis.indicators || []).map((indicator, idx) => (
                            <div key={idx} className="fraud-indicator-item flex items-start gap-md p-3" style={{ backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', minWidth: 0 }}>
                              {indicator.passed ? (
                                <CheckCircle size={18} color="var(--success)" />
                              ) : (
                                <AlertTriangle size={18} color="var(--danger)" />
                              )}
                              <div style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
                                <p className="font-bold text-sm" style={{ color: indicator.passed ? 'var(--success)' : 'var(--danger)' }}>
                                  {indicator.passed ? 'Verified' : 'Suspicious Flag'}
                                </p>
                                <p className="text-xs text-muted mt-1">{indicator.message || 'No details provided.'}</p>
                                {(indicator.message || '').toLowerCase().includes('skip') && (
                                  <p className="text-xs text-muted mt-1">This check was skipped and should be reviewed manually.</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-md">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 2s infinite' }} />
                          <span className="font-bold" style={{ color: 'var(--text-secondary)' }}>{analysisMessage(fraudStatus)}</span>
                        </div>
                        <div style={{ height: '32px', width: '40%', backgroundColor: 'var(--bg-hover)', borderRadius: '4px', border: '1px solid var(--border)' }} />
                        <div style={{ height: '8px', width: '100%', backgroundColor: 'var(--bg-hover)', borderRadius: '4px', border: '1px solid var(--border)' }} />
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '1rem' }}>
                          <div style={{ height: '60px', width: '100%', backgroundColor: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }} />
                          <div style={{ height: '60px', width: '100%', backgroundColor: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }} />
                        </div>
                      </div>
                    )}
                  </Card>
                </div>

                <div style={{ flex: 1 }}>
                  <div className="p-md" style={{ backgroundColor: 'rgba(239, 68, 68, 0.05)', border: '1px solid var(--danger-bg)', borderRadius: 'var(--radius-md)' }}>
                    <p className="font-bold flex items-center gap-sm text-sm" style={{ color: 'var(--danger)', marginBottom: '0.5rem' }}>
                      <AlertTriangle size={16} /> Internal Use Only
                    </p>
                    <p className="text-muted text-xs">
                      The fraud score and indicators are for internal review only.
                      Under no circumstances should this data be disclosed to the customer or rendered in the customer portal.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      {showApproveModal && (
        <div className="agent-action-overlay">
          <div ref={approveModalRef} className="agent-action-modal">
            <h3 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '1rem' }}>Approve Claim</h3>
            {actionError && (
              <div role="alert" style={{ padding: '0.625rem 0.875rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--danger)', color: 'var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.1)', fontSize: '0.8125rem', marginBottom: '1rem' }}>
                {actionError}
              </div>
            )}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                Estimated Cost of Repair/Replacement by Engineer (₹)
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="off"
                value={engineerEstimate}
                onChange={e => {
                  const v = e.target.value.replace(/\D/g, '');
                  setEngineerEstimate(v);
                }}
                className="form-input"
                style={{ width: '100%', padding: '0.625rem', borderRadius: 'var(--radius-sm)' }}
                placeholder="Enter engineer estimated cost..."
              />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                Claim Amount Approved (₹)
              </label>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                autoComplete="off"
                value={approvedAmount}
                onChange={e => {
                  const v = e.target.value.replace(/\D/g, '');
                  setApprovedAmount(v);
                }}
                className="form-input"
                style={{ width: '100%', padding: '0.625rem', borderRadius: 'var(--radius-sm)' }}
                placeholder="Enter approved payout amount..."
              />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                Reason for the approved claim amount
              </label>
              <textarea
                value={approveReason}
                onChange={e => setApproveReason(e.target.value)}
                className="form-input"
                style={{ width: '100%', padding: '0.625rem', minHeight: '80px', resize: 'vertical', borderRadius: 'var(--radius-sm)' }}
                placeholder="Explain the rationale for this settlement amount..."
              />
            </div>
            <div className="flex gap-sm justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => { setActionError(null); setShowApproveModal(false); }}
                style={{ padding: '0.5rem 1rem', borderRadius: 'var(--radius-sm)' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-success"
                disabled={!isApproveValid || submitting}
                onClick={() => {
                  if (isApproveValid && !submitting) {
                    submitAction('Approved', { engineerEstimate: Number(engineerEstimate), approvedAmount: Number(approvedAmount), approveReason: approveReason.trim(), agentAction: 'Approved' });
                  }
                }}
                style={{
                  padding: '0.5rem 1.25rem',
                  borderRadius: 'var(--radius-sm)',
                  opacity: isApproveValid && !submitting ? 1 : 0.4,
                  cursor: isApproveValid && !submitting ? 'pointer' : 'not-allowed',
                  pointerEvents: isApproveValid && !submitting ? 'auto' : 'none',
                  filter: isApproveValid && !submitting ? 'none' : 'grayscale(40%)',
                  transition: 'all 0.2s ease'
                }}
              >
                {submitting ? 'Approving...' : 'Confirm Approve'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showRejectModal && (
        <div className="agent-action-overlay">
          <div ref={rejectModalRef} className="agent-action-modal">
            <h3 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '0.75rem', color: 'var(--danger)' }}>Reject Claim</h3>
            {actionError && (
              <div role="alert" style={{ padding: '0.625rem 0.875rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--danger)', color: 'var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.1)', fontSize: '0.8125rem', marginBottom: '1rem' }}>
                {actionError}
              </div>
            )}
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Please provide the reason for rejection. This reason will be shown directly to the customer on their portal.
            </p>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                Reason for Rejection
              </label>
              <textarea
                value={rejectionReason}
                onChange={e => setRejectionReason(e.target.value)}
                className="form-input"
                style={{ width: '100%', padding: '0.625rem', minHeight: '110px', resize: 'vertical', borderRadius: 'var(--radius-sm)' }}
                placeholder="Provide clear reasons why this claim was rejected..."
              />
            </div>
            <div className="flex gap-sm justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => { setActionError(null); setShowRejectModal(false); }}
                style={{ padding: '0.5rem 1rem', borderRadius: 'var(--radius-sm)' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger"
                disabled={!isRejectValid || submitting}
                onClick={() => {
                  if (isRejectValid && !submitting) {
                    submitAction('Rejected', { rejectionReason: rejectionReason.trim(), agentAction: 'Rejected' });
                  }
                }}
                style={{
                  padding: '0.5rem 1.25rem',
                  borderRadius: 'var(--radius-sm)',
                  opacity: isRejectValid && !submitting ? 1 : 0.4,
                  cursor: isRejectValid && !submitting ? 'pointer' : 'not-allowed',
                  pointerEvents: isRejectValid && !submitting ? 'auto' : 'none',
                  filter: isRejectValid && !submitting ? 'none' : 'grayscale(40%)',
                  transition: 'all 0.2s ease'
                }}
              >
                {submitting ? 'Rejecting...' : 'Confirm Reject'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showRequestInfoModal && (
        <div className="agent-action-overlay">
          <div ref={requestInfoModalRef} className="agent-action-modal">
            <h3 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '0.5rem', color: 'var(--warning)' }}>Request More Information</h3>
            {actionError && (
              <div role="alert" style={{ padding: '0.625rem 0.875rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--danger)', color: 'var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.1)', fontSize: '0.8125rem', marginBottom: '1rem' }}>
                {actionError}
              </div>
            )}
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Enter what more information is needed for the claim to process. This message will be displayed to the customer on their portal.
            </p>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>
                Information Needed from Customer
              </label>
              <textarea
                value={requestInfoReason}
                onChange={e => setRequestInfoReason(e.target.value)}
                className="form-input"
                style={{ width: '100%', padding: '0.625rem', minHeight: '110px', resize: 'vertical', borderRadius: 'var(--radius-sm)' }}
                placeholder="Specify what additional documents, photos, or explanations are needed to process this claim..."
              />
            </div>
            <div className="flex gap-sm justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => { setActionError(null); setShowRequestInfoModal(false); }}
                style={{ padding: '0.5rem 1rem', borderRadius: 'var(--radius-sm)' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={!isRequestInfoValid || submitting}
                onClick={() => {
                  if (isRequestInfoValid && !submitting) {
                    submitAction('Under Review', { requestInfoReason: requestInfoReason.trim(), agentAction: 'More Info Requested' });
                  }
                }}
                style={{
                  padding: '0.5rem 1.25rem',
                  borderRadius: 'var(--radius-sm)',
                  opacity: isRequestInfoValid && !submitting ? 1 : 0.4,
                  cursor: isRequestInfoValid && !submitting ? 'pointer' : 'not-allowed',
                  pointerEvents: isRequestInfoValid && !submitting ? 'auto' : 'none',
                  filter: isRequestInfoValid && !submitting ? 'none' : 'grayscale(40%)',
                  transition: 'all 0.2s ease'
                }}
              >
                {submitting ? 'Sending...' : 'Send Request'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};