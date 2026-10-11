# Security Scan Findings

## Scan Scope

- **Working tree**: Full scan of all files in `wt-ops` worktree
- **Git history**: Scanned local remote-tracking refs `origin/insurance-pro`, `origin/models`, `origin/ayaan-frontend-v2` using `git grep` and `git log -S`
- **Files scanned**: All Python, Markdown, text, JSON, YAML, TypeScript files

## Critical

| Severity | Location | What to Do |
|---|---|---|
| CRITICAL | `origin/insurance-pro:backend/README.md:1173` - `FAST2SMS_API_KEY="HNs6..."` (commit 358a6c2) | Rotate the Fast2SMS API key immediately. Move any SMS credentials to `.env` (git-ignored). |
| CRITICAL | `origin/insurance-pro:backend/README.md:1082` - `SMTP_PASSWORD="re_Sb..."` (commit 358a6c2) | Rotate the SMTP password immediately. Move SMTP credentials to `.env` (git-ignored). |
| CRITICAL | `origin/insurance-pro:backend/app/core/config.py:19` - `SUPABASE_SERVICE_ROLE_KEY` default contains a real JWT key starting with `eyJh...` (commit 1726f80) | Remove the default value or replace with placeholder. The `.env.example` already uses `your-service-role-key` placeholder. |
| CRITICAL | `origin/insurance-pro:backend/app/core/config.py:18` - `SUPABASE_ANON_KEY` default contains a real JWT key starting with `eyJh...` (commit 1726f80) | Remove the default value or replace with placeholder. The `.env.example` already uses `your-anon-key` placeholder. |

## High

| Severity | Location | What to Do |
|---|---|---|
| HIGH | `origin/insurance-pro:backend/README.md:128-129` - `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` with real JWT values | Remove all real key values from README. Keep only variable NAMES/descriptions, never real keys. |
| HIGH | `origin/insurance-pro:backend/README.md:133` - `JWT_SECRET="your-secure-random-secret-minimum-32-chars"` | Replace with placeholder value like `your-jwt-secret-key`. |
| HIGH | `origin/insurance-pro:backend/README.md:1051` - Example key `re_SbWKS8wz_CufEEWXAfcpHPmCDLN7nwyad` in instructions | Remove example key from README. Keep only variable NAMES/descriptions. |
| HIGH | `origin/insurance-pro:backend/app/core/config.py:23` - `JWT_SECRET` default contains real-looking secret `claimpilot-secure-production-jwt-secret-key-2026-v1` | Remove the default value or replace with placeholder. |
| HIGH | `origin/insurance-pro:backend/app/core/config.py:39` - `SMTP_PASSWORD` default contains `mock-smtp-password` | Remove the default value or replace with placeholder. |

## Medium

| Severity | Location | What to Do |
|---|---|---|
| MEDIUM | `origin/insurance-pro:backend/README.md` - Contains multiple hardcoded API key references and examples | Strip or mask all API key values from README. Keep only NAMES/descriptions, never real keys. |
| MEDIUM | `origin/insurance-pro:backend/app/core/config.py:46` - `TWILIO_AUTH_TOKEN` default is empty string but variable name exposed | Remove default or replace with placeholder. |
| MEDIUM | `origin/insurance-pro:backend/app/core/config.py:48` - `FAST2SMS_API_KEY` default is empty string but variable name exposed | Remove default or replace with placeholder. |

## Low

| Severity | Location | What to Do |
|---|---|---|
| LOW | `insurance-pro/backend/.env.example` - All values are placeholders (`your-jwt-secret-key`, `your-service-role-key`, `your-smtp-password`) | No action needed. This is the correct pattern. Ensure no `.env` file is ever committed. |

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

**Summary**

- **4 CRITICAL findings** — Fast2SMS API key and SMTP password in README.md (commit 358a6c2), 2 hardcoded JWT keys in config.py (commit 1726f80)
- **4 HIGH findings** — Additional exposed keys and defaults in README and config.py
- **3 MEDIUM findings** — API key references and empty default strings
- **1 LOW finding** — .env.example correctly uses placeholders

**Git history scan results:**
- `origin/insurance-pro`: 10+ secret-related findings across README.md and config.py
- `origin/models`: No secrets found
- `origin/ayaan-frontend-v2`: No secrets found
