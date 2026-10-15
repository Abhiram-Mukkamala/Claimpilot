import React from 'react';
import { Link } from 'react-router-dom';
import { HelpCircle } from 'lucide-react';
import { useOnboarding } from '../../store/onboardingStore';

export const TopBar: React.FC = () => {
  const { openOnboarding } = useOnboarding();

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

      {/* Nav links — centred */}
      <nav style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
      }}>
        <Link to="/customer" className="topbar-nav-btn">
          Home
        </Link>
      </nav>

      {/* How it works — super right */}
      <button
        onClick={() => openOnboarding(1)}
        className="topbar-nav-btn"
        title="Interactive Claim Tutorial"
        style={{
          marginLeft: 'auto',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.35rem',
        }}
      >
        <HelpCircle size={15} />
        <span>How it works</span>
      </button>
    </div>
  );
};
