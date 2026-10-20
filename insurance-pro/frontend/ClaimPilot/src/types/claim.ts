export type ClaimStatus =
  | 'Pending Review'
  | 'Under Review'
  | 'AI Assessment'
  | 'Agent Review'
  | 'Decision Pending'
  | 'Approved'
  | 'Flagged'
  | 'Rejected'
  | 'Action Required'
  | 'Settlement Accepted'
  | 'Disputed';

export interface ClaimEvidenceItem {
  id?: string;
  claim_id?: string;
  file_url: string;
  file_type?: string;
  category: 'photo' | 'damage_photo' | 'video' | 'walkaround_video' | 'dl_front' | 'dl_back' | 'document' | string;
  created_at?: string;
  metadata?: Record<string, any>;
  storage_path?: string;
}

export interface Claim {
  id: string;
  backendId?: string;
  customerId: string;
  customerName: string;
  policyNumber: string;
  customerPhone: string;
  vehicle: string;
  claimType: string;
  incidentDate: string;
  location: string;
  description: string;
  engineNumber?: string;
  chassisNumber?: string;
  hsrpNumber?: string;
  driverName?: string;
  driverLicenseNumber?: string;
  driverLicenseFrontPhoto?: string;
  driverLicenseBackPhoto?: string;
  submittedAt: string;
  status: ClaimStatus;
  rawStatus?: string;
  images: string[];
  video?: string;
  videos?: string[];
  evidence?: ClaimEvidenceItem[];
  fraudRisk: 'Low' | 'Medium' | 'High';
  fraudScore?: number;
  engineerEstimate?: number;
  approvedAmount?: number;
  approveReason?: string;
  rejectionReason?: string;
  requestInfoReason?: string;
  disputeNotes?: string;
  reviewedByAgent?: boolean;
  reviewedAt?: string;
  agentAction?: 'Approved' | 'Rejected' | 'More Info Requested';
  clientResponse?: 'Awaiting Response' | 'Approved by Client' | 'Rejected by Client';
  clientContactEmail?: string;
  clientContactPhone?: string;
  paymentStatus?: 'Not yet authorized' | 'Forwarded to Finance' | 'Payment Processing';
  clientResponseTimestamp?: string;
  clientResponseExplanation?: string;
}
