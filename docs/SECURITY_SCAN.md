# Security Scan Findings

## Scan Scope

- **Working tree**: Full scan of all files in `wt-ops` worktree
- **Git history**: unable to verify - remote origin not accessible in this environment
- **Files scanned**: All Python, Markdown, text, JSON, YAML files excluding `.git/`

## Critical

| Severity | Location | What to Do |
|---|---|---|
| CRITICAL | `insurance-pro/backend/README.md:1173` - `FAST2SMS_API_KEY="HNs6..."` | Rotate the Fast2SMS API key immediately. Move any SMS credentials to `.env` (git-ignored). |
| CRITICAL | `insurance-pro/backend/README.md:1082` - `SMTP_PASSWORD="re_Sb..."` | Rotate the SMTP password immediately. Move SMTP credentials to `.env` (git-ignored). |
| CRITICAL | `insurance-pro/backend/app/core/config.py:19` - `SUPABASE_SERVICE_ROLE_KEY` default contains a real JWT key starting with `eyJh...` | Remove the default value or replace with placeholder. The `.env.example` already uses `your-service-role-key` placeholder. |
| CRITICAL | `insurance-pro/backend/app/core/config.py:18` - `SUPABASE_ANON_KEY` default contains a real JWT key starting with `eyJh...` | Remove the default value or replace with placeholder. The `.env.example` already uses `your-anon-key` placeholder. |

## High

| Severity | Location | What to Do |
|---|---|---|
| HIGH | `insurance-pro/backend/README.md:128-129` - `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` with real JWT values | Remove all real key values from README. Keep only variable NAMES/descriptions, never real keys. |
| HIGH | `insurance-pro/backend/README.md:133` - `JWT_SECRET="your-secure-random-secret-minimum-32-chars"` | Replace with placeholder value like `your-jwt-secret-key`. |

## Medium

| Severity | Location | What to Do |
|---|---|---|
| MEDIUM | `insurance-pro/backend/README.md` - Contains multiple hardcoded API key references and examples | Strip or mask all API key values from README. Keep only NAMES/descriptions, never real keys. |

## Low

| Severity | Location | What to Do |
|---|---|---|
| LOW | `insurance-pro/backend/.env.example` - All values are placeholders (`your-jwt-secret-key`, `your-service-role-key`, `your-smtp-password`) | No action needed. This is the correct pattern. Ensure no `.env` file is ever committed. |
| LOW | `insurance-pro/backend/app/core/config.py` - Default JWT_SECRET, SMTP_PASSWORD, and other fallbacks are in source code | These are fallbacks only. Ensure `.env` overrides them in production. No committed secrets. |

## Summary

- **4 Critical findings** — 2 exposed API keys in README, 2 hardcoded JWT keys in config.py defaults
- **2 High findings** — Additional exposed keys in README
- **1 Medium finding** — README contains hardcoded key references
- **2 Low findings** — .env.example and config.py fallbacks are properly using placeholders

**Immediate action required:**
1. Rotate the Fast2SMS API key and SMTP password exposed in README.md
2. Remove all real JWT key values from config.py defaults
3. Strip all hardcoded key values from README.md
4. Update `.env` files with new values (ensure `.env` is in `.gitignore`)

**Note:** Git history scan for `origin/insurance-pro`, `origin/models`, and `origin/ayaan-frontend-v2` was not performed due to remote access limitations. These repositories should also be scanned for committed secrets.
