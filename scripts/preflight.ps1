#!/usr/bin/env powershell
# ClaimPilot preflight: run from any directory with .\scripts\preflight.ps1
# Checks runtime prerequisites without printing environment values or secrets.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$allPassed = $true
$backendDir = Join-Path $repoRoot "insurance-pro\backend"
$backendVenvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$pythonCommand = if (Test-Path -LiteralPath $backendVenvPython) { $backendVenvPython } else { "python" }

function Write-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail = "")
    if ($Passed) {
        Write-Host "PASS: $Name" -ForegroundColor Green
    } else {
        Write-Host "FAIL: $Name $Detail" -ForegroundColor Red
        $script:allPassed = $false
    }
}

function Get-EnvValue {
    param([string]$FilePath, [string]$Key)
    if (-not (Test-Path -LiteralPath $FilePath)) { return $null }
    $line = Get-Content -LiteralPath $FilePath |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } |
        Select-Object -Last 1
    if (-not $line) { return $null }
    $value = $line.Substring($line.IndexOf("=") + 1).Trim()
    if ($value.Length -ge 2 -and (
        ($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))
    )) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    return $value
}

Write-Host "=== ClaimPilot preflight ==="
Write-Host "Repository: $repoRoot"

# 1. Local runtimes.
$pythonOk = $false
try {
    $pythonVersion = & $pythonCommand --version 2>&1
    $pythonOk = ($pythonVersion -match "Python 3\.11\.")
} catch { $pythonOk = $false }
Write-Check "Python 3.11" $pythonOk "Install/select Python 3.11 before running the demo."

$nodeOk = $false
try {
    $nodeVersion = node --version 2>&1
    $nodeOk = ($LASTEXITCODE -eq 0 -and $nodeVersion)
} catch { $nodeOk = $false }
Write-Check "Node.js installed" ([bool]$nodeOk) "Install a Node.js version supported by the committed lockfile."

# 2. Environment files and required variable names.
$backendEnv = Join-Path $repoRoot "insurance-pro\backend\.env"
$frontendEnv = Join-Path $repoRoot "insurance-pro\frontend\ClaimPilot\.env"
$backendExists = Test-Path -LiteralPath $backendEnv
$frontendExists = Test-Path -LiteralPath $frontendEnv
Write-Check "Backend .env exists" $backendExists "Copy insurance-pro\backend\.env.example to .env and configure it locally."
Write-Check "Frontend .env exists" $frontendExists "Copy insurance-pro\frontend\ClaimPilot\.env.example to .env and set VITE_API_BASE_URL."

$requiredBackendKeys = @(
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "JWT_SECRET",
    "ENVIRONMENT",
    "ALLOWED_ORIGINS",
    "FRONTEND_URL"
)
$missingBackendKeys = @()
foreach ($key in $requiredBackendKeys) {
    $value = Get-EnvValue -FilePath $backendEnv -Key $key
    if ([string]::IsNullOrWhiteSpace($value)) { $missingBackendKeys += $key }
}
Write-Check "Backend environment values present" ($missingBackendKeys.Count -eq 0) (
    if ($missingBackendKeys.Count -gt 0) { "Missing/empty variable names: $($missingBackendKeys -join ', ')" } else { "" }
)

$frontendApiUrl = Get-EnvValue -FilePath $frontendEnv -Key "VITE_API_BASE_URL"
Write-Check "Frontend API URL present" (-not [string]::IsNullOrWhiteSpace($frontendApiUrl)) "Set VITE_API_BASE_URL to the backend /api/v1 endpoint."

# 3. OTP delivery must be real, except explicit local/test fixed-code mode.
$environment = (Get-EnvValue -FilePath $backendEnv -Key "ENVIRONMENT")
$sendgridKey = Get-EnvValue -FilePath $backendEnv -Key "SENDGRID_API_KEY"
$sendgridFrom = Get-EnvValue -FilePath $backendEnv -Key "SENDGRID_FROM_EMAIL"
$fixedCode = Get-EnvValue -FilePath $backendEnv -Key "OTP_DEV_FIXED_CODE"
$hasSendGrid = -not [string]::IsNullOrWhiteSpace($sendgridKey) -and
    -not [string]::IsNullOrWhiteSpace($sendgridFrom)
$hasLocalFixedCode = ($environment -in @("development", "test")) -and ($fixedCode -match "^\d{6}$")
Write-Check "OTP delivery configured" ($hasSendGrid -or $hasLocalFixedCode) (
    "Configure SENDGRID_API_KEY + SENDGRID_FROM_EMAIL, or a six-digit OTP_DEV_FIXED_CODE for local development only."
)
if ($hasLocalFixedCode -and -not $hasSendGrid) {
    Write-Host "NOTE: fixed-code OTP is local/test only; never deploy it."
}

# 4. Model checkpoint presence. This does not prove inference quality.
$weightsDir = Join-Path $repoRoot "insurance-pro\backend\app\models\weights"
$weightFiles = @()
if (Test-Path -LiteralPath $weightsDir) {
    $weightFiles = @(Get-ChildItem -LiteralPath $weightsDir -File |
        Where-Object { $_.Name -in @("best.pt", "yolov11m.pt") -and $_.Length -gt 0 })
}
Write-Check "YOLO checkpoint present" ($weightFiles.Count -gt 0) "Expected a non-empty best.pt or yolov11m.pt under insurance-pro\backend\app\models\weights."

# 5. Local dependency import check.
if ($pythonOk) {
    $importOutput = & $pythonCommand -c "import fastapi, uvicorn, supabase, ultralytics, yaml, pydantic" 2>&1
    Write-Check "Backend dependency imports" ($LASTEXITCODE -eq 0) "Activate/install the backend environment from insurance-pro\backend\requirements.txt."
} else {
    Write-Check "Backend dependency imports" $false "Skipped because Python 3.11 was not found."
}

# 6. Supabase DNS/TLS port reachability (read-only; no DB writes).
# The backend /health/ready route performs the actual Data API query after startup.
$supabaseUrl = Get-EnvValue -FilePath $backendEnv -Key "SUPABASE_URL"
$supabaseReachable = $false
if (-not [string]::IsNullOrWhiteSpace($supabaseUrl)) {
    try {
        $uri = [System.Uri]$supabaseUrl
        if ($uri.Scheme -eq "https") {
            $supabaseReachable = [bool](Test-NetConnection -ComputerName $uri.DnsSafeHost -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue)
        }
    } catch { $supabaseReachable = $false }
}
Write-Check "Supabase host accepts HTTPS connections" $supabaseReachable "Check the configured project URL and network access; actual database access is verified by /health/ready."

# 7. The local demo ports need to be free.
foreach ($port in @(8000, 4173)) {
    $inUse = $false
    try { $inUse = [bool](Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue) } catch {}
    Write-Check "Port $port free" (-not $inUse) "Stop the process already listening on this port."
}

Write-Host ""
if ($allPassed) {
    Write-Host "Preflight passed. This does not replace the live claim E2E test." -ForegroundColor Green
    exit 0
}
Write-Host "Preflight failed. Fix the checks above; no secrets were printed." -ForegroundColor Red
exit 1
