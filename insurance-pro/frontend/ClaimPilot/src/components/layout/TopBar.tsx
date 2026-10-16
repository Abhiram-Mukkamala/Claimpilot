import React, { useRef } from 'react';
import { Link } from 'react-router-dom';
import { HelpCircle } from 'lucide-react';
import { gsap, isReducedMotion } from '../../lib/gsap';

interface TopBarProps {
  onOpenHowItWorks?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenHowItWorks }) => {
  const btnRef = useRef<HTMLButtonElement>(null);

  const handleMouseEnter = () => {
    if (isReducedMotion() || !btnRef.current) return;
    gsap.to(btnRef.current, {
      scale: 1.04,
      duration: 0.2,
      ease: 'power2.out',
    });
  };

  const handleMouseLeave = () => {
    if (isReducedMotion() || !btnRef.current) return;
    gsap.to(btnRef.current, {
      scale: 1,
      duration: 0.2,
      ease: 'power2.out',
    });
  };

  return (
    <div className="topbar">
      {/* Logo */}
      <span className="topbar-logo" style={{ flexShrink: 0 }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7l10 5 10-5-10-5z" fill="var(--accent)" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        ClaimPilot AI
      </span>

      {/* Home link — centred */}
      <nav style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
      }}>
        <Link to="/customer" className="topbar-nav-btn">
          Home
        </Link>
      </nav>

      {/* How it works button — right aligned */}
      {onOpenHowItWorks ? (
        <button
          ref={btnRef}
          onClick={onOpenHowItWorks}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          className="topbar-nav-btn"
          title="Learn how to file a claim with ClaimPilot"
          aria-label="How it works tutorial"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.35rem 0.85rem',
            borderRadius: '999px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            fontSize: '0.85rem',
            cursor: 'pointer',
            transition: 'background 0.2s, border-color 0.2s',
          }}
        >
          <HelpCircle size={15} style={{ color: 'var(--accent)' }} />
          <span>How it works</span>
        </button>
      ) : (
        <div style={{ width: '20px' }} />
      )}
    </div>
  );
};

