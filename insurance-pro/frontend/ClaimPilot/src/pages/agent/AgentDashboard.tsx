import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { claimsApi } from '../../services/claimsApi';
import type { Claim } from '../../types/claim';
import { Badge } from '../../components/ui/Badge';
import { AlertTriangle, CheckCircle, Clock, ArrowRight } from 'lucide-react';
import { useAuth } from '../../store/authStore';
import { useGSAP, animateStagger } from '../../lib/gsap';

export const AgentDashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [claims, setClaims] = useState<Claim[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let isMounted = true;
    claimsApi.getClaims().then(data => {
      if (isMounted) {
        setClaims(data || []);
      }
    }).catch(err => {
      console.error('Error loading claims in dashboard:', err);
      if (isMounted) {
        setClaims([]);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  useGSAP(() => {
    if (claims.length === 0) return;
    animateStagger('.kpi-card', { stagger: 0.05, y: 10 });
    animateStagger('.queue-item', { stagger: 0.04, y: 8, delay: 0.08 });
    animateStagger('.activity-item', { stagger: 0.05, y: 6, delay: 0.12 });
  }, { scope: containerRef, dependencies: [claims.length] });

  const pending = claims.filter(c => c.status === 'Pending Review' || c.status === 'Decision Pending' || c.status === 'Under Review' || c.status === 'Flagged');
  const highRisk = claims.filter(c => c.fraudRisk === 'High');
  const todayStr = new Date().toDateString();
  const newToday = claims.filter(c => c.submittedAt && new Date(c.submittedAt).toDateString() === todayStr);
  const approvedToday = claims.filter(c => c.status === 'Approved' && c.reviewedAt && new Date(c.reviewedAt).toDateString() === todayStr).length;

  const priorityQueue = [...highRisk, ...pending].filter((c, i, arr) => arr.findIndex(x => x.id === c.id) === i).slice(0, 4);

  const getRiskColor = (risk?: string) => {
    if (risk === 'High') return 'var(--danger)';
    if (risk === 'Medium') return 'var(--warning)';
    return 'var(--success)';
  };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const kpis = [
    { label: 'Need Review', value: pending.length, color: undefined },
    { label: 'High Risk', value: highRisk.length, color: 'var(--danger)' },
    { label: 'New Today', value: newToday.length, color: undefined },
    { label: 'SLA Risk', value: claims.filter(c => c.fraudRisk === 'High' && c.status !== 'Approved' && c.status !== 'Rejected').length, color: 'var(--warning)' },
  ];

  const activity = claims.slice(0, 4).map(c => {
    let icon = <Clock size={15} color="var(--accent)" />;
    let desc = `Claim submitted for ${c.vehicle}`;
    if (c.status === 'Approved') {
      icon = <CheckCircle size={15} color="var(--success)" />;
      desc = `Claim approved (${c.approvedAmount ? `₹${c.approvedAmount.toLocaleString()}` : 'Settlement issued'})`;
    } else if (c.status === 'Settlement Accepted') {
      icon = <CheckCircle size={15} color="var(--success)" />;
      desc = `Customer accepted settlement offer`;
    } else if (c.status === 'Disputed') {
      icon = <AlertTriangle size={15} color="var(--danger)" />;
      desc = `Customer disputed settlement amount`;
    } else if (c.fraudRisk === 'High') {
      icon = <AlertTriangle size={15} color="var(--danger)" />;
      desc = `Flagged for high fraud risk`;
    }

    const timeAgo = c.submittedAt ? new Date(c.submittedAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : 'Recent';

    return {
      icon,
      id: c.id,
      desc,
      time: timeAgo
    };
  });

  return (
    <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', gap: '2rem', paddingBottom: '3rem', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>

      {/* ── Page header ── */}
      <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '1.25rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.03em', marginBottom: '0.25rem' }}>
          {greeting}, {user?.name ? user.name.split(' ')[0] : 'Agent'}
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
          {new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          {' '}· Claims Operations
        </p>
      </div>

      {/* ── KPI cards ── */}
      <div className="kpi-grid">
        {kpis.map(kpi => (
          <div key={kpi.label} className="kpi-card ambient-glow-card" style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '1.125rem 1.25rem',
          }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '1.75rem',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: kpi.color ?? 'var(--text-primary)',
              lineHeight: 1,
              marginBottom: '0.5rem',
            }}>
              {kpi.value}
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              {kpi.label}
            </div>
          </div>
        ))}
      </div>

      {/* ── Two-column body ── */}
      <div className="dashboard-layout">

        {/* Left: Priority Queue */}
        <div style={{ flex: 2, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <p style={{
              fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.07em',
              textTransform: 'uppercase', color: 'var(--text-secondary)',
            }}>
              Priority Queue
            </p>
            <button
              className="btn-ghost"
              style={{ fontSize: '0.8125rem', color: 'var(--accent)', padding: '0.25rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
              onClick={() => navigate('/agent/claims')}
            >
              View all <ArrowRight size={13} />
            </button>
          </div>

          {/* Queue table */}
          <div style={{
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
          }}>
            {priorityQueue.length === 0 ? (
              <p style={{ padding: '2rem', color: 'var(--text-secondary)', textAlign: 'center', fontSize: '0.9375rem' }}>
                No items in queue
              </p>
            ) : priorityQueue.map((claim, idx) => (
              <div
                key={claim.id}
                className="queue-item"
                onClick={() => navigate(`/agent/claims/${claim.id}`)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.9375rem 1.125rem',
                  borderBottom: idx < priorityQueue.length - 1 ? '1px solid var(--border)' : 'none',
                  cursor: 'pointer',
                  transition: 'background-color 0.1s',
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--bg-hover)')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                {/* Left: claim info */}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.8125rem',
                      fontWeight: 600,
                      color: 'var(--text-primary)',
                      letterSpacing: '0.01em',
                    }}>
                      {claim.id}
                    </span>
                    <span style={{ fontSize: '0.9375rem', color: 'var(--text-secondary)' }}>
                      {claim.customerName}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{
                      width: '6px', height: '6px', borderRadius: '50%',
                      backgroundColor: getRiskColor(claim.fraudRisk),
                      flexShrink: 0,
                    }} />
                    <span style={{ fontSize: '0.8125rem', color: getRiskColor(claim.fraudRisk), fontWeight: 500 }}>
                      {claim.fraudRisk || 'Low'} Risk
                    </span>
                    <span style={{ color: 'var(--border-strong)' }}>·</span>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {claim.vehicle}
                    </span>
                    <span style={{ color: 'var(--border-strong)' }}>·</span>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {claim.claimType}
                    </span>
                  </div>
                </div>

                {/* Right: badge + action */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
                  <Badge variant={
                    claim.status === 'Approved' ? 'success' :
                      claim.status === 'Flagged' || claim.status === 'Rejected' ? 'danger' : 'warning'
                  }>
                    {claim.status}
                  </Badge>
                  <ArrowRight size={15} color="var(--text-secondary)" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Workload + Activity */}
        <div style={{ flex: 1, minWidth: '240px', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>

          {/* Today's Workload */}
          <div>
            <p style={{
              fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.07em',
              textTransform: 'uppercase', color: 'var(--text-secondary)',
              marginBottom: '1rem',
            }}>
              Today's Workload
            </p>
            <div style={{
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
            }}>
              {[
                { label: 'New Claims', value: newToday.length, color: undefined },
                { label: 'Pending Review', value: pending.length, color: undefined },
                { label: 'High Risk', value: highRisk.length, color: 'var(--danger)' },
                { label: 'Approved Today', value: approvedToday, color: 'var(--success)' },
              ].map((row, idx, arr) => (
                <div
                  key={row.label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 1.125rem',
                    borderBottom: idx < arr.length - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <span style={{ fontSize: '0.9375rem', color: row.color ?? 'var(--text-primary)' }}>
                    {row.label}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.9375rem',
                    fontWeight: 600,
                    color: row.color ?? 'var(--text-primary)',
                  }}>
                    {row.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <div>
            <p style={{
              fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.07em',
              textTransform: 'uppercase', color: 'var(--text-secondary)',
              marginBottom: '1rem',
            }}>
              Recent Activity
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
              {activity.length === 0 ? (
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', margin: 0 }}>
                  No recent claim activities.
                </p>
              ) : activity.map(item => (
                <div key={item.id} className="activity-item" style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                  <div style={{ marginTop: '0.125rem', flexShrink: 0 }}>{item.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.125rem' }}>
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                        color: 'var(--text-primary)',
                      }}>
                        {item.id}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', flexShrink: 0, marginLeft: '0.5rem' }}>
                        {item.time}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                      {item.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};