import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { claimsApi } from '../../services/claimsApi';
import type { Claim } from '../../types/claim';
import { Badge } from '../../components/ui/Badge';
import { Drawer } from '../../components/ui/Drawer';
import { Search, AlertTriangle } from 'lucide-react';
import { useGSAP, animateFadeIn, animateStagger } from '../../lib/gsap';

export const AgentClaims = () => {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [activeFilter, setActiveFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    claimsApi.getClaims().then(data => {
      setClaims(data);
      setLoading(false);
    });
  }, []);

  // Header entrance — runs once
  useGSAP(() => {
    animateFadeIn('.ac-header', { y: 8, duration: 0.32 });
    animateFadeIn('.ac-toolbar', { y: 6, duration: 0.3, delay: 0.07 });
  }, { scope: containerRef });

  // Rows stagger whenever visible list changes
  useGSAP(() => {
    if (!loading) {
      animateStagger('.claim-row', { stagger: 0.03, y: 6, duration: 0.28, delay: 0.04 });
    }
  }, { scope: containerRef, dependencies: [loading, activeFilter, searchQuery] });

  const getRiskColor = (risk: string) => {
    if (risk === 'High') return 'var(--danger)';
    if (risk === 'Medium') return 'var(--warning)';
    return 'var(--success)';
  };

  const filteredClaims = claims.filter(claim => {
    // 1. Search Query
    if (searchQuery && !claim.id.toLowerCase().includes(searchQuery.toLowerCase()) && !claim.customerName.toLowerCase().includes(searchQuery.toLowerCase()) && !claim.vehicle.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }

    // 2. Tab Filter
    if (activeFilter === 'New') {
      return new Date(claim.submittedAt).toDateString() === new Date().toDateString();
    }
    if (activeFilter === 'Needs Review') {
      return claim.status === 'Pending Review' || claim.status === 'Decision Pending';
    }
    if (activeFilter === 'High Risk') {
      return claim.fraudRisk === 'High';
    }
    if (activeFilter === 'Approved') {
      return claim.status === 'Approved';
    }
    if (activeFilter === 'Reviewed Claims') {
      return Boolean(
        claim.reviewedByAgent ||
        claim.status === 'Approved' ||
        claim.status === 'Rejected' ||
        claim.requestInfoReason ||
        claim.agentAction
      );
    }
    return true; // 'All'
  });

  return (
    <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', paddingBottom: '3rem' }}>

      {/* ── Header ── */}
      <div className="ac-header" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '1.25rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.03em', marginBottom: '0.25rem' }}>
          All Claims
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
          {claims.length} total claims in queue
        </p>
      </div>

      {/* ── Toolbar ── */}
      <div className="ac-toolbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>

        {/* Filter Tabs */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {['All', 'New', 'Needs Review', 'High Risk', 'Approved', 'Reviewed Claims'].map((tab) => {
            const isActive = tab === activeFilter;
            return (
              <button
                key={tab}
                onClick={() => setActiveFilter(tab)}
                className={isActive ? 'btn-secondary' : 'btn-ghost'}
                style={{
                  padding: '0.375rem 0.75rem',
                  fontSize: '0.8125rem',
                  color: tab === 'High Risk' && !isActive ? 'var(--danger)' : undefined,
                  fontWeight: isActive ? 600 : 500,
                  backgroundColor: isActive ? 'var(--bg-hover)' : 'transparent',
                  borderColor: isActive ? 'var(--border-strong)' : 'transparent',
                }}
              >
                {tab}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} color="var(--text-secondary)" style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              className="form-input"
              placeholder="Search claims..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '2.25rem', paddingTop: '0.375rem', paddingBottom: '0.375rem', fontSize: '0.8125rem', width: '240px' }}
            />
          </div>
        </div>
      </div>

      {/* ── Data Table ── */}
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th style={{ width: '120px' }}>Claim ID</th>
              <th>Customer</th>
              <th>Vehicle</th>
              <th>Type</th>
              <th>Submitted</th>
              <th>Status</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '2rem' }}>Loading claims...</td></tr>
            ) : filteredClaims.length === 0 ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '2rem' }}>No claims found for this filter.</td></tr>
            ) : (
              filteredClaims.map(claim => (
                <tr
                  key={claim.id}
                  className={`interactive-row claim-row ${selectedClaim?.id === claim.id ? 'selected-row' : ''}`}
                  onClick={() => setSelectedClaim(claim)}
                >
                  <td>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.8125rem' }}>
                      {claim.id}
                    </span>
                  </td>
                  <td style={{ fontWeight: 500 }}>{claim.customerName}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{claim.vehicle}</td>
                  <td>{claim.claimType}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                    {new Date(claim.submittedAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </td>
                  <td>
                    <Badge variant={
                      claim.status === 'Approved' ? 'success' :
                        claim.status === 'Flagged' || claim.status === 'Rejected' ? 'danger' : 'warning'
                    }>
                      {claim.status}
                    </Badge>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: getRiskColor(claim.fraudRisk) }} />
                      <span style={{ fontSize: '0.8125rem', color: getRiskColor(claim.fraudRisk), fontWeight: 500 }}>
                        {claim.fraudRisk}
                      </span>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ── Quick Preview Drawer ── */}
      <Drawer
        isOpen={!!selectedClaim}
        onClose={() => setSelectedClaim(null)}
        title={selectedClaim ? `Claim ${selectedClaim.id}` : ''}
      >
        {selectedClaim && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

            {/* Header info */}
            <div>
              <p style={{ fontSize: '1.25rem', fontWeight: 600, letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>
                {selectedClaim.vehicle}
              </p>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                {selectedClaim.customerName} • {selectedClaim.claimType}
              </p>
            </div>

            {/* Evidence Image Placeholder */}
            <div style={{
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              border: '1px solid var(--border)',
              backgroundColor: 'var(--bg-hover)',
              height: '240px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative'
            }}>
              <div style={{ position: 'absolute', inset: 0, opacity: 0.1, backgroundImage: 'linear-gradient(45deg, #000 25%, transparent 25%, transparent 75%, #000 75%, #000), linear-gradient(45deg, #000 25%, transparent 25%, transparent 75%, #000 75%, #000)', backgroundSize: '20px 20px', backgroundPosition: '0 0, 10px 10px' }} />
              <div style={{ textAlign: 'center', zIndex: 1 }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-strong)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem auto' }}>
                  <span style={{ fontSize: '1.25rem' }}>📷</span>
                </div>
                <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>AI Evidence Extraction</p>
                <p style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Awaiting media payload...</p>
              </div>
            </div>

            {/* Quick Stats Box */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              padding: '1.25rem',
              backgroundColor: 'var(--bg-surface)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Status</span>
                <Badge variant={
                  selectedClaim.status === 'Approved' ? 'success' :
                    selectedClaim.status === 'Flagged' || selectedClaim.status === 'Rejected' ? 'danger' : 'warning'
                }>
                  {selectedClaim.status}
                </Badge>
              </div>
              {selectedClaim.approvedAmount && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Approved Payout</span>
                  <span style={{ fontWeight: 600, color: 'var(--success)', fontSize: '0.875rem' }}>
                    ₹{selectedClaim.approvedAmount.toLocaleString()}
                  </span>
                </div>
              )}
              {selectedClaim.rejectionReason && (
                <div style={{ fontSize: '0.75rem', color: 'var(--danger)', padding: '0.5rem', backgroundColor: 'rgba(239, 68, 68, 0.08)', borderRadius: 'var(--radius-sm)' }}>
                  <strong>Rejection Reason:</strong> {selectedClaim.rejectionReason}
                </div>
              )}
              {selectedClaim.requestInfoReason && (
                <div style={{ fontSize: '0.75rem', color: 'var(--warning)', padding: '0.5rem', backgroundColor: 'rgba(234, 179, 8, 0.08)', borderRadius: 'var(--radius-sm)' }}>
                  <strong>More Info Requested:</strong> {selectedClaim.requestInfoReason}
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                  <AlertTriangle size={14} /> Fraud Risk
                </span>
                <span style={{
                  fontWeight: 600,
                  color: getRiskColor(selectedClaim.fraudRisk)
                }}>
                  {selectedClaim.fraudRisk}
                </span>
              </div>
            </div>

            {/* AI Summary Placeholder */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '1rem', backgroundColor: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-strong)' }}>
              <span className="section-label" style={{ marginBottom: '0', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent)', animation: 'pulse 2s infinite' }} />
                AI Summary & Estimation
              </span>
              <p style={{ fontSize: '0.9375rem', lineHeight: 1.5, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                Generative AI is processing damage patterns and assessing historical repair benchmarks...
              </p>
              <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <div style={{ height: '24px', width: '120px', backgroundColor: 'var(--bg-surface)', borderRadius: '4px', border: '1px solid var(--border)' }} />
                <div style={{ height: '24px', width: '80px', backgroundColor: 'var(--bg-surface)', borderRadius: '4px', border: '1px solid var(--border)' }} />
              </div>
            </div>

            {/* Action */}
            <div style={{ marginTop: '1rem' }}>
              <button
                className="btn-primary"
                style={{ width: '100%', padding: '0.75rem' }}
                onClick={() => navigate(`/agent/claims/${selectedClaim.id}`)}
              >
                Open Investigation Workspace
              </button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};
