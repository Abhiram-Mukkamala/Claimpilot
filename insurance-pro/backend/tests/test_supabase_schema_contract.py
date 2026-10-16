"""Static contract checks keeping the Supabase migration aligned with the backend."""
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
CORE_SCHEMA = MIGRATIONS / "20261016194212_claimpilot_core_schema.sql"
SETTLEMENT_COMPAT = MIGRATIONS / "20261016194327_claim_settlement_offer_compat.sql"


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
        assert re.search(
            rf"create table if not exists public\\.{table}\\b",
            sql,
        ), f"Backend table public.{table} is absent from the core migration"


def test_claim_schema_supports_statuses_and_fields_written_by_backend():
    sql = _read_migration(CORE_SCHEMA)
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
        assert re.search(rf"\\b{field}\\b", sql)
    settlement_sql = _read_migration(SETTLEMENT_COMPAT)
    assert re.search(r"add column if not exists settlement_offer_amount", settlement_sql)


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
    assert "'claim-evidence','claim-evidence',false,52428800" in re.sub(r"\\s+", "", sql)
    assert "'image/jpeg'" in sql
    assert "'image/png'" in sql
    assert "'image/webp'" in sql
    assert "'video/mp4'" in sql
    assert "'video/quicktime'" in sql
