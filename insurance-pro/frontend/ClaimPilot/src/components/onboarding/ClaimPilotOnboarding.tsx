import React, { useEffect, useRef } from 'react';
import { useOnboarding } from '../../store/onboardingStore';
import { ONBOARDING_STEPS } from './onboardingSteps';
import { OnboardingStep } from './OnboardingStep';
import { gsap, useGSAP, isReducedMotion } from '../../lib/gsap';
import { X, ArrowRight, ArrowLeft, Check, Sparkles } from 'lucide-react';
import './onboarding.css';

export const ClaimPilotOnboarding: React.FC = () => {
  const {
    isOpen,
    currentStep,
    direction,
    nextStep,
    prevStep,
    setStep,
    skipOnboarding,
    completeOnboarding,
  } = useOnboarding();

  const overlayRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const stepContainerRef = useRef<HTMLDivElement>(null);

  const stepData = ONBOARDING_STEPS.find((s) => s.id === currentStep) || ONBOARDING_STEPS[0];
  const isFinalStep = currentStep === ONBOARDING_STEPS.length;

  const skipOnboardingRef = useRef(skipOnboarding);
  skipOnboardingRef.current = skipOnboarding;

  // Keep keyboard focus within the dialog and prevent background scrolling.
  useEffect(() => {
    if (!isOpen) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    modalRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        skipOnboardingRef.current();
        return;
      }

      if (e.key !== 'Tab') return;
      const focusable = overlayRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable?.length) {
        e.preventDefault();
        modalRef.current?.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousBodyOverflow;
      previouslyFocused?.focus();
    };
  }, [isOpen]);

  // Entrance and exit animations for modal container
  useGSAP(
    () => {
      if (!isOpen || !overlayRef.current || !modalRef.current) return;

      if (isReducedMotion()) {
        gsap.set(overlayRef.current, { opacity: 1 });
        gsap.set(modalRef.current, { opacity: 1, scale: 1, y: 0 });
        return;
      }

      const tl = gsap.timeline();
      tl.fromTo(
        overlayRef.current,
        { opacity: 0 },
        { opacity: 1, duration: 0.3, ease: 'power2.out' }
      ).fromTo(
        modalRef.current,
        { opacity: 0, scale: 0.96, y: 16 },
        { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: 'power2.out' },
        '-=0.15'
      );
    },
    { dependencies: [isOpen] }
  );

  // Step transition animation (directional)
  useGSAP(
    () => {
      if (!stepContainerRef.current) return;

      if (isReducedMotion()) {
        gsap.set(stepContainerRef.current, { opacity: 1, x: 0 });
        return;
      }

      const startX = direction === 'forward' ? 24 : -24;

      gsap.fromTo(
        stepContainerRef.current,
        { opacity: 0, x: startX },
        { opacity: 1, x: 0, duration: 0.28, ease: 'power2.out', clearProps: 'transform' }
      );
    },
    { dependencies: [currentStep, direction] }
  );

  if (!isOpen) return null;

  return (
    <div
      ref={overlayRef}
      className="onboarding-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
      aria-describedby="onboarding-desc"
    >
      <div ref={modalRef} className="onboarding-modal" tabIndex={-1}>
        {/* Close Button */}
        <button
          onClick={skipOnboarding}
          className="onboarding-close-btn"
          aria-label="Close tutorial"
          title="Skip tutorial (Esc)"
        >
          <X size={16} />
        </button>

        {/* Header */}
        <div className="onboarding-header">
          <div className="onboarding-badge">
            <Sparkles size={12} />
            <span>{stepData.badge}</span>
          </div>
          <h2 id="onboarding-title" className="onboarding-title">
            {stepData.title}
          </h2>
          <p id="onboarding-desc" className="onboarding-desc">
            {stepData.description}
          </p>
        </div>

        {/* Interactive Step Body */}
        <div className="onboarding-body">
          <div ref={stepContainerRef} className="onboarding-step-container">
            <OnboardingStep step={currentStep} />
          </div>
        </div>

        {/* Footer Navigation */}
        <div className="onboarding-footer">
          {/* Left Controls: Back */}
          <div className="onboarding-nav-left">
            <button
              onClick={prevStep}
              disabled={currentStep === 1}
              className="btn-onboarding-back"
              aria-label="Previous step"
            >
              <ArrowLeft size={14} />
              <span>Back</span>
            </button>
          </div>

          {/* Center Controls: Progress Dots */}
          <div className="onboarding-nav-center" role="group" aria-label="Jump to tutorial step">
            {ONBOARDING_STEPS.map((s) => (
              <button
                key={s.id}
                onClick={() => setStep(s.id)}
                className={`onboarding-dot ${s.id === currentStep ? 'active' : ''}`}
                aria-label={`Jump to Step ${s.id}: ${s.title}`}
                aria-current={s.id === currentStep ? 'step' : undefined}
                title={`Step ${s.id}`}
              />
            ))}
          </div>

          {/* Right Controls: Skip / Next / Get Started */}
          <div className="onboarding-nav-right">
            {!isFinalStep ? (
              <>
                <button onClick={skipOnboarding} className="btn-onboarding-skip">
                  Skip
                </button>
                <button onClick={nextStep} className="btn-onboarding-next">
                  <span>Next</span>
                  <ArrowRight size={14} />
                </button>
              </>
            ) : (
              <button onClick={completeOnboarding} className="btn-onboarding-finish">
                <span>Get started</span>
                <Check size={16} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
