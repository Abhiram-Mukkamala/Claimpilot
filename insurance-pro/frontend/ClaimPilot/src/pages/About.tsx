import React, { useEffect, useRef } from 'react';

interface AboutProps {
  onReturn: () => void;
  isVisible: boolean;
  onSectionChange?: (sectionId: string) => void;
}

export const About: React.FC<AboutProps> = ({ onReturn, isVisible, onSectionChange }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Set up Intersection Observer for sections
  useEffect(() => {
    if (!isVisible) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            onSectionChange?.(entry.target.id);
          }
        });
      },
      {
        root: containerRef.current,
        threshold: 0.5,
      }
    );

    const sections = containerRef.current?.querySelectorAll('.about-section');
    sections?.forEach((section) => observer.observe(section));

    return () => observer.disconnect();
  }, [isVisible, onSectionChange]);

  return (
    <div
      ref={containerRef}
      className="about-page-container"
      style={{
        opacity: isVisible ? 1 : 0,
        pointerEvents: isVisible ? 'auto' : 'none',
      }}
    >
      <div id="hero" className="about-section">
        <h1 className="about-hero-title">ClaimPilot AI</h1>
        <p style={{ fontSize: '1.25rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
          The operations platform for the next generation of claims processing.
        </p>
      </div>

      <div id="problem" className="about-section">
        <h2 style={{ fontSize: '2.5rem', fontWeight: 600, marginBottom: '1rem' }}>The Problem</h2>
        <p style={{ fontSize: '1.125rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
          Traditional claims processing is slow, manual, and prone to error. Adjusters spend hours on data entry instead of resolving cases.
        </p>
      </div>

      <div id="solution" className="about-section">
        <h2 style={{ fontSize: '2.5rem', fontWeight: 600, marginBottom: '1rem' }}>How it Works</h2>
        <p style={{ fontSize: '1.125rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
          We use advanced AI to analyze damage, detect fraud, and automate the lifecycle of a claim, turning days into minutes.
        </p>
      </div>

      <div id="team" className="about-section">
        <h2 style={{ fontSize: '2.5rem', fontWeight: 600, marginBottom: '1rem' }}>Who are We</h2>
        <p style={{ fontSize: '1.125rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto', marginBottom: '3rem' }}>
          We are a team of insurance experts, AI researchers, and software engineers dedicated to transforming the insurance industry.
        </p>

        <div style={{ marginTop: '2rem' }}>
          <button
            onClick={onReturn}
            className="btn btn-primary"
            style={{ padding: '0.75rem 2rem', fontSize: '1rem', fontWeight: 600, borderRadius: 'var(--radius-md)' }}
          >
            SIGN IN
          </button>
        </div>
      </div>
    </div>
  );
};
