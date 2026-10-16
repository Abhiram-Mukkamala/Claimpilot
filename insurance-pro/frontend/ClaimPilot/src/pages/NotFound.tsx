import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../store/authStore';
import { Compass, ArrowLeft } from 'lucide-react';

export const NotFound: React.FC = () => {
  const { user } = useAuth();
  const homePath = user ? (user.role === 'agent' ? '/agent' : '/customer') : '/login';

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      backgroundColor: 'var(--bg-base)',
      color: 'var(--text-primary)',
      textAlign: 'center'
    }}>
      <div style={{
        maxWidth: '440px',
        width: '100%',
        padding: '3rem 2.5rem',
        backgroundColor: 'rgba(16, 16, 22, 0.4)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: '0 24px 64px -12px rgba(0, 0, 0, 0.6)'
      }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 1.5rem auto',
          color: 'var(--accent)'
        }}>
          <Compass size={28} />
        </div>

        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          fontWeight: 600,
          color: 'var(--accent)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase'
        }}>
          404 Error
        </span>

        <h1 style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          letterSpacing: '-0.03em',
          marginTop: '0.5rem',
          marginBottom: '0.75rem'
        }}>
          Page Not Found
        </h1>

        <p style={{
          fontSize: '0.875rem',
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
          marginBottom: '2rem'
        }}>
          The page or claim resource you are looking for does not exist or has been moved.
        </p>

        <Link
          to={homePath}
          className="btn btn-primary"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            width: '100%',
            padding: '0.75rem 1.25rem',
            fontWeight: 600,
            fontSize: '0.875rem',
            textDecoration: 'none'
          }}
        >
          <ArrowLeft size={16} />
          Return to {user ? 'Dashboard' : 'Sign In'}
        </Link>
      </div>
    </div>
  );
};
