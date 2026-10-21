-- ==========================================================
-- ClaimPilot Migration Script: v2.0 (OTP & Schema Refinements)
-- Execute this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/sjokskemaonnvbqlnbdz/sql
-- ==========================================================

-- Extensions & ENUMs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('customer', 'agent', 'admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE claim_type AS ENUM ('Accident', 'Theft', 'Fire', 'Natural Event');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE claim_status AS ENUM (
      'pending_review', 
      'under_review', 
      'flagged', 
      'action_required', 
      'agent_approved', 
      'settlement_accepted', 
      'disputed', 
      'rejected'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 1. Profiles Table Updates
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  full_name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  phone_number VARCHAR(20) UNIQUE NOT NULL,
  dob DATE NOT NULL,
  role user_role DEFAULT 'customer',
  is_email_verified BOOLEAN DEFAULT FALSE,
  is_phone_verified BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure columns exist if table was already created in v1
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS is_phone_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. OTP Lifecycle Storage (SMS & Email)
CREATE TABLE IF NOT EXISTS public.otp_verifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  identifier VARCHAR(255) NOT NULL, -- Email address or E.164 Phone Number
  otp_code VARCHAR(6) NOT NULL,
  channel VARCHAR(10) NOT NULL, -- 'email' or 'sms'
  attempts INT DEFAULT 0,
  is_verified BOOLEAN DEFAULT FALSE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Claims Engine Table (Refined with Location & Financials)
CREATE TABLE IF NOT EXISTS public.claims (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_number VARCHAR(50) UNIQUE NOT NULL,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  assigned_agent_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
  
  -- Policy & Vehicle Metadata
  incident_type claim_type NOT NULL,
  vehicle_name VARCHAR(100) NOT NULL,
  policy_number VARCHAR(100) NOT NULL,
  hsrp_number VARCHAR(20) NOT NULL,
  engine_number VARCHAR(50) NOT NULL,
  chassis_number VARCHAR(50) NOT NULL,
  incident_date DATE NOT NULL,
  
  -- Address Breakdown
  location_address TEXT NOT NULL,
  location_city VARCHAR(100),
  location_state VARCHAR(100),
  pincode VARCHAR(10),
  description VARCHAR(500) NOT NULL,
  
  -- Driver Verification
  driver_name VARCHAR(255) NOT NULL,
  driver_dl_number VARCHAR(20) NOT NULL,
  
  -- Financial Ledger
  claimed_amount NUMERIC(10, 2) DEFAULT 0.00,
  approved_amount NUMERIC(10, 2) DEFAULT 0.00,

  -- Workflow & Fraud Metrics
  status claim_status DEFAULT 'pending_review',
  fraud_score INT DEFAULT 0,
  risk_level VARCHAR(20) DEFAULT 'Low Risk',
  
  -- Agent Audit Logs
  agent_rejection_reason TEXT,
  agent_custom_notes TEXT,
  requested_info_notes JSONB DEFAULT '[]'::jsonb,
  dispute_notes TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure v2 columns exist on existing table
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS location_city VARCHAR(100);
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS location_state VARCHAR(100);
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS pincode VARCHAR(10);
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS claimed_amount NUMERIC(10, 2) DEFAULT 0.00;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS approved_amount NUMERIC(10, 2) DEFAULT 0.00;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS agent_custom_notes TEXT;
ALTER TABLE public.claims ADD COLUMN IF NOT EXISTS dispute_notes TEXT;

-- 4. Claim Evidence Catalog
CREATE TABLE IF NOT EXISTS public.claim_evidence (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE NOT NULL,
  file_url TEXT NOT NULL,
  storage_path VARCHAR(500) NOT NULL,
  file_type VARCHAR(50) NOT NULL,
  category VARCHAR(50) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE public.claim_evidence ADD COLUMN IF NOT EXISTS storage_path VARCHAR(500) DEFAULT '';

-- 5. AI Damage Assessment
CREATE TABLE IF NOT EXISTS public.claim_ai_analysis (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  claim_id UUID REFERENCES public.claims(id) ON DELETE CASCADE UNIQUE NOT NULL,
  detected_damages JSONB NOT NULL DEFAULT '[]'::jsonb,
  estimated_cost_min NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
  estimated_cost_max NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
  clahe_image_url TEXT,
  segmentation_masks JSONB DEFAULT '{}'::jsonb,
  surface_area_px INT DEFAULT 0,
  relative_deformation_z JSONB DEFAULT '{}'::jsonb,
  dsine_vectors JSONB DEFAULT '{}'::jsonb,
  fraud_flags JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Performance Indices
CREATE INDEX IF NOT EXISTS idx_claims_user_id ON public.claims(user_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON public.claims(status);
CREATE INDEX IF NOT EXISTS idx_otp_identifier ON public.otp_verifications(identifier);
CREATE INDEX IF NOT EXISTS idx_otp_expires_at ON public.otp_verifications(expires_at);
