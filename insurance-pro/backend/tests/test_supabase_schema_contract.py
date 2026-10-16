"""Static contract checks keeping the Supabase migration aligned with the backend."""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
CORE_SCHEMA = MIGRATIONS / "20261016194212_claimpilot_core_schema.sql"
SETTLEMENT_COMPAT = MIGRATIONS / "20261016194327_claim_settlement_offer_compat.sql"
FK_INDEXES = MIGRATIONS / "20261016195154_claimpilot_fk_indexes.sql"


def _read_migration(path: Path) -> str:
    assert path.is_file(), f"Required Supabase migration is missing: {path.name}"
    return path.read_text(encoding="utf-8").lower()


def test_core_schema_has_every_table_used_by_the_backend():
    sql = _read_migration(CORE_SCHEMA)
    tables = (
        "profiles",
        "otp_verifications",
        "claims",
        "claim_evidence",
        "claim_ai_analysis",
        "claim_fraud_analyses",
        "agent_policies",
        "policies",
    )
    for table in tables:
        assert f"create table if not exists public.{table} (" in sql, (
            f"Backend table public.{table} is absent from the core migration"
        )


def test_claim_schema_supports_statuses_and_fields_written_by_backend():
    sql = _read_migration(CORE_SCHEMA)
    api_schema = (REPO_ROOT / "insurance-pro" / "backend" / "app" / "schemas" / "claim.py").read_text(encoding="utf-8")
    for shared_status in ("pending_review", "under_review", "flagged", "manual_review", "action_required", "agent_approved", "settlement_accepted", "disputed", "rejected"):
        assert f'{shared_status} = "{shared_status}"' in api_schema, (
            f"ClaimStatus API enum is missing database status {shared_status}"
        )
    for status in (
        "pending_review",
        "under_review",
        "flagged",
        "manual_review",
        "action_required",
        "agent_approved",
        "settlement_accepted",
        "disputed",
        "rejected",
    ):
        assert f"'{status}'" in sql
    for field in ("location_city", "location_state", "pincode", "claimed_amount", "approved_amount"):
        assert field in sql
    settlement_sql = _read_migration(SETTLEMENT_COMPAT)
    assert "add column if not exists settlement_offer_amount" in settlement_sql


def test_otp_challenges_persist_purpose_identity_expiry_and_replay_state():
    sql = _read_migration(CORE_SCHEMA)
    table_start = sql.index("create table if not exists public.otp_verifications")
    table_end = sql.index(");", table_start)
    otp_table = sql[table_start:table_end]
    for fragment in (
        "identifier varchar(255) not null",
        "otp_code varchar(6) not null",
        "purpose varchar(10) not null",
        "user_id uuid references auth.users(id)",
        "attempts integer not null default 0",
        "is_verified boolean not null default false",
        "expires_at timestamptz not null",
    ):
        assert fragment in otp_table


def test_all_app_tables_enable_rls_and_deny_direct_client_table_grants():
    sql = _read_migration(CORE_SCHEMA)
    tables = (
        "profiles",
        "otp_verifications",
        "claims",
        "claim_evidence",
        "claim_ai_analysis",
        "claim_fraud_analyses",
        "agent_policies",
        "policies",
    )
    for table in tables:
        assert f"alter table public.{table} enable row level security" in sql
    assert "revoke all privileges on all tables in schema public from anon, authenticated" in sql
    assert "to service_role" in sql


def test_evidence_bucket_is_private_and_limits_match_backend():
    sql = _read_migration(CORE_SCHEMA)
    compact_sql = "".join(sql.split())
    assert "'claim-evidence','claim-evidence',false,52428800" in compact_sql
    for mime in ("image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"):
        assert f"'{mime}'" in sql



def test_foreign_key_indexes_are_kept_in_a_follow_up_migration():
    sql = _read_migration(FK_INDEXES)
    compact_sql = "".join(sql.split())
    assert "idx_otp_verifications_user_id" in sql
    assert "onpublic.otp_verifications(user_id)" in compact_sql
    assert "idx_policies_assigned_agent_id" in sql
    assert "onpublic.policies(assigned_agent_id)" in compact_sql
