-- Compatibility for the existing agent approval route.
-- approved_amount remains the canonical settlement amount; this field is retained
-- because the current API writes it while the UI/backend contract is being unified.
ALTER TABLE public.claims
  ADD COLUMN IF NOT EXISTS settlement_offer_amount NUMERIC(10,2)
  CHECK (settlement_offer_amount IS NULL OR settlement_offer_amount >= 0);

COMMENT ON COLUMN public.claims.settlement_offer_amount IS
  'Compatibility field used by the current agent approval route; approved_amount remains the canonical settlement amount.';
