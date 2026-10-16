export interface OnboardingStepItem {
  step: number;
  id: string;
  tag: string;
  title: string;
  description: string;
  nextButtonText?: string;
}

export const ONBOARDING_STEPS: OnboardingStepItem[] = [
  {
    step: 1,
    id: 'welcome',
    tag: 'Welcome',
    title: 'Welcome to ClaimPilot',
    description: "Let's walk through how easy it is to file and track a claim.",
    nextButtonText: 'Next →'
  },
  {
    step: 2,
    id: 'start-claim',
    tag: 'Step 1 of 5',
    title: 'Start a new claim',
    description: 'Choose the option to start a new claim and provide the basic details about your incident.',
    nextButtonText: 'Next →'
  },
  {
    step: 3,
    id: 'upload-damage',
    tag: 'Step 2 of 5',
    title: 'Upload photos or video',
    description: 'Add clear photos or a video of the damaged area. ClaimPilot uses this media to help analyze the damage.',
    nextButtonText: 'Next →'
  },
  {
    step: 4,
    id: 'review-damage',
    tag: 'Step 3 of 5',
    title: 'Review the detected damage',
    description: 'ClaimPilot analyzes the submitted media and presents the detected damage for review.',
    nextButtonText: 'Next →'
  },
  {
    step: 5,
    id: 'submit-claim',
    tag: 'Step 4 of 5',
    title: 'Review and submit',
    description: 'Confirm your claim details and submit when everything looks correct.',
    nextButtonText: 'Next →'
  },
  {
    step: 6,
    id: 'track-claim',
    tag: 'Step 5 of 5',
    title: 'Track everything in one place',
    description: 'Once submitted, you can monitor your claim status directly from your ClaimPilot dashboard.',
    nextButtonText: 'Get started'
  }
];
