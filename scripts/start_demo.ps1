#!/usr/bin/env powershell
# start_demo.ps1 - One-command local demo launcher for claimbot AI
# Usage: .\scripts\start_demo.ps1

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

# ============================================================
# VALIDATION: Check prerequisites
# ============================================================

Write-Host "=== Starting claimbot AI demo ==="

# Check Python 3.11
Write-Host -NoNewline "Checking Python 3.11... "
try {
    $pythonOutput = python --version 2>&1
    if ($pythonOutput -match "Python 3\.11\.") {
        Write-Host "OK"
    } else {
        Write-Host "FAIL"
        Write-Error "Python 3.11 is required (found: $pythonOutput)"
        exit 1
    }
} catch {
    Write-Host "FAIL"
    Write-Error "Python not found. Please install Python 3.11."
    exit 1
}

# Check Node.js
Write-Host -NoNewline "Checking Node.js... "
try {
    $nodeOutput = node --version 2>&1
    if ($nodeOutput) {
        Write-Host "OK (v$($nodeOutput.Trim()))"
    } else {
        Write-Host "FAIL"
        Write-Error "Node.js is required but not found."
        exit 1
    }
} catch {
    Write-Host "FAIL"
    Write-Error "Node.js not found. Please install Node.js."
    exit 1
}

# ============================================================
# VALIDATION: Check .env files
# ============================================================

function Test-EnvFile {
    param(
        [string]$FilePath,
        [string[]]$RequiredKeys
    )
    
    if (-not (Test-Path $FilePath)) {
        Write-Host "FAIL: $FilePath does not exist"
        return $false
    }
    
    $fileContent = Get-Content $FilePath -Raw
    $missingKeys = @()
    
    foreach ($key in $RequiredKeys) {
        # Match lines like: KEY=value or KEY = value or KEY="value"
        $match = [regex]::Match($fileContent, "^\s*$key\s*=", [System.Text.RegularExpressions.RegexOptions]::Multiline)
        if (-not $match.Success) {
            $missingKeys += $key
        }
    }
    
    if ($missingKeys.Count -gt 0) {
        Write-Host "FAIL: $FilePath missing keys: $($missingKeys -join ', ')"
        return $false
    }
    
    return $true
}

$backendEnvPath = "insurance-pro\backend\.env"
$frontendEnvPath = "insurance-pro\frontend\ClaimPilot\.env"
$backendDir = Join-Path $repoRoot "insurance-pro\backend"
$frontendDir = Join-Path $repoRoot "insurance-pro\frontend\ClaimPilot"

$backendRequiredKeys = @("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "JWT_SECRET", "ENVIRONMENT")
$frontendRequiredKeys = @("VITE_API_BASE_URL")

Write-Host -NoNewline "Checking $backendEnvPath... "
$backendEnvOk = Test-EnvFile -FilePath $backendEnvPath -RequiredKeys $backendRequiredKeys
if ($backendEnvOk) { Write-Host "OK" }

Write-Host -NoNewline "Checking $frontendEnvPath... "
$frontendEnvOk = Test-EnvFile -FilePath $frontendEnvPath -RequiredKeys $frontendRequiredKeys
if ($frontendEnvOk) { Write-Host "OK" }

Write-Host -NoNewline "Checking OTP delivery configuration... "
$emailConfigured = $false
$localFixedCode = $false
if (Test-Path $backendEnvPath) {
    $envContent = Get-Content $backendEnvPath -Raw
    $sendgridKeyMatch = [regex]::Match($envContent, '(?m)^\s*SENDGRID_API_KEY\s*=\s*"?([^"\r\n]+)"?\s*$')
    $sendgridFromMatch = [regex]::Match($envContent, '(?m)^\s*SENDGRID_FROM_EMAIL\s*=\s*"?([^"\r\n]+)"?\s*$')
    $environmentMatch = [regex]::Match($envContent, '(?m)^\s*ENVIRONMENT\s*=\s*"?([^"\r\n]+)"?\s*$')
    $fixedCodeMatch = [regex]::Match($envContent, '(?m)^\s*OTP_DEV_FIXED_CODE\s*=\s*"?\d{6}"?\s*$')
    $emailConfigured = $sendgridKeyMatch.Success -and $sendgridFromMatch.Success
    $environment = if ($environmentMatch.Success) { $environmentMatch.Groups[1].Value.Trim() } else { "" }
    $localFixedCode = $environment -in @("development", "test") -and $fixedCodeMatch.Success
}
if ($emailConfigured) {
    Write-Host "SendGrid configured"
} elseif ($localFixedCode) {
    Write-Host "development/test fixed OTP configured (never use in production)"
} else {
    Write-Host "FAIL"
    Write-Error "Configure SENDGRID_API_KEY and SENDGRID_FROM_EMAIL, or a six-digit OTP_DEV_FIXED_CODE with ENVIRONMENT=development for local-only testing."
    exit 1
}

if (-not $backendEnvOk -or -not $frontendEnvOk) {
    Write-Error "Environment files are missing or incomplete."
    exit 1
}

# ============================================================
# SETUP: PID tracking file
# ============================================================

$pidFile = "$env:TEMP\claimbot_demo_pids.txt"
if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force
}

# ============================================================
# START: Backend (uvicorn)
# ============================================================

Write-Host -NoNewline "Starting backend... "
$backendProcess = Start-Process -FilePath "python" -WorkingDirectory $backendDir -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") -PassThru
$backendProcess.Id | Out-File $pidFile
Write-Host "PID=$($backendProcess.Id)"

# ============================================================
# START: Frontend (npm)
# ============================================================

Write-Host -NoNewline "Starting frontend... "
Write-Host -NoNewline "Starting frontend... "
Write-Host "Running npm ci, then npm run build (Vite bakes VITE_* values at build time)..."
$frontendProcess = Start-Process -FilePath "powershell" -WorkingDirectory $frontendDir -ArgumentList @(
    "-NoLogo", "-NoProfile", "-NonInteractive",
    "-Command", "npm ci; if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE }; npm run build; if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE }; npm run preview"
) -PassThru
$frontendProcess.Id | Out-File $pidFile -Append
Write-Host "Frontend PID=$($frontendProcess.Id)"

# ============================================================
# WAIT: For backend to be ready
# ============================================================

Write-Host -NoNewline "Waiting for Supabase-backed readiness... "
$maxRetries = 30
$retryInterval = 2
$backendReady = $false

for ($i = 0; $i -lt $maxRetries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health/ready" -Method Get -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {
        # Keep retrying while backend starts; liveness and /docs do not prove
        # that Supabase and OTP delivery are configured.
    }

    Start-Sleep -Seconds $retryInterval
}

if (-not $backendReady) {
    Write-Host "FAIL"
    Write-Error "Backend did not become ready within $($maxRetries * $retryInterval) seconds."
    Write-Error "Check backend logs. Stopping all processes..."
    # Attempt to clean up
    if (Test-Path $pidFile) {
        $pids = Get-Content $pidFile
        foreach ($pid in $pids) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    exit 1
}

Write-Host "OK"

# ============================================================
# OPEN: Browser
# ============================================================

Write-Host "Opening browser to frontend..."
start "" "http://localhost:4173"

# ============================================================
# STATUS: Print service status
# ============================================================

Write-Host ""
Write-Host "=== Demo is running ==="
Write-Host "Backend:  http://localhost:8000 (PID: $($backendProcess.Id))"
Write-Host "Frontend: http://localhost:4173 (PID: $($frontendProcess.Id))"
Write-Host "PID file: $pidFile"
Write-Host ""
Write-Host "To stop: .\scripts\stop_demo.ps1"
