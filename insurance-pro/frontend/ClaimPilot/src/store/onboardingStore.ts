import { useState, useEffect } from 'react';

const ONBOARDING_COMPLETED_KEY = 'claimpilot_onboarding_completed';

interface OnboardingState {
  isOpen: boolean;
  currentStep: number;
  direction: 'forward' | 'backward';
  isCompleted: boolean;
}

class OnboardingStore {
  private state: OnboardingState = {
    isOpen: false,
    currentStep: 1,
    direction: 'forward',
    isCompleted: false,
  };
  private listeners: Set<(state: OnboardingState) => void> = new Set();
  private checkedAutoTriggerIdentities = new Set<string>();

  constructor() {
    if (typeof window !== 'undefined') {
      const completed = localStorage.getItem(ONBOARDING_COMPLETED_KEY) === 'true';
      this.state.isCompleted = completed;
    }
  }

  getState(): OnboardingState {
    return this.state;
  }

  private update(partial: Partial<OnboardingState>) {
    this.state = { ...this.state, ...partial };
    this.listeners.forEach((listener) => listener(this.state));
  }

  /**
   * Automatically opens tutorial if this is the user's first time
   */
  checkAndTriggerFirstTime(userId?: string, email?: string) {
    if (typeof window === 'undefined') return;
    const identity = userId || email || 'anonymous';
    if (this.checkedAutoTriggerIdentities.has(identity)) return;
    this.checkedAutoTriggerIdentities.add(identity);

    const userCompleted = userId
      ? localStorage.getItem(`${ONBOARDING_COMPLETED_KEY}_${userId}`) === 'true'
      : false;
    const emailCompleted = email
      ? localStorage.getItem(`${ONBOARDING_COMPLETED_KEY}_${email}`) === 'true'
      : false;
    const fallbackCompleted = !userId && !email && localStorage.getItem(ONBOARDING_COMPLETED_KEY) === 'true';

    if (!userCompleted && !emailCompleted && !fallbackCompleted) {
      // Delay slightly so dashboard entrance animations settle smoothly
      setTimeout(() => {
        this.openOnboarding(1);
      }, 450);
    } else {
      this.update({ isCompleted: true });
    }
  }

  openOnboarding(step = 1) {
    this.update({
      isOpen: true,
      currentStep: Math.max(1, Math.min(step, 6)),
      direction: 'forward',
    });
  }

  closeOnboarding() {
    this.update({ isOpen: false });
  }

  setStep(step: number) {
    const nextStep = Math.max(1, Math.min(step, 6));
    const direction = nextStep >= this.state.currentStep ? 'forward' : 'backward';
    this.update({ currentStep: nextStep, direction });
  }

  nextStep() {
    if (this.state.currentStep < 6) {
      this.setStep(this.state.currentStep + 1);
    } else {
      this.completeOnboarding();
    }
  }

  prevStep() {
    if (this.state.currentStep > 1) {
      this.setStep(this.state.currentStep - 1);
    }
  }

  skipOnboarding() {
    this.markAsCompleted();
    this.update({ isOpen: false });
  }

  completeOnboarding() {
    this.markAsCompleted();
    this.update({ isOpen: false, currentStep: 1 });
  }

  private markAsCompleted() {
    if (typeof window === 'undefined') return;
    localStorage.setItem(ONBOARDING_COMPLETED_KEY, 'true');

    // Also persist for any active session user
    try {
      const stored = sessionStorage.getItem('auth_user');
      if (stored) {
        const user = JSON.parse(stored);
        if (user?.id) localStorage.setItem(`${ONBOARDING_COMPLETED_KEY}_${user.id}`, 'true');
        if (user?.email) localStorage.setItem(`${ONBOARDING_COMPLETED_KEY}_${user.email}`, 'true');
      }
    } catch {
      // Ignore
    }

    this.update({ isCompleted: true });
  }

  subscribe(listener: (state: OnboardingState) => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}

export const onboardingStore = new OnboardingStore();

export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>(onboardingStore.getState());

  useEffect(() => {
    return onboardingStore.subscribe(setState);
  }, []);

  return {
    ...state,
    openOnboarding: (step?: number) => onboardingStore.openOnboarding(step),
    closeOnboarding: () => onboardingStore.closeOnboarding(),
    nextStep: () => onboardingStore.nextStep(),
    prevStep: () => onboardingStore.prevStep(),
    setStep: (step: number) => onboardingStore.setStep(step),
    skipOnboarding: () => onboardingStore.skipOnboarding(),
    completeOnboarding: () => onboardingStore.completeOnboarding(),
    checkAndTriggerFirstTime: (userId?: string, email?: string) =>
      onboardingStore.checkAndTriggerFirstTime(userId, email),
  };
}
