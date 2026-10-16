import React, { useRef } from 'react';
import { 
  Plus, 
  Car, 
  Flame, 
  CloudLightning, 
  ShieldAlert, 
  CheckCircle2, 
  Clock, 
  Check, 
  Sparkles, 
  ArrowRight,
  Camera
} from 'lucide-react';
import { useGSAP, gsap, isReducedMotion } from '../../lib/gsap';

interface OnboardingStepVisualProps {
  step: number;
}

export const OnboardingStepVisual: React.FC<OnboardingStepVisualProps> = ({ step }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (!containerRef.current) return;
    const reduced = isReducedMotion();

    // Clean up any lingering animations
    gsap.killTweensOf(containerRef.current.querySelectorAll('*'));

    if (reduced) {
      gsap.set(containerRef.current.querySelectorAll('.anim-element'), { opacity: 1, y: 0, scale: 1 });
      return;
    }

    if (step === 1) {
      // Step 1: Dashboard cards entrance
      gsap.fromTo(
        containerRef.current.querySelectorAll('.anim-element'),
        { opacity: 0, y: 14, scale: 0.98 },
        { opacity: 1, y: 0, scale: 1, duration: 0.45, stagger: 0.08, ease: 'power2.out' }
      );
    } else if (step === 2) {
      // Step 2: Spotlight pulse & category cards
      gsap.fromTo(
        containerRef.current.querySelectorAll('.anim-element'),
        { opacity: 0, y: 12 },
        { opacity: 1, y: 0, duration: 0.4, stagger: 0.07, ease: 'power2.out' }
      );

      gsap.fromTo(
        containerRef.current.querySelector('.spotlight-ring'),
        { scale: 0.96, opacity: 0.4 },
        { scale: 1.03, opacity: 0.9, duration: 1.6, repeat: -1, yoyo: true, ease: 'sine.inOut' }
      );
    } else if (step === 3) {
      // Step 3: Simulated upload progress and media thumbs
      const progressBar = containerRef.current.querySelector('.mock-progress-fill');
      const thumbs = containerRef.current.querySelectorAll('.mock-thumb');

      if (progressBar) {
        gsap.fromTo(
          progressBar,
          { width: '0%' },
          { width: '100%', duration: 1.2, ease: 'power2.out', delay: 0.1 }
        );
      }

      if (thumbs.length > 0) {
        gsap.fromTo(
          thumbs,
          { opacity: 0, y: 10, scale: 0.92 },
          { opacity: 1, y: 0, scale: 1, duration: 0.4, stagger: 0.15, delay: 0.4, ease: 'back.out(1.4)' }
        );
      }
    } else if (step === 4) {
      // Step 4: Damage detection markers popping in sequence
      const markers = containerRef.current.querySelectorAll('.damage-marker-pin');
      const cards = containerRef.current.querySelectorAll('.detection-item-card');

      gsap.fromTo(
        markers,
        { scale: 0, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.4, stagger: 0.18, ease: 'back.out(2)' }
      );

      gsap.fromTo(
        cards,
        { opacity: 0, x: 12 },
        { opacity: 1, x: 0, duration: 0.35, stagger: 0.12, delay: 0.2, ease: 'power2.out' }
      );
    } else if (step === 5) {
      // Step 5: Summary card fields and submit button pulse
      const rows = containerRef.current.querySelectorAll('.summary-row-item');
      const submitBtn = containerRef.current.querySelector('.mock-submit-btn');

      gsap.fromTo(
        rows,
        { opacity: 0, y: 8 },
        { opacity: 1, y: 0, duration: 0.35, stagger: 0.06, ease: 'power2.out' }
      );

      if (submitBtn) {
        gsap.fromTo(
          submitBtn,
          { scale: 0.97, opacity: 0 },
          { scale: 1, opacity: 1, duration: 0.4, delay: 0.3, ease: 'back.out(1.2)' }
        );
      }
    } else if (step === 6) {
      // Step 6: Status timeline progression & celebration
      const timelineNodes = containerRef.current.querySelectorAll('.timeline-node-item');
      const celebration = containerRef.current.querySelector('.celebration-badge');

      gsap.fromTo(
        timelineNodes,
        { opacity: 0, scale: 0.9 },
        { opacity: 1, scale: 1, duration: 0.35, stagger: 0.1, ease: 'power2.out' }
      );

      if (celebration) {
        gsap.fromTo(
          celebration,
          { opacity: 0, y: 12, scale: 0.95 },
          { opacity: 1, y: 0, scale: 1, duration: 0.5, delay: 0.35, ease: 'back.out(1.5)' }
        );
      }
    }
  }, { scope: containerRef, dependencies: [step] });

  return (
    <div ref={containerRef} className="onboarding-visual-stage">
      {/* STEP 1: DASHBOARD OVERVIEW */}
      {step === 1 && (
        <div className="onboarding-step-content-grid">
          <div className="onboarding-mock-window anim-element">
            <div className="mock-window-header">
              <div className="mock-window-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="mock-window-title">ClaimPilot Portal Preview</span>
            </div>

            <div className="mock-window-body">
              <div className="mock-dash-topbar anim-element">
                <div className="flex items-center gap-2">
                  <div className="mock-logo-pill">
                    <Sparkles size={13} className="text-emerald-400" />
                    <span>ClaimPilot AI</span>
                  </div>
                  <span className="mock-badge-subtle">Online Engine</span>
                </div>
                <div className="mock-user-avatar">AK</div>
              </div>

              <div className="mock-dash-grid">
                <div className="mock-dash-card active-card anim-element">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold text-emerald-400">AI Instant Intake</span>
                    <span className="mock-chip">Active</span>
                  </div>
                  <p className="text-sm font-bold text-white mb-1">Upload & Analyze in Seconds</p>
                  <p className="text-xs text-slate-400">Computer-vision driven damage assessment with high accuracy segmentation.</p>
                </div>

                <div className="mock-dash-card anim-element">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold text-slate-300">Live Claim Tracking</span>
                    <Clock size={14} className="text-slate-400" />
                  </div>
                  <p className="text-sm font-bold text-white mb-1">Real-time Surveyor Review</p>
                  <p className="text-xs text-slate-400">Transparent timeline tracking every step from inspection to payout.</p>
                </div>
              </div>

              <div className="mock-feature-pill anim-element">
                <ShieldAlert size={15} className="text-emerald-400" />
                <span>Zero guesswork • Instant damage detection • Complete 3D analysis</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: START A NEW CLAIM */}
      {step === 2 && (
        <div className="onboarding-step-content-grid">
          <div className="onboarding-mock-window">
            <div className="mock-window-header">
              <div className="mock-window-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="mock-window-title">Step 1 • Claim Initiation</span>
            </div>

            <div className="mock-window-body">
              {/* Spotlight Wrapper */}
              <div className="spotlight-container">
                <div className="spotlight-ring" />
                <div className="mock-spotlight-cta anim-element">
                  <div className="flex items-center gap-3">
                    <div className="mock-cta-icon-box">
                      <Plus size={20} className="text-emerald-400" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">File a New Claim</p>
                      <p className="text-xs text-slate-400">Quick start with vehicle & incident details</p>
                    </div>
                  </div>
                  <div className="mock-spotlight-badge">
                    <span>Click to Start</span>
                    <ArrowRight size={13} />
                  </div>
                </div>
              </div>

              <div className="mock-section-divider anim-element">
                <span>Select Incident Category</span>
              </div>

              <div className="mock-category-row">
                <div className="mock-category-card selected anim-element">
                  <Car size={18} className="text-emerald-400 mb-1" />
                  <span className="text-xs font-bold text-white">Collision</span>
                  <span className="text-[10px] text-slate-400">Accident damage</span>
                </div>
                <div className="mock-category-card anim-element">
                  <Flame size={18} className="text-amber-400 mb-1" />
                  <span className="text-xs font-bold text-white">Fire</span>
                  <span className="text-[10px] text-slate-400">Vehicle fire</span>
                </div>
                <div className="mock-category-card anim-element">
                  <CloudLightning size={18} className="text-sky-400 mb-1" />
                  <span className="text-xs font-bold text-white">Natural Event</span>
                  <span className="text-[10px] text-slate-400">Flood / Monsoon</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: UPLOAD MEDIA */}
      {step === 3 && (
        <div className="onboarding-step-content-grid">
          <div className="onboarding-mock-window">
            <div className="mock-window-header">
              <div className="mock-window-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="mock-window-title">Step 2 • Multi-Angle Evidence Upload</span>
            </div>

            <div className="mock-window-body">
              <div className="mock-upload-dropzone anim-element">
                <div className="mock-upload-icon-pulse">
                  <Camera size={22} className="text-emerald-400" />
                </div>
                <p className="text-sm font-bold text-white mb-1">Photos & 360° Video Walkthrough</p>
                <p className="text-xs text-slate-400 mb-3">Drag & drop damage evidence or capture with mobile</p>

                {/* Progress bar */}
                <div className="mock-progress-track">
                  <div className="mock-progress-fill" />
                </div>
                <div className="flex justify-between items-center text-[11px] text-slate-400 mt-1">
                  <span>Uploading files (3/3)...</span>
                  <span className="text-emerald-400 font-semibold">100% Ready</span>
                </div>
              </div>

              <div className="mock-thumbs-grid">
                <div className="mock-thumb anim-element">
                  <div className="mock-thumb-img bumper-preview" />
                  <div className="mock-thumb-info">
                    <span className="mock-thumb-name">Front_Bumper.jpg</span>
                    <span className="mock-thumb-status">✓ Validated</span>
                  </div>
                </div>

                <div className="mock-thumb anim-element">
                  <div className="mock-thumb-img fender-preview" />
                  <div className="mock-thumb-info">
                    <span className="mock-thumb-name">Left_Fender.jpg</span>
                    <span className="mock-thumb-status">✓ Validated</span>
                  </div>
                </div>

                <div className="mock-thumb anim-element">
                  <div className="mock-thumb-img video-preview">
                    <span className="video-badge">360° MP4</span>
                  </div>
                  <div className="mock-thumb-info">
                    <span className="mock-thumb-name">360_Walkaround.mp4</span>
                    <span className="mock-thumb-status">✓ 1080p HD</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 4: DAMAGE DETECTION */}
      {step === 4 && (
        <div className="onboarding-step-content-grid">
          <div className="onboarding-mock-window">
            <div className="mock-window-header">
              <div className="mock-window-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="mock-window-title">Step 3 • AI Computer Vision Analysis</span>
            </div>

            <div className="mock-window-body">
              <div className="mock-analysis-container">
                {/* Visual car analysis canvas */}
                <div className="mock-car-viewer">
                  <div className="mock-car-overlay-bg" />

                  {/* Marker 1 */}
                  <div className="damage-marker-pin pin-1" style={{ top: '38%', left: '32%' }}>
                    <span className="pin-number">1</span>
                    <div className="pin-pulse" />
                    <div className="pin-tooltip">
                      <strong>Front Bumper</strong>
                      <span>Est. ₹14,500 - ₹18,000 • 94% conf.</span>
                    </div>
                  </div>

                  {/* Marker 2 */}
                  <div className="damage-marker-pin pin-2" style={{ top: '32%', left: '68%' }}>
                    <span className="pin-number">2</span>
                    <div className="pin-pulse" />
                    <div className="pin-tooltip">
                      <strong>Left Headlamp</strong>
                      <span>Est. ₹6,500 - ₹8,500 • 89% conf.</span>
                    </div>
                  </div>

                  <div className="ai-watermark-pill">
                    <ShieldAlert size={13} className="text-emerald-400" />
                    <span>AI Damage Segmentation Engine</span>
                  </div>
                </div>

                {/* Detected parts list */}
                <div className="mock-detection-list">
                  <div className="detection-item-card anim-element">
                    <div className="flex items-center gap-2">
                      <span className="detection-badge-num">1</span>
                      <div>
                        <p className="text-xs font-bold text-white">Front Bumper</p>
                        <p className="text-[10px] text-slate-400">Deformation • Est. ₹14,500 - ₹18,000</p>
                      </div>
                    </div>
                    <span className="detection-score">94%</span>
                  </div>

                  <div className="detection-item-card anim-element">
                    <div className="flex items-center gap-2">
                      <span className="detection-badge-num">2</span>
                      <div>
                        <p className="text-xs font-bold text-white">Left Headlight</p>
                        <p className="text-[10px] text-slate-400">Lens Crack • Est. ₹6,500 - ₹8,500</p>
                      </div>
                    </div>
                    <span className="detection-score">89%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 5: REVIEW & SUBMIT */}
      {step === 5 && (
        <div className="onboarding-step-content-grid">
          <div className="onboarding-mock-window">
            <div className="mock-window-header">
              <div className="mock-window-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="mock-window-title">Step 4 • Review & Pre-assessment</span>
            </div>

            <div className="mock-window-body">
              <div className="mock-summary-card">
                <div className="summary-header">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Claim Summary</span>
                  <span className="mock-chip-green">Ready to Dispatch</span>
                </div>

                <div className="summary-details">
                  <div className="summary-row-item">
                    <span className="text-xs text-slate-400">Vehicle (HSRP)</span>
                    <span className="text-xs font-semibold text-white">2024 Tata Nexon EV (MH 12 AB 1234)</span>
                  </div>
                  <div className="summary-row-item">
                    <span className="text-xs text-slate-400">Policy Number</span>
                    <span className="text-xs font-semibold text-white">CP-IN-884920</span>
                  </div>
                  <div className="summary-row-item">
                    <span className="text-xs text-slate-400">Estimated Repair Cost</span>
                    <span className="text-xs font-bold text-emerald-400">₹21,000 - ₹26,500</span>
                  </div>
                  <div className="summary-row-item">
                    <span className="text-xs text-slate-400">Automated Fraud & DL Check</span>
                    <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                      <Check size={12} /> Low Risk (4/4 Passed)
                    </span>
                  </div>
                </div>

                <div className="mock-submit-action">
                  <div className="mock-submit-btn">
                    <Sparkles size={15} />
                    <span>Submit Claim to Surveyor</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 6: TRACK STATUS */}
      {step === 6 && (
        <div className="onboarding-step-content-grid">
          <div className="onboarding-mock-window">
            <div className="mock-window-header">
              <div className="mock-window-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <span className="mock-window-title">Step 5 • Real-time Claim Tracking</span>
            </div>

            <div className="mock-window-body">
              {/* Claim Card Status */}
              <div className="mock-active-claim-box anim-element">
                <div className="flex justify-between items-center mb-3">
                  <div>
                    <span className="text-xs text-slate-400 font-mono">#CLM-IN-2026-8891</span>
                    <p className="text-sm font-bold text-white">Tata Nexon EV • Collision</p>
                  </div>
                  <span className="mock-chip-green flex items-center gap-1">
                    <CheckCircle2 size={12} /> In Progress
                  </span>
                </div>

                {/* Progress Timeline */}
                <div className="mock-timeline-wrapper">
                  <div className="mock-timeline-line" />
                  <div className="mock-timeline-nodes">
                    <div className="timeline-node-item active">
                      <div className="node-circle done">✓</div>
                      <span className="node-label">Submitted</span>
                    </div>
                    <div className="timeline-node-item active">
                      <div className="node-circle done">✓</div>
                      <span className="node-label">AI Analysis</span>
                    </div>
                    <div className="timeline-node-item current">
                      <div className="node-circle pulse">3</div>
                      <span className="node-label">Surveyor Review</span>
                    </div>
                    <div className="timeline-node-item">
                      <div className="node-circle">4</div>
                      <span className="node-label">Settlement</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Celebration Callout */}
              <div className="celebration-badge">
                <div className="celebration-icon-box">🎉</div>
                <div>
                  <h4 className="text-sm font-bold text-white">You're all set!</h4>
                  <p className="text-xs text-slate-300">You're ready to file your first claim with ClaimPilot.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
