import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';

// Register GSAP plugins
gsap.registerPlugin(useGSAP);

export { gsap, useGSAP };

/**
 * Checks if the user prefers reduced motion for accessibility
 */
export const isReducedMotion = (): boolean => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

/**
 * Common standard timings and easings for subtle, professional UI feel
 */
export const ANIM_DURATION = {
  fast: 0.22,
  normal: 0.35,
  gentle: 0.45,
};

export const ANIM_EASE = {
  out: 'power2.out',
  soft: 'power1.out',
};

/**
 * Subtly fades in an element or section with a gentle upward translation
 */
export const animateFadeIn = (
  target: gsap.TweenTarget,
  options?: { y?: number; duration?: number; delay?: number }
) => {
  if (isReducedMotion()) {
    return gsap.set(target, { opacity: 1, y: 0 });
  }

  return gsap.fromTo(
    target,
    { opacity: 0, y: options?.y ?? 10 },
    {
      opacity: 1,
      y: 0,
      duration: options?.duration ?? ANIM_DURATION.normal,
      delay: options?.delay ?? 0,
      ease: ANIM_EASE.out,
      clearProps: 'transform',
    }
  );
};

/**
 * Staggers a list or grid of cards/items with micro-offsets
 */
export const animateStagger = (
  targets: gsap.TweenTarget,
  options?: { stagger?: number; y?: number; duration?: number; delay?: number }
) => {
  if (isReducedMotion()) {
    return gsap.set(targets, { opacity: 1, y: 0 });
  }

  return gsap.fromTo(
    targets,
    { opacity: 0, y: options?.y ?? 12 },
    {
      opacity: 1,
      y: 0,
      duration: options?.duration ?? ANIM_DURATION.normal,
      stagger: options?.stagger ?? 0.05,
      delay: options?.delay ?? 0,
      ease: ANIM_EASE.out,
      clearProps: 'transform',
    }
  );
};

/**
 * Smooth step transition for multi-step wizards (e.g. NewClaim)
 */
export const animateStep = (
  target: gsap.TweenTarget,
  direction: 'forward' | 'backward' = 'forward'
) => {
  if (isReducedMotion()) {
    return gsap.set(target, { opacity: 1, x: 0 });
  }

  const startX = direction === 'forward' ? 14 : -14;
  return gsap.fromTo(
    target,
    { opacity: 0, x: startX },
    {
      opacity: 1,
      x: 0,
      duration: ANIM_DURATION.normal,
      ease: ANIM_EASE.out,
      clearProps: 'transform',
    }
  );
};
