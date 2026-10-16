export interface OnboardingStepData {
  id: number;
  badge: string;
  title: string;
  description: string;
}

export const ONBOARDING_STEPS: OnboardingStepData[] = [
  {
    id: 1,
    badge: 'Step 1 of 6 · Overview',
    title: 'Welcome to ClaimPilot',
    description: "Let's walk through how easy it is to file and track a claim.",
  },
  {
    id: 2,
    badge: 'Step 2 of 6 · Incident Info',
    title: 'Start a new claim',
    description: 'Choose the option to start a new claim and provide the basic details about your incident.',
  },
  {
    id: 3,
    badge: 'Step 3 of 6 · Evidence',
    title: 'Upload photos or video',
    description: 'Add clear photos or a video of the damaged area. ClaimPilot uses this media to help analyze the damage.',
  },
  {
    id: 4,
    badge: 'Step 4 of 6 · AI Vision',
    title: 'Review the detected damage',
    description: 'ClaimPilot analyzes the submitted media and presents the detected damage for review.',
  },
  {
    id: 5,
    badge: 'Step 5 of 6 · Final Review',
    title: 'Review and submit',
    description: 'Confirm your claim details and submit when everything looks correct.',
  },
  {
    id: 6,
    badge: 'Step 6 of 6 · Complete',
    title: 'Track everything in one place',
    description: 'Once submitted, you can monitor your claim status directly from your ClaimPilot dashboard.',
  },
];
