import React from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../store/authStore';
import { useTheme } from '../../store/themeStore';
import { LogOut } from 'lucide-react';
import '../../agent.css';

export const AgentLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const { } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', padding: '1rem' }}>
      <div className="agent-layout" style={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        borderRadius: 'var(--radius-xl)',
        overflow: 'hidden',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        background: 'rgba(14, 14, 20, 0.28)',
        backdropFilter: 'blur(5px) saturate(100%)',
        WebkitBackdropFilter: 'blur(5px) saturate(120%)',
        boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(0, 0, 0, 0)'
      }}>
        <header className="app-header">
          <div className="container flex items-center justify-between app-header-inner">
            {/* Wordmark */}
            <span className="app-wordmark">
              ClaimPilot
            </span>

            {/* Nav links */}
            <nav className="flex items-center gap-xl" style={{ height: '100%' }}>
              <NavLink
                to="/agent"
                end
                className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              >
                Dashboard
              </NavLink>
              <NavLink
                to="/agent/claims"
                className={({ isActive }) => `nav-link ${isActive || location.pathname.startsWith('/agent/claims') ? 'active' : ''}`}
              >
                All Claims
              </NavLink>
            </nav>

            {/* Right side */}
            <div className="flex items-center gap-md">
              <span className="text-sm text-muted">{user?.name}</span>

              <button
                onClick={handleLogout}
                className="btn-ghost"
                style={{ padding: '0.25rem' }}
                title="Sign out"
              >
                <LogOut size={15} />
              </button>
            </div>
          </div>
        </header>

        <main className="app-main">
          <div className="app-main-inner">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};


