-- Persist the basis/limitations of geometry-derived repair-cost estimates.
-- These values are indicative only until calibrated against insurer/garage data.
ALTER TABLE public.claim_ai_analysis
  ADD COLUMN IF NOT EXISTS estimate_basis TEXT;

COMMENT ON COLUMN public.claim_ai_analysis.estimate_basis IS
  'Statement describing the basis and calibration limitation of the AI repair-cost estimate.';
