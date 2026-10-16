export const GLOBAL_ONBOARDING_KEY = 'claimpilot_onboarding_completed';

const getStorageKey = (identifier?: string): string => {
  if (identifier && identifier.trim()) {
    const clean = identifier.toLowerCase().trim().replace(/[^a-z0-9_@.-]/g, '_');
    return `${GLOBAL_ONBOARDING_KEY}_${clean}`;
  }
  return GLOBAL_ONBOARDING_KEY;
};

/**
 * Check if a specific user (by email/id) or global session has already completed onboarding.
 */
export const hasCompletedOnboarding = (identifier?: string): boolean => {
  try {
    if (identifier && identifier.trim()) {
      const userKey = getStorageKey(identifier);
      const userCompleted = localStorage.getItem(userKey);
      // If user has an explicit record, respect it
      if (userCompleted !== null) {
        return userCompleted === 'true';
      }
      // New user accounts without a record must see onboarding
      return false;
    }
    return localStorage.getItem(GLOBAL_ONBOARDING_KEY) === 'true';
  } catch {
    return false;
  }
};

/**
 * Mark onboarding as completed for a specific user and global fallback.
 */
export const markOnboardingCompleted = (identifier?: string): void => {
  try {
    if (identifier && identifier.trim()) {
      const userKey = getStorageKey(identifier);
      localStorage.setItem(userKey, 'true');
    }
    localStorage.setItem(GLOBAL_ONBOARDING_KEY, 'true');
  } catch (e) {
    console.error('Failed to save onboarding completion state:', e);
  }
};

/**
 * Reset onboarding state for testing or manual triggers.
 */
export const resetOnboardingState = (identifier?: string): void => {
  try {
    if (identifier && identifier.trim()) {
      const userKey = getStorageKey(identifier);
      localStorage.removeItem(userKey);
    }
    localStorage.removeItem(GLOBAL_ONBOARDING_KEY);
  } catch (e) {
    console.error('Failed to reset onboarding state:', e);
  }
};
