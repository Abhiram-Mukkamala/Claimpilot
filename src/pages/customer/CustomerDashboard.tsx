import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../store/authStore';
import { claimsApi } from '../../services/claimsApi';
import type { Claim } from '../../types/claim';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { ChevronRight, FilePlus } from 'lucide-react';
import { useGSAP, animateFadeIn, animateStagger } from '../../lib/gsap';

export const CustomerDashboard = () => {
  const { user } = useAuth();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    claimsApi.getClaims().then(data => {
      setClaims(data);
      setLoading(false);
    });
  }, []);

  // Stagger sections in once data is ready
  useGSAP(() => {
    if (loading) return;
    animateFadeIn('.cd-header', { y: 8, duration: 0.32 });
    animateFadeIn('.cd-cta', { y: 10, duration: 0.35, delay: 0.05 });
    animateFadeIn('.cd-active', { y: 10, duration: 0.35, delay: 0.1 });
    animateStagger('.cd-past-item', { stagger: 0.05, y: 8, delay: 0.14 });
  }, { scope: containerRef, dependencies: [loading] });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Approved': return <Badge variant="success">Approved</Badge>;
      case 'Flagged':
      case 'Rejected': return <Badge variant="danger">{status}</Badge>;
      default: return <Badge variant="warning">{status}</Badge>;
    }
  };

  // Helper for linear progress
  const getProgress = (status: string) => {
    const steps = ['Submitted', 'AI Assessment', 'Review'];
    let currentIndex = 0;
    if (status === 'Pending Review' || status === 'AI Assessment') currentIndex = 1;
    if (status === 'Agent Review' || status === 'Decision Pending') currentIndex = 2;
    if (status === 'Approved' || status === 'Rejected') currentIndex = 3; // completed
    return { steps, currentIndex };
  };

  const activeClaim = claims[0]; // Just picking the first one as active for demo
  const pastClaims = claims.slice(1);

  return (
    <div ref={containerRef} className="flex flex-col gap-xl max-w-4xl mx-auto" style={{ maxWidth: '900px', margin: '0 auto' }}>
      <section className="cd-header mt-8">
        <h1 className="text-2xl mb-2">Good evening, {user?.name.split(' ')[0] || 'User'}</h1>
        <p className="text-muted">Your insurance claims portal.</p>
      </section>

      {/* Primary Call to Action */}
      <Link to="/customer/new-claim" className="cd-cta">
        <div className="interactive-card flex justify-between items-center" style={{ padding: '2rem', border: '1px dashed var(--border-light)' }}>
          <div className="flex items-center gap-md">
            <div style={{ backgroundColor: 'var(--bg-tertiary)', padding: '1rem', borderRadius: '50%' }}>
              <FilePlus size={24} color="var(--accent-primary)" />
            </div>
            <div>
              <h2 className="text-lg">Request New Claim</h2>
              <p className="text-sm text-muted">Start a new accident, fire, or natural event claim</p>
            </div>
          </div>
          <ChevronRight size={24} color="var(--text-secondary)" />
        </div>
      </Link>

      {/* Active Claim Focus */}
      {loading ? (
        <p className="text-muted">Loading your claims...</p>
      ) : activeClaim && (
        <section className="cd-active">
          <h2 className="text-sm text-muted uppercase font-bold mb-4">Active Claim</h2>
          <Card style={{ padding: '0' }} className="overflow-hidden">
            <div className="flex justify-between items-start p-lg" style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-color)' }}>
              <div>
                <h3 className="text-xl mb-1">{activeClaim.vehicle}</h3>
                <p className="text-muted">{activeClaim.id} • {activeClaim.claimType}</p>
              </div>
              {getStatusBadge(activeClaim.status)}
            </div>

            <div style={{ padding: '1.5rem', backgroundColor: 'rgba(255, 255, 255, 0.02)' }}>
              <div className="flex justify-between items-center relative mb-4">
                {/* Progress Bar Track */}
                <div style={{ position: 'absolute', top: '50%', left: '10%', right: '10%', height: '2px', backgroundColor: 'var(--border)', zIndex: 0 }} />

                {getProgress(activeClaim.status).steps.map((step, idx) => {
                  const isActive = getProgress(activeClaim.status).currentIndex >= idx;
                  return (
                    <div key={idx} className="flex flex-col items-center gap-sm relative" style={{ zIndex: 1, backgroundColor: 'rgba(20, 20, 28, 0.7)', backdropFilter: 'blur(8px)', borderRadius: 'var(--radius-sm)', padding: '0.25rem 0.75rem' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: isActive ? 'var(--accent-primary)' : 'var(--border-strong)' }} />
                      <span className="text-xs" style={{ color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{step}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <Link to={`/customer/claims/${activeClaim.id}`} className="block interactive-row text-center p-md text-sm font-bold" style={{ color: 'var(--accent-primary)', borderTop: '1px solid var(--border-color)', padding: '1rem' }}>
              View Full Details →
            </Link>
          </Card>
        </section>
      )}

      {/* Past Claims */}
      {pastClaims.length > 0 && (
        <section>
          <h2 className="text-sm text-muted uppercase font-bold mb-4">Recent Claims</h2>
          <div className="flex flex-col gap-sm">
            {pastClaims.map(claim => (
              <Link key={claim.id} to={`/customer/claims/${claim.id}`} className="cd-past-item">
                <div className="interactive-card flex justify-between items-center">
                  <div>
                    <h3 className="text-base mb-1">{claim.vehicle}</h3>
                    <p className="text-xs text-muted">{claim.id} • {new Date(claim.submittedAt).toLocaleDateString()}</p>
                  </div>
                  <div className="flex items-center gap-md">
                    {getStatusBadge(claim.status)}
                    <ChevronRight size={16} color="var(--text-secondary)" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};
