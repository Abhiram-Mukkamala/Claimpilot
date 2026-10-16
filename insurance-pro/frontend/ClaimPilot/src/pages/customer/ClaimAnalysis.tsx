import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { claimsApi, toSettlementDecisionError } from '../../services/claimsApi';
import type { SettlementDecisionStatus } from '../../services/claimsApi';
import { analysisApi } from '../../services/analysisApi';
import type { Claim } from '../../types/claim';
import type { DamageAnalysis, DamageArea } from '../../types/analysis';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { DamageViewer } from '../../components/ui/DamageViewer';
import { ArrowLeft, ShieldAlert, Zap, AlertTriangle, CheckCircle, Box } from 'lucide-react';
import { useGSAP, animateFadeIn, animateStagger } from '../../lib/gsap';

export const ClaimAnalysis = () => {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [analysis, setAnalysis] = useState<DamageAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDamage, setSelectedDamage] = useState<DamageArea | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  // Settlement Decision State
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decisionSuccessMessage, setDecisionSuccessMessage] = useState<string | null>(null);
  const [showDisputeModal, setShowDisputeModal] = useState(false);
  const [disputeNotes, setDisputeNotes] = useState('');
  const [disputeModalError, setDisputeModalError] = useState<string | null>(null);
  // Set when the backend reports the claim could not be updated in its current state (409/404):
  // the user must reload the authoritative claim status before retrying.
  const [decisionNeedsRefresh, setDecisionNeedsRefresh] = useState(false);
  const [refreshingClaim, setRefreshingClaim] = useState(false);
  const decisionInFlightRef = useRef(false);

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (id) {
      Promise.all([
        claimsApi.getClaimById(id),
        analysisApi.getDamageAnalysis(id).catch(() => null)
      ]).then(([claimData, analysisData]) => {
        setClaim(claimData || null);
        setAnalysis(analysisData);
        if (claimData?.images?.length) {
          setSelectedImage(claimData.images[0]);
        } else if (analysisData?.imageUrl) {
          setSelectedImage(analysisData.imageUrl);
        }
        setLoading(false);
      }).catch(err => {
        console.error('Error fetching claim:', err);
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

  const applyConfirmedDecision = (newStatus: SettlementDecisionStatus, extra: Partial<Claim> = {}) => {
    setClaim(prev => prev ? {
      ...prev,
      ...extra,
      status: newStatus === 'settlement_accepted' ? 'Settlement Accepted' : 'Disputed',
      rawStatus: newStatus,
    } : null);
  };

  const handleAcceptSettlement = async () => {
    if (!claim || decisionInFlightRef.current) return;
    decisionInFlightRef.current = true;
    setSubmittingDecision(true);
    setDecisionError(null);
    setDecisionNeedsRefresh(false);
    setDecisionSuccessMessage(null);
    try {
      const claimTargetId = claim.backendId || claim.id;
      // Resolves only when the backend confirms new_status === 'settlement_accepted'.
      const result = await claimsApi.submitSettlementDecision(claimTargetId, 'ACCEPT');
      applyConfirmedDecision(result.newStatus);
      setDecisionSuccessMessage(result.message);
    } catch (err: unknown) {
      const decisionErr = toSettlementDecisionError(err);
      setDecisionError(decisionErr.message);
      setDecisionNeedsRefresh(decisionErr.requiresRefresh);
    } finally {
      decisionInFlightRef.current = false;
      setSubmittingDecision(false);
    }
  };

  const handleSubmitDispute = async () => {
    if (!claim || decisionInFlightRef.current) return;
    if (!disputeNotes.trim()) {
      setDisputeModalError('Please provide a reason or notes for your dispute.');
      return;
    }
    decisionInFlightRef.current = true;
    setSubmittingDecision(true);
    setDisputeModalError(null);
    setDecisionError(null);
    setDecisionNeedsRefresh(false);
    setDecisionSuccessMessage(null);
    try {
      const claimTargetId = claim.backendId || claim.id;
      // Resolves only when the backend confirms new_status === 'disputed'.
      const result = await claimsApi.submitSettlementDecision(claimTargetId, 'DISPUTE', disputeNotes.trim());
      applyConfirmedDecision(result.newStatus, { disputeNotes: disputeNotes.trim() });
      setShowDisputeModal(false);
      setDecisionSuccessMessage(result.message);
    } catch (err: unknown) {
      // Keep the modal open with the user's notes intact so they can retry safely.
      const decisionErr = toSettlementDecisionError(err);
      setDisputeModalError(decisionErr.message);
      setDecisionNeedsRefresh(decisionErr.requiresRefresh);
    } finally {
      decisionInFlightRef.current = false;
      setSubmittingDecision(false);
    }
  };

  // Reloads the authoritative claim from the backend so a retry is based on its real current status.
  const handleRefreshClaim = async () => {
    if (!id || refreshingClaim) return;
    const modalOpen = showDisputeModal;
    setRefreshingClaim(true);
    try {
      const fresh = await claimsApi.getClaimById(id);
      if (!fresh) throw new Error('Claim not found.');
      setClaim(fresh);
      setDecisionError(null);
      setDisputeModalError(null);
      setDecisionNeedsRefresh(false);
      setShowDisputeModal(false);
    } catch (err: any) {
      const message = `Could not reload the claim status${err?.message ? `: ${err.message}` : ''}. Please refresh the page.`;
      if (modalOpen) setDisputeModalError(message);
      else setDecisionError(message);
    } finally {
      setRefreshingClaim(false);
    }
  };

  const getStatusBadgeVariant = (status: string): 'success' | 'warning' | 'danger' | 'neutral' => {
    if (status === 'Approved' || status === 'Settlement Accepted') return 'success';
    if (status === 'Rejected' || status === 'Disputed' || status === 'Flagged') return 'danger';
    if (status === 'Under Review' || status === 'Action Required') return 'warning';
    return 'neutral';
  };

  if (loading) return <div className="text-muted p-xl text-center">Loading claim details...</div>;
  if (!claim) return <div className="text-muted p-xl text-center">Claim not found.</div>;

  return (
    <div ref={containerRef} className="flex flex-col gap-lg max-w-5xl mx-auto" style={{ maxWidth: '1800px', marginLeft: '0.8rem', paddingBottom: '8rem' }}>
      <div className="analysis-header flex items-center gap-md page-header mb-4">
        <Link to="/customer" className="btn-secondary btn-sm" style={{ padding: '0.5rem' }}>
          <ArrowLeft size={16} />
        </Link>
        <div>
          <div className="flex items-center gap-sm">
            <h2 className="text-2xl m-0">{claim.vehicle}</h2>
            <Badge variant={getStatusBadgeVariant(claim.status)}>{claim.status}</Badge>
          </div>
          <p className="text-muted text-sm mt-1">{claim.id} • {claim.claimType} • Submitted {new Date(claim.submittedAt).toLocaleDateString()}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-xl items-start">
        {/* Left Column: Analysis Visuals */}
        <div className="flex flex-col gap-md lg:sticky lg:top-6">
          {analysis && (analysis.imageUrl || selectedImage) ? (
            <Card style={{ padding: '0.5rem', overflow: 'hidden' }}>
              <DamageViewer
                analysis={{ ...analysis, imageUrl: selectedImage || analysis.imageUrl }}
                selectedDamageId={selectedDamage?.id}
                onSelectDamage={setSelectedDamage}
              />
            </Card>
          ) : (
            <Card className="flex flex-col items-center justify-center gap-md text-muted" style={{ minHeight: '380px' }}>
              <ShieldAlert size={48} opacity={0.4} />
              <div className="text-center">
                <p className="font-bold text-base text-primary">Damage Analysis In Progress</p>
                <p className="text-xs text-muted mt-1">Reviewing uploaded photos and vehicle damage...</p>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Details & Settlement Actions */}
        <div className="flex flex-col gap-md">
          {/* Customer Settlement Actions */}
          {(claim.status === 'Approved' || claim.rawStatus === 'agent_approved') && (
            <Card style={{ border: '1px solid var(--accent-primary)', backgroundColor: 'rgba(34, 197, 94, 0.04)' }}>
              <div className="flex flex-col gap-md">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-sm">
                    <CheckCircle size={20} color="var(--success)" />
                    <h3 className="text-base font-bold m-0" style={{ color: 'var(--text-primary)' }}>
                      Settlement Offer Ready
                    </h3>
                  </div>
                  <Badge variant="success">Action Required</Badge>
                </div>
                <p className="text-sm text-secondary m-0">
                  The reviewer has evaluated your claim and approved a settlement payout of <strong style={{ color: 'var(--success)' }}>₹{(claim.approvedAmount || 0).toLocaleString()}</strong>.
                </p>
                {claim.approveReason && (
                  <p className="text-xs text-muted p-2 m-0" style={{ background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)' }}>
                    Adjuster note: "{claim.approveReason}"
                  </p>
                )}

                {decisionError && (
                  <div role="alert" style={{ color: 'var(--danger)', fontSize: '0.8125rem' }}>
                    {decisionError}
                  </div>
                )}

                {decisionNeedsRefresh ? (
                  <div className="flex gap-md mt-2">
                    <button
                      id="settlement-refresh-claim-btn"
                      className="btn btn-primary"
                      disabled={refreshingClaim}
                      onClick={handleRefreshClaim}
                      style={{ flex: 1, padding: '0.625rem', fontWeight: 600 }}
                    >
                      {refreshingClaim ? 'Reloading...' : 'Reload Claim Status'}
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-md mt-2">
                    <button
                      id="settlement-accept-btn"
                      className="btn btn-primary"
                      disabled={submittingDecision}
                      onClick={handleAcceptSettlement}
                      style={{ flex: 1, padding: '0.625rem', fontWeight: 600 }}
                    >
                      {submittingDecision ? 'Processing...' : decisionError ? 'Retry Accept Settlement' : 'Accept Settlement'}
                    </button>
                    <button
                      id="settlement-dispute-btn"
                      className="btn-secondary"
                      disabled={submittingDecision}
                      onClick={() => setShowDisputeModal(true)}
                      style={{ flex: 1, padding: '0.625rem', fontWeight: 600, color: 'var(--warning)', borderColor: 'var(--warning)' }}
                    >
                      Dispute Settlement
                    </button>
                  </div>
                )}
              </div>
            </Card>
          )}

          {claim.status === 'Settlement Accepted' && (
            <Card style={{ border: '1px solid var(--success)', backgroundColor: 'rgba(34, 197, 94, 0.05)' }}>
              <div className="flex items-center gap-sm mb-2">
                <CheckCircle size={20} color="var(--success)" />
                <h3 className="text-base font-bold m-0" style={{ color: 'var(--success)' }}>
                  Settlement Accepted
                </h3>
              </div>
              <p className="text-sm text-primary mb-1">
                You accepted the settlement payout of <strong>₹{(claim.approvedAmount || 0).toLocaleString()}</strong>.
              </p>
              {decisionSuccessMessage && (
                <p role="status" className="text-sm m-0 mb-1" style={{ color: 'var(--success)', fontWeight: 600 }}>
                  {decisionSuccessMessage}
                </p>
              )}
              <p className="text-xs text-muted m-0">
                Settlement offer accepted. Payout status: not started (no payment provider integrated).
              </p>
            </Card>
          )}

          {claim.status === 'Disputed' && (
            <Card style={{ border: '1px solid var(--danger)', backgroundColor: 'rgba(239, 68, 68, 0.05)' }}>
              <div className="flex items-center gap-sm mb-2">
                <ShieldAlert size={20} color="var(--danger)" />
                <h3 className="text-base font-bold m-0" style={{ color: 'var(--danger)' }}>
                  Settlement Disputed
                </h3>
              </div>
              <p className="text-sm text-primary mb-1">
                This settlement has been disputed and escalated to a senior adjuster for priority re-evaluation.
              </p>
              {decisionSuccessMessage && (
                <p role="status" className="text-sm m-0 mb-1" style={{ fontWeight: 600 }}>
                  {decisionSuccessMessage}
                </p>
              )}
              {claim.disputeNotes && (
                <p className="text-xs text-muted p-2 mt-2 m-0" style={{ background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)' }}>
                  Your dispute notes: "{claim.disputeNotes}"
                </p>
              )}
              <p className="text-xs text-muted mt-2 m-0">
                Support Helpline: +91 (800) 252-4674 • 24/7 Priority Dispute Assistance
              </p>
            </Card>
          )}

          {/* 3D Mesh Viewer CTA */}
          <Link to={`/customer/claims/${id}/mesh`} className="interactive-card block p-md" style={{ background: 'rgba(255, 255, 255, 0.03)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255, 255, 255, 0.1)', textDecoration: 'none', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)' }}>
            <div className="flex items-center gap-md">
              <div style={{ background: 'rgba(255, 255, 255, 0.1)', padding: '0.8rem', borderRadius: '50%', color: 'var(--text-primary)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                <Box size={24} />
              </div>
              <div>
                <h3 className="text-base font-bold mb-1 m-0 flex items-center gap-sm" style={{ color: 'var(--text-primary)' }}>Explore 3D Damage Mesh <Badge variant="neutral">Beta</Badge></h3>
                <p className="text-xs text-muted m-0">Click here to view an interactive 3D spatial model of the vehicle damage assessment.</p>
              </div>
            </div>
          </Link>

          {/* Media Galleries */}
          {((claim.images && claim.images.length > 0) || (claim.videos && claim.videos.length > 0)) && (
            <Card>
              <h3 className="text-sm text-muted uppercase font-bold mb-4">Evidence Media</h3>
              {claim.images && claim.images.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-muted font-bold uppercase mb-2">Uploaded Photos ({claim.images.length})</p>
                  <div className="flex gap-sm overflow-x-auto pb-2">
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

              {claim.videos && claim.videos.length > 0 && (
                <div>
                  <p className="text-xs text-muted font-bold uppercase mb-2">Uploaded Videos ({claim.videos.length})</p>
                  <div className="flex gap-sm overflow-x-auto pb-2">
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
          )}

          <Card>
            <h3 className="text-sm text-muted uppercase font-bold flex items-center gap-sm mb-4"><Zap size={16} color="var(--accent-primary)" /> AI Assessment</h3>
            {analysis ? (
              <div className="flex flex-col gap-md">
                {analysis.damages.length > 0 ? (
                  <>
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
                  </>
                ) : (
                  <p className="text-sm text-muted">No structural damages detected from uploaded evidence.</p>
                )}

                {(analysis.totalEstimatedCost.max > 0 || claim.status === 'Approved') && (
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
                      {claim.status === 'Approved'
                        ? 'Final approved claim payout.'
                        : analysis.estimateBasis
                          ? `Estimate basis: ${analysis.estimateBasis}. This is indicative, uncalibrated guidance and is not a settlement guarantee.`
                          : '*AI-generated cost estimates are indicative and may vary following assessment and approval by a qualified engineer.'}
                    </p>
                  </div>
                )}

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
              <p className="text-muted text-sm">Damage assessment is currently in progress or awaiting reviewer confirmation. Check back shortly.</p>
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

      {/* Dispute Settlement Modal */}
      {showDisputeModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.6)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            padding: '2rem',
            width: '100%',
            maxWidth: '480px',
            boxShadow: '0 24px 48px -12px rgba(0, 0, 0, 0.5)'
          }}>
            <h3 className="text-lg font-bold mb-2">Dispute Settlement Offer</h3>
            <p className="text-xs text-muted mb-4">
              Please specify the reasons why you dispute the proposed repair settlement of ₹{(claim.approvedAmount || 0).toLocaleString()}. Your notes will be escalated directly to our senior claims adjuster.
            </p>

            {disputeModalError && (
              <div role="alert" style={{ color: 'var(--danger)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>
                {disputeModalError}
              </div>
            )}

            <textarea
              className="form-input"
              rows={4}
              value={disputeNotes}
              onChange={e => {
                setDisputeNotes(e.target.value);
                if (disputeModalError) setDisputeModalError(null);
              }}
              placeholder="e.g. Authorized service center quoted higher for OEM replacement parts..."
              style={{ width: '100%', resize: 'vertical', marginBottom: '1.25rem' }}
            />

            <div className="flex justify-end gap-sm">
              <button
                id="dispute-cancel-btn"
                className="btn-secondary"
                disabled={submittingDecision || refreshingClaim}
                onClick={() => {
                  setShowDisputeModal(false);
                  setDisputeModalError(null);
                }}
                style={{ padding: '0.5rem 1rem' }}
              >
                Cancel
              </button>
              {decisionNeedsRefresh ? (
                <button
                  id="dispute-refresh-claim-btn"
                  className="btn btn-primary"
                  disabled={refreshingClaim}
                  onClick={handleRefreshClaim}
                  style={{ padding: '0.5rem 1rem' }}
                >
                  {refreshingClaim ? 'Reloading...' : 'Reload Claim Status'}
                </button>
              ) : (
                <button
                  id="dispute-submit-btn"
                  className="btn btn-primary"
                  disabled={submittingDecision}
                  onClick={handleSubmitDispute}
                  style={{ padding: '0.5rem 1rem', backgroundColor: 'var(--danger)', borderColor: 'var(--danger)' }}
                >
                  {submittingDecision ? 'Submitting...' : disputeModalError ? 'Retry Dispute' : 'Submit Dispute'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
