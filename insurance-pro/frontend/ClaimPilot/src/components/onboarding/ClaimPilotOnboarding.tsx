import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, ArrowRight, ArrowLeft, Sparkles } from 'lucide-react';
import { ONBOARDING_STEPS } from './onboardingSteps';
import { OnboardingStepVisual } from './OnboardingStepVisual';
import { useGSAP, gsap, isReducedMotion } from '../../lib/gsap';
import './onboarding.css';

interface ClaimPilotOnboardingProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ClaimPilotOnboarding: React.FC<ClaimPilotOnboardingProps> = ({
  isOpen,
  onClose,
}) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const directionRef = useRef<'forward' | 'backward'>('forward');

  const overlayRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const stepContainerRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const descRef = useRef<HTMLParagraphElement>(null);

  const stepData = ONBOARDING_STEPS[currentStepIndex] || ONBOARDING_STEPS[0];
  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === ONBOARDING_STEPS.length - 1;

  // Reset to first step whenever reopened
  useEffect(() => {
    if (isOpen) {
      setCurrentStepIndex(0);
      setIsTransitioning(false);
    }
  }, [isOpen]);

  // Entrance animation when modal opens
  useGSAP(() => {
    if (!isOpen || !overlayRef.current || !dialogRef.current) return;

    if (isReducedMotion()) {
      gsap.set(overlayRef.current, { opacity: 1 });
      gsap.set(dialogRef.current, { opacity: 1, scale: 1, y: 0 });
      return;
    }

    const tl = gsap.timeline();
    tl.fromTo(
      overlayRef.current,
      { opacity: 0 },
      { opacity: 1, duration: 0.28, ease: 'power2.out' }
    );
    tl.fromTo(
      dialogRef.current,
      { opacity: 0, scale: 0.95, y: 16 },
      { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: 'power2.out' },
      '-=0.15'
    );
  }, { dependencies: [isOpen] });

  // Step transition animation handler
  const transitionToStep = useCallback((targetIndex: number) => {
    if (targetIndex === currentStepIndex || isTransitioning) return;
    if (targetIndex < 0 || targetIndex >= ONBOARDING_STEPS.length) return;

    const direction = targetIndex > currentStepIndex ? 'forward' : 'backward';
    directionRef.current = direction;

    if (isReducedMotion() || !stepContainerRef.current) {
      setCurrentStepIndex(targetIndex);
      return;
    }

    setIsTransitioning(true);
    const container = stepContainerRef.current;
    const exitX = direction === 'forward' ? -24 : 24;
    const enterX = direction === 'forward' ? 24 : -24;

    const tl = gsap.timeline({
      onComplete: () => {
        setIsTransitioning(false);
      },
    });

    // Animate out current step content
    tl.to(container, {
      opacity: 0,
      x: exitX,
      duration: 0.2,
      ease: 'power2.in',
      onComplete: () => {
        setCurrentStepIndex(targetIndex);
        gsap.set(container, { x: enterX, opacity: 0 });
      },
    });

    // Animate in new step content
    tl.to(container, {
      opacity: 1,
      x: 0,
      duration: 0.28,
      ease: 'power2.out',
      clearProps: 'transform',
    });
  }, [currentStepIndex, isTransitioning]);

  const handleNext = () => {
    if (isLastStep) {
      handleComplete();
    } else {
      transitionToStep(currentStepIndex + 1);
    }
  };

  const handleBack = () => {
    if (!isFirstStep) {
      transitionToStep(currentStepIndex - 1);
    }
  };

  const handleSkip = () => {
    handleCloseModal();
  };

  const handleComplete = () => {
    handleCloseModal();
  };

  const handleCloseModal = () => {
    if (isReducedMotion() || !overlayRef.current || !dialogRef.current) {
      onClose();
      return;
    }

    const tl = gsap.timeline({
      onComplete: onClose,
    });
    tl.to(dialogRef.current, {
      opacity: 0,
      scale: 0.96,
      y: 12,
      duration: 0.22,
      ease: 'power2.in',
    });
    tl.to(
      overlayRef.current,
      { opacity: 0, duration: 0.18, ease: 'power2.in' },
      '-=0.1'
    );
  };

  // Keyboard navigation & accessibility
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseModal();
      } else if (e.key === 'ArrowRight' && !isLastStep) {
        e.preventDefault();
        transitionToStep(currentStepIndex + 1);
      } else if (e.key === 'ArrowLeft' && !isFirstStep) {
        e.preventDefault();
        transitionToStep(currentStepIndex - 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentStepIndex, isLastStep, isFirstStep, transitionToStep]);

  if (!isOpen) return null;

  return (
    <div
      ref={overlayRef}
      className="onboarding-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-step-title"
      aria-describedby="onboarding-step-desc"
    >
      <div ref={dialogRef} className="onboarding-dialog" tabIndex={-1}>
        {/* Close Button */}
        <button
          onClick={handleCloseModal}
          className="onboarding-close-btn"
          title="Close tutorial (Esc)"
          aria-label="Close tutorial"
        >
          <X size={16} />
        </button>

        {/* Step Header */}
        <div className="onboarding-header">
          <div className="onboarding-header-meta">
            <span className="onboarding-step-badge">
              <Sparkles size={12} />
              {stepData.tag}
            </span>
          </div>

          <h2 id="onboarding-step-title" ref={titleRef} className="onboarding-title">
            {stepData.title}
          </h2>

          <p id="onboarding-step-desc" ref={descRef} className="onboarding-desc">
            {stepData.description}
          </p>
        </div>

        {/* Visual Stage Box */}
        <div className="onboarding-stage-wrapper">
          <div ref={stepContainerRef} className="onboarding-step-slider-container">
            <OnboardingStepVisual step={stepData.step} />
          </div>
        </div>

        {/* Navigation & Progress Footer */}
        <div className="onboarding-footer">
          {/* Dot Progress Indicators */}
          <div className="onboarding-progress-dots" role="tablist" aria-label="Tutorial steps">
            {ONBOARDING_STEPS.map((s, idx) => (
              <button
                key={s.id}
                onClick={() => transitionToStep(idx)}
                className={`onboarding-dot ${idx === currentStepIndex ? 'active' : ''}`}
                title={`Go to step ${idx + 1}: ${s.title}`}
                aria-label={`Step ${idx + 1} of ${ONBOARDING_STEPS.length}`}
                aria-selected={idx === currentStepIndex}
                role="tab"
              />
            ))}
          </div>

          {/* Action Buttons */}
          <div className="onboarding-nav-group">
            {!isFirstStep && (
              <button
                onClick={handleBack}
                className="onboarding-btn-back"
                aria-label="Previous step"
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <ArrowLeft size={14} /> Back
                </span>
              </button>
            )}

            {!isLastStep ? (
              <>
                <button
                  onClick={handleSkip}
                  className="onboarding-btn-skip"
                  aria-label="Skip onboarding tutorial"
                >
                  Skip
                </button>
                <button
                  onClick={handleNext}
                  className="onboarding-btn-next"
                  aria-label="Next step"
                >
                  <span>{stepData.nextButtonText || 'Next →'}</span>
                </button>
              </>
            ) : (
              <button
                onClick={handleComplete}
                className="onboarding-btn-get-started"
                aria-label="Complete tutorial and get started"
              >
                <span>Get started</span>
                <ArrowRight size={15} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
