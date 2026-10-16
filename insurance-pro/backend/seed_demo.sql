-- ============================================================================
-- ClaimPilot Demo Seeding Script: agent_policies & policies
-- ============================================================================
-- PREREQUISITES / INSTRUCTIONS:
-- 1. Register an Agent account first through the application or Supabase Auth.
-- 2. Verify that the agent record exists in public.profiles.
-- 3. Replace '<AGENT_EMAIL_PLACEHOLDER>' below with the registered agent's exact
--    email address (for example: 'agent@claimpilot.ai').
-- 4. Execute this SQL script in the Supabase SQL Editor:
--    https://supabase.com/dashboard/project/_/sql
-- ============================================================================

-- Ensure required extension for UUID generation exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Ensure Table DDL: public.agent_policies
-- Used by claims.py:58-68 as source of truth for Agent-Policy mapping
CREATE TABLE IF NOT EXISTS public.agent_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_number VARCHAR(100) UNIQUE NOT NULL,
    agent_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Ensure Table DDL: public.policies
-- Used by claims.py:72-80, 104-142 for policy lookup and tracking
CREATE TABLE IF NOT EXISTS public.policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_number VARCHAR(100) UNIQUE NOT NULL,
    assigned_agent_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    customer_name VARCHAR(255),
    vehicle_model VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Performance Indices
CREATE INDEX IF NOT EXISTS idx_agent_policies_policy_number ON public.agent_policies(policy_number);
CREATE INDEX IF NOT EXISTS idx_agent_policies_agent_id ON public.agent_policies(agent_id);
CREATE INDEX IF NOT EXISTS idx_policies_policy_number ON public.policies(policy_number);

-- 4. Enable Row Level Security (RLS) & Service Role Policies
ALTER TABLE public.agent_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.policies ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'agent_policies' AND policyname = 'Allow read access for authenticated users'
    ) THEN
        CREATE POLICY "Allow read access for authenticated users" 
        ON public.agent_policies FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'policies' AND policyname = 'Allow read access for authenticated users'
    ) THEN
        CREATE POLICY "Allow read access for authenticated users" 
        ON public.policies FOR SELECT TO authenticated USING (true);
    END IF;
END $$;

-- 5. Seed Demo Policies Mapped to the Target Agent
-- Idempotent: Skips if policy_number already exists

-- DEMO-POL-001
INSERT INTO public.agent_policies (policy_number, agent_id)
SELECT 'DEMO-POL-001', id 
FROM public.profiles 
WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
ON CONFLICT (policy_number) DO NOTHING;

INSERT INTO public.policies (policy_number, assigned_agent_id, customer_name, vehicle_model)
SELECT 'DEMO-POL-001', id, 'Demo Customer 1', 'Honda City 2022'
FROM public.profiles 
WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
ON CONFLICT (policy_number) DO NOTHING;

-- DEMO-POL-002
INSERT INTO public.agent_policies (policy_number, agent_id)
SELECT 'DEMO-POL-002', id 
FROM public.profiles 
WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
ON CONFLICT (policy_number) DO NOTHING;

INSERT INTO public.policies (policy_number, assigned_agent_id, customer_name, vehicle_model)
SELECT 'DEMO-POL-002', id, 'Demo Customer 2', 'Hyundai Creta 2023'
FROM public.profiles 
WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
ON CONFLICT (policy_number) DO NOTHING;

-- DEMO-POL-003
INSERT INTO public.agent_policies (policy_number, agent_id)
SELECT 'DEMO-POL-003', id 
FROM public.profiles 
WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
ON CONFLICT (policy_number) DO NOTHING;

INSERT INTO public.policies (policy_number, assigned_agent_id, customer_name, vehicle_model)
SELECT 'DEMO-POL-003', id, 'Demo Customer 3', 'Tata Nexon EV 2024'
FROM public.profiles 
WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
ON CONFLICT (policy_number) DO NOTHING;
