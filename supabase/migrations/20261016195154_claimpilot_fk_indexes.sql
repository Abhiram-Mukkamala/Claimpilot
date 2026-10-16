-- Cover frequently joined foreign keys to avoid table scans on referenced-row changes.
CREATE INDEX IF NOT EXISTS idx_otp_verifications_user_id
  ON public.otp_verifications(user_id);

CREATE INDEX IF NOT EXISTS idx_policies_assigned_agent_id
  ON public.policies(assigned_agent_id);
