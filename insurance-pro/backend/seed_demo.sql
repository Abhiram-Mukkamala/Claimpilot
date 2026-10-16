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

-- The versioned Supabase migrations create the schema. Do not recreate it here
-- and do not add broad authenticated SELECT policies: the frontend talks to
-- FastAPI, while the server uses the service-role database client.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM public.profiles
        WHERE email = '<AGENT_EMAIL_PLACEHOLDER>'
          AND role = 'agent'
    ) THEN
        RAISE EXCEPTION
            'No registered agent profile found. Replace <AGENT_EMAIL_PLACEHOLDER> with a real agent email and register that agent first.';
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
