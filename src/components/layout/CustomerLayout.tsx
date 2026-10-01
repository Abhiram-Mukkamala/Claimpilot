import React, { useEffect, useState, useRef } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../store/authStore';
import { claimsApi } from '../../services/claimsApi';
import type { Claim } from '../../types/claim';
import { Badge } from '../ui/Badge';
import { LogOut, Plus, ChevronDown } from 'lucide-react';
import { TopBar } from './TopBar';
import { gsap, useGSAP, animateFadeIn, animateStagger, isReducedMotion } from '../../lib/gsap';

export const CustomerLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [claims, setClaims] = useState<Claim[]>([]);
  const homeRef = useRef<HTMLDivElement>(null);
  const claimsListRef = useRef<HTMLDivElement>(null);
  const chevronRef = useRef<HTMLDivElement>(null);
  const isFirstMount = useRef(true);

  const isHome = location.pathname === '/customer';
  const [claimsMinimized, setClaimsMinimized] = useState(false);

  useEffect(() => {
    claimsApi.getClaims().then(setClaims);
  }, []);

  useGSAP(() => {
    if (isHome) {
      animateFadeIn('.customer-home-brand', { y: 12, duration: 0.4 });
      animateFadeIn('.customer-home-title', { y: 10, delay: 0.05 });
      animateStagger('.customer-quick-card', { stagger: 0.06, y: 10, delay: 0.1 });
    }
  }, { scope: homeRef, dependencies: [isHome] });

  useGSAP(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }

    const listEl = claimsListRef.current;
    const chevronEl = chevronRef.current;
    if (!listEl) return;

    if (isReducedMotion()) {
      if (claimsMinimized) {
        listEl.style.display = 'none';
        if (chevronEl) chevronEl.style.transform = 'rotate(-90deg)';
      } else {
        listEl.style.display = 'flex';
        listEl.style.flex = '1';
        listEl.style.height = '';
        listEl.style.opacity = '1';
        if (chevronEl) chevronEl.style.transform = 'rotate(0deg)';
      }
      return;
    }

    gsap.killTweensOf(listEl);
    if (chevronEl) gsap.killTweensOf(chevronEl);

    if (claimsMinimized) {
      if (chevronEl) {
        gsap.to(chevronEl, {
          rotation: -90,
          duration: 0.28,
          ease: 'power2.inOut',
        });
      }

      const startHeight = listEl.offsetHeight;
      listEl.style.flex = 'none';
      listEl.style.height = `${startHeight}px`;

      gsap.to(listEl, {
        height: 0,
        opacity: 0,
        duration: 0.28,
        ease: 'power2.inOut',
        onComplete: () => {
          listEl.style.display = 'none';
        },
      });
    } else {
      if (chevronEl) {
        gsap.to(chevronEl, {
          rotation: 0,
          duration: 0.3,
          ease: 'power2.out',
        });
      }

      listEl.style.display = 'flex';
      listEl.style.flex = 'none';
      listEl.style.height = 'auto';
      const targetHeight = listEl.scrollHeight;
      listEl.style.height = '0px';
      listEl.style.opacity = '0';

      gsap.to(listEl, {
        height: targetHeight,
        opacity: 1,
        duration: 0.32,
        ease: 'power2.out',
        onComplete: () => {
          listEl.style.flex = '1';
          listEl.style.height = '';
        },
      });

      const claimItems = listEl.querySelectorAll('.sidebar-claim-link');
      if (claimItems.length > 0) {
        gsap.fromTo(
          claimItems,
          { opacity: 0, y: -6 },
          {
            opacity: 1,
            y: 0,
            duration: 0.22,
            stagger: 0.035,
            delay: 0.05,
            ease: 'power2.out',
            clearProps: 'transform,opacity',
          }
        );
      }
    }
  }, [claimsMinimized]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getBadgeVariant = (status: string): 'success' | 'warning' | 'danger' | 'neutral' => {
    if (status === 'Approved') return 'success';
    if (status === 'Flagged' || status === 'Rejected') return 'danger';
    return 'warning';
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '1rem' }}>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        borderRadius: 'var(--radius-xl)',
        overflow: 'hidden',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        background: 'rgba(14, 14, 20, 0.01)',
        backdropFilter: 'blur(5px) saturate(100%)',
        WebkitBackdropFilter: 'blur(5px) saturate(120%)',
        boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.14)'
      }}>
        <TopBar />
        <div style={{ display: 'flex', flex: 1, height: 'calc(100vh - 72px - 2rem)', overflow: 'hidden', position: 'relative' }}>
          {/* ── Sidebar ── */}
          <aside className="sidebar">
            {/* Logo */}
            <div className="sidebar-header">
              <span className="sidebar-title">
                Dashboard
              </span>
              <button
                onClick={handleLogout}
                title="Sign out"
                className="btn-ghost"
                style={{ padding: '0.25rem', display: 'flex', alignItems: 'center' }}
              >
                <LogOut size={14} />
              </button>
            </div>

            {/* New Claim button */}
            <div className="sidebar-actions">
              <Link to="/customer/new-claim" className="sidebar-nav-btn">
                <Plus size={14} />
                New Claim
              </Link>
            </div>

            {/* Past claims list */}
            <div className="sidebar-claims">
              <div
                className="sidebar-section-header"
                onClick={() => setClaimsMinimized(prev => !prev)}
                role="button"
                tabIndex={0}
                aria-expanded={!claimsMinimized}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setClaimsMinimized(prev => !prev);
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                <p className="sidebar-section-label">
                  Your Claims
                </p>
                <div
                  ref={chevronRef}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transformOrigin: '50% 50%',
                    willChange: 'transform',
                  }}
                >
                  <ChevronDown size={14} color="var(--text-secondary)" />
                </div>
              </div>

              <div
                ref={claimsListRef}
                className="sidebar-claims-list-wrapper"
                style={{
                  flex: 1,
                  minHeight: 0,
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <div className="sidebar-claims-list">
                  {claims.length === 0 ? (
                    <p style={{
                      fontSize: '0.75rem',
                      color: 'var(--text-secondary)',
                      padding: '0.5rem 1.25rem',
                    }}>
                      No claims yet.
                    </p>
                  ) : (
                    claims.map(claim => {
                      const isActive = location.pathname === `/customer/claims/${claim.id}`;
                      return (
                        <Link
                          key={claim.id}
                          to={`/customer/claims/${claim.id}`}
                          className={`sidebar-claim-link ${isActive ? 'active' : ''}`}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                            <span className="sidebar-claim-id">
                              {claim.id}
                            </span>
                            <Badge variant={getBadgeVariant(claim.status)}>{claim.status}</Badge>
                          </div>
                          <p className="sidebar-claim-vehicle">
                            {claim.vehicle}
                          </p>
                          <p className="sidebar-claim-date">
                            {new Date(claim.submittedAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                          </p>
                        </Link>
                      );
                    })
                  )}
                </div>
              </div>
            </div>

            {/* User footer */}
            <div className="sidebar-footer">
              <div className="sidebar-avatar">
                {user?.name?.charAt(0).toUpperCase()}
              </div>
              <div style={{ overflow: 'hidden', flex: 1 }}>
                <p className="sidebar-user-name">
                  {user?.name}
                </p>
                <p className="sidebar-user-role">Personal Account</p>
              </div>

            </div>
          </aside>

          {/* ── Main content ── */}
          <main style={{ flex: 1, overflowY: 'auto', height: '100%', minWidth: 0 }}>
            {isHome ? (
              /* Home state — centered CTA like Claude new chat */
              <div ref={homeRef} className="customer-home">
                <div className="customer-home-inner">
                  <div className="customer-home-brand">
                    ClaimPilot AI
                  </div>
                  <h1 className="customer-home-title" style={{
                    fontSize: '1.75rem',
                    fontWeight: 700,
                    letterSpacing: '-0.04em',
                    color: 'var(--text-primary)',
                    marginBottom: '0.5rem',
                  }}>
                    How can we help?
                  </h1>
                  <p style={{
                    fontSize: '0.9375rem',
                    color: 'var(--text-secondary)',
                    marginBottom: '2.5rem',
                    lineHeight: 1.6,
                  }}>
                    File a new insurance claim or select one from the sidebar to check its status.
                  </p>

                  <Link
                    to="/customer/new-claim"
                    className="btn btn-file-claim"
                    style={{
                      padding: '0.85rem 1.85rem',
                      fontSize: '1rem',
                      gap: '0.5rem',
                    }}
                  >
                    <Plus size={18} strokeWidth={2.5} />
                    File a New Claim
                  </Link>

                  {/* Quick feature list */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr 1fr',
                    gap: '0.75rem',
                    marginTop: '3rem',
                  }}>
                    {[
                      { label: 'Collision', sub: 'Accident damage', type: 'Accident' },
                      { label: 'Fire', sub: 'Vehicle fire', type: 'Fire' },
                      { label: 'Natural Event', sub: 'Flood, earthquake, etc.', type: 'Natural Event' },
                    ].map(item => (
                      <Link
                        key={item.label}
                        to={`/customer/new-claim?type=${encodeURIComponent(item.type)}`}
                        className="interactive-card customer-quick-card ambient-glow-card"
                        style={{
                          padding: '1.5rem',
                          textAlign: 'left',
                          textDecoration: 'none',
                        }}
                      >
                        <p style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                          {item.label}
                        </p>
                        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{item.sub}</p>
                      </Link>
                    ))}
                  </div>

                </div>
              </div>
            ) : (
              <div className="customer-content">
                <Outlet />
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};


