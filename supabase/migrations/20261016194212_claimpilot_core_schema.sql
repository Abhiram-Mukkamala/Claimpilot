-- ClaimPilot core schema for Supabase.
-- Backend-only data access: all exposed public tables have RLS enabled and
-- no anon/authenticated table grants. FastAPI uses the service_role key server-side.
-- Evidence bucket is private; browser uploads use short-lived signed upload URLs.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
  CREATE TYPE public.user_role AS ENUM ('customer', 'agent', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.claim_type AS ENUM ('Accident', 'Theft', 'Fire', 'Natural Event');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE public.claim_status AS ENUM (
    'pending_review',
    'under_review',
    'flagged',
    'manual_review',
    'action_required',
    'agent_approved',
    'settlement_accepted',
    'disputed',
    'rejected'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  phone_number VARCHAR(20) UNIQUE NOT NULL,
  dob DATE NOT NULL,
  role public.user_role NOT NULL DEFAULT 'customer',
  is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  is_phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.otp_verifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  identifier VARCHAR(255) NOT NULL,
  otp_code VARCHAR(6) NOT NULL,
  channel VARCHAR(10) NOT NULL CHECK (channel IN ('email', 'sms')),
  purpose VARCHAR(10) NOT NULL DEFAULT 'signup' CHECK (purpose IN ('signup', 'login')),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.claims (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_number VARCHAR(50) UNIQUE NOT NULL,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  assigned_agent_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  incident_type public.claim_type NOT NULL,
  vehicle_name VARCHAR(100) NOT NULL,
  policy_number VARCHAR(100) NOT NULL,
  hsrp_number VARCHAR(20) NOT NULL,
  engine_number VARCHAR(50) NOT NULL,
  chassis_number VARCHAR(50) NOT NULL,
  incident_date DATE NOT NULL,
  location_address TEXT NOT NULL,
  location_city VARCHAR(100),
  location_state VARCHAR(100),
  pincode VARCHAR(10),
  description VARCHAR(500) NOT NULL,
  driver_name VARCHAR(255) NOT NULL,
  driver_dl_number VARCHAR(50) NOT NULL,
  claimed_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (claimed_amount >= 0),
  approved_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (approved_amount >= 0),
  status public.claim_status NOT NULL DEFAULT 'pending_review',
  fraud_score INTEGER NOT NULL DEFAULT 0 CHECK (fraud_score BETWEEN 0 AND 100),
  risk_level VARCHAR(20) NOT NULL DEFAULT 'Low Risk',
  agent_rejection_reason TEXT,
  agent_custom_notes TEXT,
  requested_info_notes JSONB NOT NULL DEFAULT '[]'::jsonb,
  dispute_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.claim_evidence (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id UUID NOT NULL REFERENCES public.claims(id) ON DELETE CASCADE,
  file_url TEXT NOT NULL,
  storage_path VARCHAR(500) NOT NULL,
  file_type VARCHAR(50) NOT NULL,
  category VARCHAR(50) NOT NULL CHECK (category IN ('photo', 'walkaround_video', 'dl_front', 'dl_back', 'video', 'damage_photo')),
  phash VARCHAR(16),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.claim_ai_analysis (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id UUID NOT NULL UNIQUE REFERENCES public.claims(id) ON DELETE CASCADE,
  detected_damages JSONB NOT NULL DEFAULT '[]'::jsonb,
  estimated_cost_min NUMERIC(10,2) NOT NULL DEFAULT 0.00,
  estimated_cost_max NUMERIC(10,2) NOT NULL DEFAULT 0.00,
  clahe_image_url TEXT,
  segmentation_masks JSONB NOT NULL DEFAULT '{}'::jsonb,
  surface_area_px INTEGER NOT NULL DEFAULT 0,
  relative_deformation_z JSONB NOT NULL DEFAULT '{}'::jsonb,
  dsine_vectors JSONB NOT NULL DEFAULT '{}'::jsonb,
  fraud_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  fraud_analysis JSONB,
  analysis_status TEXT,
  error_message TEXT,
  fraud_analysis_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.claim_fraud_analyses (
  claim_id UUID PRIMARY KEY REFERENCES public.claims(id) ON DELETE CASCADE,
  analysis_status TEXT NOT NULL,
  error_message TEXT,
  score INTEGER CHECK (score BETWEEN 0 AND 100),
  risk_level TEXT,
  indicators JSONB NOT NULL DEFAULT '[]'::jsonb,
  analysis JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.agent_policies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  policy_number VARCHAR(100) UNIQUE NOT NULL,
  agent_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.policies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  policy_number VARCHAR(100) UNIQUE NOT NULL,
  assigned_agent_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  customer_name VARCHAR(255),
  vehicle_model VARCHAR(100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claims_user_id ON public.claims(user_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON public.claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_assigned_agent ON public.claims(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id ON public.claim_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_phash ON public.claim_evidence(phash) WHERE phash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_otp_identifier_created_at ON public.otp_verifications(identifier, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_otp_expires_at ON public.otp_verifications(expires_at);
CREATE INDEX IF NOT EXISTS idx_agent_policies_policy_number ON public.agent_policies(policy_number);
CREATE INDEX IF NOT EXISTS idx_agent_policies_agent_id ON public.agent_policies(agent_id);
CREATE INDEX IF NOT EXISTS idx_policies_policy_number ON public.policies(policy_number);

-- The FastAPI service is the only application layer permitted to access these tables.
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.otp_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_ai_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_fraud_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policies ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON TABLE
  public.profiles,
  public.otp_verifications,
  public.claims,
  public.claim_evidence,
  public.claim_ai_analysis,
  public.claim_fraud_analyses,
  public.agent_policies,
  public.policies
TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- Avoid reintroducing Data API grants to these roles for future tables created by this owner.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;

-- This starter table was empty at review time and is unrelated to ClaimPilot.
-- Remove its broad default Data API grants while preserving the table itself.
DO $$ BEGIN
  IF to_regclass('public.tasks') IS NOT NULL THEN
    EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE public.tasks FROM anon, authenticated';
  END IF;
  IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
    EXECUTE 'REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated';
  END IF;
END $$;

-- Private evidence storage. The service-role backend signs short-lived upload/read URLs.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'claim-evidence',
  'claim-evidence',
  FALSE,
  52428800,
  ARRAY['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/quicktime']::text[]
)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    public = FALSE,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;
