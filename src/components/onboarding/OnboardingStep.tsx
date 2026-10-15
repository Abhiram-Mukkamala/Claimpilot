import React from 'react';
import {
  FilePlus,
  Upload,
  ChevronRight,
  ShieldCheck,
  Check,
  Camera,
  Car
} from 'lucide-react';

interface OnboardingStepProps {
  step: number;
}

export const OnboardingStep: React.FC<OnboardingStepProps> = ({ step }) => {
  switch (step) {
    case 1:
      return (
        <div className="step1-dashboard-preview mock-stage-card">
          <div className="step1-top-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent)' }} />
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#FFFFFF' }}>ClaimPilot AI Hub</span>
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>LIVE DASHBOARD</span>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'rgba(240, 240, 245, 0.7)', margin: '0' }}>
            Choose an incident type or check active claims right from your home screen.
          </p>

          <div className="step1-grid">
            <div className="step1-type-card">
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#FFFFFF' }}>Collision</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Accident damage</span>
            </div>
            <div className="step1-type-card">
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#FFFFFF' }}>Fire</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Vehicle fire</span>
            </div>
            <div className="step1-type-card">
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#FFFFFF' }}>Natural Event</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Flood, hail, storm</span>
            </div>
          </div>
        </div>
      );

    case 2:
      return (
        <div className="step2-spotlight-wrapper mock-stage-card">
          {/* Highlighted File New Claim Button */}
          <div className="step2-spotlight-target">
            <span className="step2-spotlight-badge">START HERE</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
              <div style={{ background: 'rgba(5, 150, 105, 0.2)', padding: '0.65rem', borderRadius: '50%', color: 'var(--accent)' }}>
                <FilePlus size={20} />
              </div>
              <div>
                <p style={{ margin: '0', fontSize: '0.95rem', fontWeight: 600, color: '#FFFFFF' }}>File a New Claim</p>
                <p style={{ margin: '0', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Start a new incident report in 4 simple steps</p>
              </div>
            </div>
            <ChevronRight size={18} color="var(--accent)" />
          </div>

          {/* Quick Mock Details Input */}
          <div className="step2-fields-mock">
            <div className="step2-field-box">
              <span style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.2rem' }}>Vehicle Model</span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 500, color: '#FFFFFF' }}>2023 Hyundai Verna</span>
            </div>
            <div className="step2-field-box">
              <span style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.2rem' }}>HSRP Number</span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 500, color: '#FFFFFF', fontFamily: 'var(--font-mono)' }}>MH12AB1234</span>
            </div>
          </div>
        </div>
      );

    case 3:
      return (
        <div className="mock-stage-card">
          <div className="step3-upload-zone">
            <div style={{ background: 'rgba(255, 255, 255, 0.06)', padding: '0.75rem', borderRadius: '50%', color: 'var(--accent)' }}>
              <Upload size={22} />
            </div>
            <p style={{ fontSize: '0.875rem', fontWeight: 600, color: '#FFFFFF', margin: '0' }}>Drop damage photos or click to browse</p>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0' }}>Upload up to 10 photos and 2 walkaround videos (JPG, PNG, MP4)</p>

            <div className="step3-progress-bar">
              <div className="step3-progress-fill" />
            </div>
          </div>

          <div className="step3-thumbnails">
            <div className="step3-thumb">
              <Camera size={16} color="var(--text-secondary)" />
              <div className="step3-thumb-check"><Check size={12} /></div>
            </div>
            <div className="step3-thumb">
              <Camera size={16} color="var(--text-secondary)" />
              <div className="step3-thumb-check"><Check size={12} /></div>
            </div>
            <div className="step3-thumb">
              <Camera size={16} color="var(--text-secondary)" />
              <div className="step3-thumb-check"><Check size={12} /></div>
            </div>
          </div>
        </div>
      );

    case 4:
      return (
        <div className="step4-analysis-layout mock-stage-card">
          {/* Simulated 2D/3D Viewer with Damage Hotspots */}
          <div className="step4-viewer-mock">
            <Car size={56} color="rgba(255, 255, 255, 0.25)" />
            <div className="step4-damage-marker" style={{ top: '35%', left: '30%' }} title="Front Bumper Dent">
              1
            </div>
            <div className="step4-damage-marker" style={{ top: '48%', right: '28%' }} title="Fender Crease">
              2
            </div>
            <span style={{
              position: 'absolute',
              bottom: '8px',
              left: '12px',
              fontSize: '0.6875rem',
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)'
            }}>
              AI DETECTION OVERLAY
            </span>
          </div>

          {/* Detections List */}
          <div className="step4-detections-list">
            <div className="step4-detection-item">
              <div>
                <p style={{ margin: '0', fontSize: '0.8125rem', fontWeight: 600, color: '#FFFFFF' }}>01 Front Bumper Dent</p>
                <p style={{ margin: '0', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Area: 142 cm² · Depth: 1.8 cm</p>
              </div>
              <span style={{ fontSize: '0.7rem', color: '#F87171', background: 'rgba(248, 113, 113, 0.12)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
                Moderate
              </span>
            </div>

            <div className="step4-detection-item">
              <div>
                <p style={{ margin: '0', fontSize: '0.8125rem', fontWeight: 600, color: '#FFFFFF' }}>02 Left Fender Crease</p>
                <p style={{ margin: '0', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Surface scratch · Light paint repair</p>
              </div>
              <span style={{ fontSize: '0.7rem', color: '#FBBF24', background: 'rgba(251, 191, 36, 0.12)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
                Minor
              </span>
            </div>
          </div>
        </div>
      );

    case 5:
      return (
        <div className="step5-submit-card mock-stage-card">
          <div className="step5-summary-row">
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Vehicle</span>
            <span style={{ fontSize: '0.8125rem', fontWeight: 500, color: '#FFFFFF' }}>2023 Hyundai Verna (MH12AB1234)</span>
          </div>
          <div className="step5-summary-row">
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Damage Evidence</span>
            <span style={{ fontSize: '0.8125rem', fontWeight: 500, color: '#FFFFFF' }}>3 Photos · 1 Video Walkaround</span>
          </div>
          <div className="step5-summary-row">
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>AI Verification</span>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--accent)' }}>Passed · 2 Visible Areas Tagged</span>
          </div>

          <div className="step5-cta-highlight">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <ShieldCheck size={20} color="var(--accent)" />
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#FFFFFF' }}>Ready to submit for assessment</span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>INSTANT LOG</span>
          </div>
        </div>
      );

    case 6:
      return (
        <div className="step6-track-card mock-stage-card">
          {/* Progress Timeline */}
          <div className="step6-timeline">
            <div className="step6-timeline-line" />
            <div className="step6-timeline-node">
              <div className="step6-timeline-dot" />
              <span style={{ fontSize: '0.6875rem', color: '#FFFFFF', fontWeight: 600 }}>Submitted</span>
            </div>
            <div className="step6-timeline-node">
              <div className="step6-timeline-dot" />
              <span style={{ fontSize: '0.6875rem', color: '#FFFFFF', fontWeight: 600 }}>AI Assessment</span>
            </div>
            <div className="step6-timeline-node">
              <div className="step6-timeline-dot" style={{ background: '#FBBF24' }} />
              <span style={{ fontSize: '0.6875rem', color: '#FBBF24', fontWeight: 600 }}>Review</span>
            </div>
            <div className="step6-timeline-node">
              <div className="step6-timeline-dot" style={{ background: 'rgba(255, 255, 255, 0.2)', boxShadow: 'none' }} />
              <span style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)' }}>Approved</span>
            </div>
          </div>

          <div className="step6-celebrate-box">
            <p style={{ margin: '0 0 0.25rem 0', fontSize: '1.1rem', fontWeight: 700, color: '#FFFFFF' }}>
              You're all set 🎉
            </p>
            <p style={{ margin: '0', fontSize: '0.85rem', color: 'rgba(220, 220, 235, 0.8)' }}>
              You're ready to file your first claim with ClaimPilot. Monitor real-time status and 3D spatial damage anytime from your dashboard.
            </p>
          </div>
        </div>
      );

    default:
      return null;
  }
};
