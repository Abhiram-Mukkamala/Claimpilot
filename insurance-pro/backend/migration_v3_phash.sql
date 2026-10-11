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

ALTER TABLE public.claim_ai_analysis
  ADD COLUMN IF NOT EXISTS fraud_analysis_error TEXT;

CREATE TABLE IF NOT EXISTS public.claim_fraud_analyses (
  claim_id UUID PRIMARY KEY REFERENCES public.claims (id) ON DELETE CASCADE,
  analysis_status TEXT NOT NULL,
  error_message TEXT,
  score INTEGER,
  risk_level TEXT,
  indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
  analysis JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
