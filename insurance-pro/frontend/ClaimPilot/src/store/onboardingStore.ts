import { useState, useEffect } from 'react';

const ONBOARDING_COMPLETED_KEY = 'claimpilot_onboarding_completed';

interface OnboardingState {
  isOpen: boolean;
  currentStep: number;
  direction: 'forward' | 'backward';
  isCompleted: boolean;
}

// Keep the same key normalization as the existing onboardingStorage helper.
// This preserves completion flags written by the previous onboarding UI.
const normalizeIdentity = (identifier: string): string =>
  identifier.trim().toLowerCase().replace(/[^a-z0-9_@.-]/g, '_');

const getCompletionKey = (identifier: string): string =>
  `${ONBOARDING_COMPLETED_KEY}_${normalizeIdentity(identifier)}`;

class OnboardingStore {
  private state: OnboardingState = {
    isOpen: false,
    currentStep: 1,
    direction: 'forward',
    isCompleted: false,
  };
  private listeners: Set<(state: OnboardingState) => void> = new Set();
  private checkedAutoTriggerIdentities = new Set<string>();
  private activeUserId?: string;
  private activeEmail?: string;

  constructor() {
    if (typeof window !== 'undefined') {
      try {
        this.state.isCompleted = localStorage.getItem(ONBOARDING_COMPLETED_KEY) === 'true';
      } catch {
        // Storage may be unavailable in restricted browser contexts.
      }
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
   * Automatically opens tutorial if this is the user's first time.
   */
  checkAndTriggerFirstTime(userId?: string, email?: string) {
    if (typeof window === 'undefined') return;

    // Retain the active identity so completion can be persisted even if the
    // auth store keeps its user object in localStorage rather than sessionStorage.
    this.activeUserId = userId;
    this.activeEmail = email;

    const identity = normalizeIdentity(userId || email || 'anonymous');
    if (this.checkedAutoTriggerIdentities.has(identity)) return;
    this.checkedAutoTriggerIdentities.add(identity);

    let userCompleted = false;
    let emailCompleted = false;
    try {
      userCompleted = userId
        ? localStorage.getItem(getCompletionKey(userId)) === 'true'
        : false;
      emailCompleted = email
        ? localStorage.getItem(getCompletionKey(email)) === 'true'
        : false;
      const fallbackCompleted =
        !userId && !email && localStorage.getItem(ONBOARDING_COMPLETED_KEY) === 'true';

      if (!userCompleted && !emailCompleted && !fallbackCompleted) {
        // Delay slightly so dashboard entrance animations settle smoothly.
        setTimeout(() => {
          this.openOnboarding(1);
        }, 450);
      } else {
        this.update({ isCompleted: true });
      }
    } catch {
      // If storage is unavailable, still allow the tutorial to be shown.
      this.openOnboarding(1);
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

    try {
      const identities = new Set<string>();
      if (this.activeUserId) identities.add(this.activeUserId);
      if (this.activeEmail) identities.add(this.activeEmail);

      // Support either storage location so identity is recovered safely when
      // onboarding is opened manually before the auth effect has run.
      const storedUser = localStorage.getItem('auth_user') || sessionStorage.getItem('auth_user');
      if (storedUser) {
        try {
          const user = JSON.parse(storedUser);
          if (typeof user?.id === 'string' && user.id) identities.add(user.id);
          if (typeof user?.email === 'string' && user.email) identities.add(user.email);
        } catch {
          // Ignore malformed cached auth state; active identity may still exist.
        }
      }

      for (const identity of identities) {
        localStorage.setItem(getCompletionKey(identity), 'true');
      }
      // Keep the legacy global flag for compatibility with old consumers.
      localStorage.setItem(ONBOARDING_COMPLETED_KEY, 'true');
      this.update({ isCompleted: true });
    } catch {
      // Do not break the tutorial UI if browser storage is unavailable.
    }
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
