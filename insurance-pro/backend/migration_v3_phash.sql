-- Run manually in the Supabase SQL editor. This migration is safe to reapply.
ALTER TABLE public.claim_evidence
  ADD COLUMN IF NOT EXISTS phash VARCHAR(16);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_phash
  ON public.claim_evidence (phash)
  WHERE phash IS NOT NULL;

ALTER TABLE public.claim_ai_analysis
  ADD COLUMN IF NOT EXISTS fraud_analysis JSONB;

ALTER TABLE public.claim_ai_analysis
  ADD COLUMN IF NOT EXISTS analysis_status TEXT,
  ADD COLUMN IF NOT EXISTS error_message TEXT;
