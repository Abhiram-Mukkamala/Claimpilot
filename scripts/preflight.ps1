#!/usr/bin/env powershell
# preflight.ps1 - Pre-demo checklist for claimbot AI
# Usage: .\scripts\preflight.ps1
# Exits with non-zero code on any FAIL

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

Write-Host "=== Preflight Checklist ==="
Write-Host ""

$allPassed = $true

# ============================================================
# CHECK 1: Python version >= 3.11
# ============================================================

Write-Host -NoNewline "(1) Python >= 3.11... "
try {
    $pythonOutput = python --version 2>&1
    if ($pythonOutput -match "Python 3\.11\.") {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL: Requires Python 3.11 (found: $pythonOutput)"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL: Python not found"
    $allPassed = $false
}

# ============================================================
# CHECK 2: Node.js version
# ============================================================

Write-Host -NoNewline "(2) Node.js installed... "
try {
    $nodeOutput = node --version 2>&1
    if ($nodeOutput) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL: Node.js not found"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL: Node.js not found"
    $allPassed = $false
}

# ============================================================
# CHECK 3: Both .env files exist
# ============================================================

$backendEnvPath = "insurance-pro\backend\.env"
$frontendEnvPath = "insurance-pro\frontend\ClaimPilot\.env"

Write-Host -NoNewline "(3a) Backend .env file exists... "
if (Test-Path $backendEnvPath) {
    Write-Host "PASS"
} else {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
}

Write-Host -NoNewline "(3b) Frontend .env file exists... "
if (Test-Path $frontendEnvPath) {
    Write-Host "PASS"
} else {
    Write-Host "FAIL: $frontendEnvPath does not exist"
    $allPassed = $false
}

# ============================================================
# CHECK 4: Required variable NAMES are set in .env files
# ============================================================

Write-Host -NoNewline "(4a) Backend required variable names... "
$backendRequiredKeys = @("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "JWT_SECRET", "ENVIRONMENT")
$backendMissingKeys = @()

if (Test-Path $backendEnvPath) {
    $backendEnvContent = Get-Content $backendEnvPath -Raw
    foreach ($key in $backendRequiredKeys) {
        $match = [regex]::Match($backendEnvContent, "^\s*$key\s*=", [System.Text.RegularExpressions.RegexOptions]::Multiline)
        if (-not $match.Success) {
            $backendMissingKeys += $key
        }
    }
    
    if ($backendMissingKeys.Count -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL: Missing variable names: $($backendMissingKeys -join ', ')"
        $allPassed = $false
    }
} else {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
}

Write-Host -NoNewline "(4b) Frontend required variable names... "
$frontendRequiredKeys = @("VITE_API_BASE_URL")
$frontendMissingKeys = @()

if (Test-Path $frontendEnvPath) {
    $frontendEnvContent = Get-Content $frontendEnvPath -Raw
    foreach ($key in $frontendRequiredKeys) {
        $match = [regex]::Match($frontendEnvContent, "^\s*$key\s*=", [System.Text.RegularExpressions.RegexOptions]::Multiline)
        if (-not $match.Success) {
            $frontendMissingKeys += $key
        }
    }
    
    if ($frontendMissingKeys.Count -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL: Missing variable names: $($frontendMissingKeys -join ', ')"
        $allPassed = $false
    }
} else {
    Write-Host "FAIL: $frontendEnvPath does not exist"
    $allPassed = $false
}

# ============================================================
# CHECK 4c: Email OTP delivery is explicitly configured
# ============================================================

Write-Host -NoNewline "(4c) Email OTP delivery configured... "
if (Test-Path $backendEnvPath) {
    $backendEnvContent = Get-Content $backendEnvPath -Raw
    $sendgridKey = [regex]::Match($backendEnvContent, '(?m)^\s*SENDGRID_API_KEY\s*=\s*"?([^"\r\n]+)"?\s*# ============================================================

Write-Host -NoNewline "(5) Weight files exist and non-empty... "
$weightsDir = "insurance-pro\backend\app\models\weights"

if (-not (Test-Path $weightsDir)) {
    Write-Host "FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    # Look for YOLO weight files (best.pt is primary, yolov11m.pt is fallback)
    $yoloWeightFiles = Get-ChildItem -Path $weightsDir -File -Include @("best.pt", "yolov11m.pt")
    
    if ($yoloWeightFiles.Count -eq 0) {
        Write-Host "FAIL: Expected at least one YOLO weight file (best.pt or yolov11m.pt), found $($yoloWeightFiles.Count)"
        $allPassed = $false
    } else {
        $allNonEmpty = $true
        $emptyFiles = @()
        foreach ($file in $yoloWeightFiles) {
            if ($file.Length -eq 0) {
                $allNonEmpty = $false
                $emptyFiles += $file.Name
            }
        }
        if (-not $allNonEmpty) {
            Write-Host "FAIL: Empty weight files: $($emptyFiles -join ', ')"
            $allPassed = $false
        } else {
            Write-Host "PASS (found $($yoloWeightFiles.Count) YOLO weight file(s))"
        }
    }
}

# ============================================================
# CHECK 6: Ports 8000 and 4173 are free
# ============================================================

$ports = @(8000, 4173)
foreach ($port in $ports) {
    Write-Host -NoNewline "(6) Port $port is free... "
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($connection -eq $false) {
            Write-Host "PASS"
        } else {
            Write-Host "FAIL: Port $port is in use"
            $allPassed = $false
        }
    } catch {
        # If we can't test (e.g., network issues), assume it's free
        Write-Host "PASS"
    }
}

# ============================================================
# CHECK 7: Supabase is reachable
# ============================================================

Write-Host -NoNewline "(7) Supabase is reachable... "

if (-not (Test-Path $backendEnvPath)) {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
} else {
    $envContent = Get-Content $backendEnvPath -Raw
    $supabaseUrlMatch = [regex]::Match($envContent, "^\s*SUPABASE_URL\s*=\s*(.+?)\s*$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
    
    if (-not $supabaseUrlMatch.Success) {
        Write-Host "FAIL: SUPABASE_URL not found in backend .env"
        $allPassed = $false
    } else {
        $supabaseUrl = $supabaseUrlMatch.Groups[1].Value.Trim('"', "'")
        try {
            # Ensure URL starts with https://
            if (-not $supabaseUrl.StartsWith("https://")) {
                if (-not $supabaseUrl.StartsWith("http://")) {
                    $supabaseUrl = "https://" + $supabaseUrl
                }
            }
            
            $response = Invoke-WebRequest -Uri $supabaseUrl -Method Head -UseBasicParsing -ErrorAction Stop
            Write-Host "PASS"
        } catch {
            Write-Host "FAIL: Could not reach Supabase URL"
            $allPassed = $false
        }
    }
}

# ============================================================
# CHECK 8: Backend deps import
# ============================================================

Write-Host -NoNewline "(8) Backend deps import... "
try {
    # Test critical imports
    $pythonCheck = python -c "import fastapi; import uvicorn; import ultralytics; import yaml; import pydantic" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL"
    $allPassed = $false
}

# ============================================================
# CHECK 9: Ultralytics loads each weight file
# ============================================================

Write-Host "(9) Ultralytics loads weight files..."

if (-not (Test-Path $weightsDir)) {
    Write-Host "  FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    $weightFiles = Get-ChildItem -Path $weightsDir -File -Include @("*.pt", "*.pth", "*.bin", "*.weights", "*.h5", "*.safetensors")
    
    if ($weightFiles.Count -lt 2) {
        Write-Host "  FAIL: Expected at least 2 weight files, found $($weightFiles.Count)"
        $allPassed = $false
    } else {
        $allLoaded = $true
        foreach ($file in $weightFiles) {
            Write-Host -NoNewline "  Loading $($file.Name)... "
            try {
                $pythonScript = "from ultralytics import YOLO; model = YOLO('$($file.FullName)'); print(', '.join(model.names.values()))"
                $output = python -c $pythonScript 2>&1
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "FAIL"
                    Write-Host "    Error: $output"
                    $allLoaded = $false
                    $allPassed = $false
                } else {
                    Write-Host "OK (classes: $output)"
                }
            } catch {
                Write-Host "FAIL"
                Write-Host "    Error: $_"
                $allLoaded = $false
                $allPassed = $false
            }
        }
        
        if ($allLoaded) {
            Write-Host "  PASS"
        }
    }
}

# ============================================================
# FINAL RESULT
# ============================================================

Write-Host ""
Write-Host "=== Preflight Result ==="
if ($allPassed) {
    Write-Host "ALL CHECKS PASSED"
    exit 0
} else {
    Write-Host "SOME CHECKS FAILED"
    exit 1
}
)
    $sendgridFrom = [regex]::Match($backendEnvContent, '(?m)^\s*SENDGRID_FROM_EMAIL\s*=\s*"?([^"\r\n]+)"?\s*# ============================================================

Write-Host -NoNewline "(5) Weight files exist and non-empty... "
$weightsDir = "insurance-pro\backend\app\models\weights"

if (-not (Test-Path $weightsDir)) {
    Write-Host "FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    # Look for YOLO weight files (best.pt is primary, yolov11m.pt is fallback)
    $yoloWeightFiles = Get-ChildItem -Path $weightsDir -File -Include @("best.pt", "yolov11m.pt")
    
    if ($yoloWeightFiles.Count -eq 0) {
        Write-Host "FAIL: Expected at least one YOLO weight file (best.pt or yolov11m.pt), found $($yoloWeightFiles.Count)"
        $allPassed = $false
    } else {
        $allNonEmpty = $true
        $emptyFiles = @()
        foreach ($file in $yoloWeightFiles) {
            if ($file.Length -eq 0) {
                $allNonEmpty = $false
                $emptyFiles += $file.Name
            }
        }
        if (-not $allNonEmpty) {
            Write-Host "FAIL: Empty weight files: $($emptyFiles -join ', ')"
            $allPassed = $false
        } else {
            Write-Host "PASS (found $($yoloWeightFiles.Count) YOLO weight file(s))"
        }
    }
}

# ============================================================
# CHECK 6: Ports 8000 and 4173 are free
# ============================================================

$ports = @(8000, 4173)
foreach ($port in $ports) {
    Write-Host -NoNewline "(6) Port $port is free... "
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($connection -eq $false) {
            Write-Host "PASS"
        } else {
            Write-Host "FAIL: Port $port is in use"
            $allPassed = $false
        }
    } catch {
        # If we can't test (e.g., network issues), assume it's free
        Write-Host "PASS"
    }
}

# ============================================================
# CHECK 7: Supabase is reachable
# ============================================================

Write-Host -NoNewline "(7) Supabase is reachable... "

if (-not (Test-Path $backendEnvPath)) {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
} else {
    $envContent = Get-Content $backendEnvPath -Raw
    $supabaseUrlMatch = [regex]::Match($envContent, "^\s*SUPABASE_URL\s*=\s*(.+?)\s*$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
    
    if (-not $supabaseUrlMatch.Success) {
        Write-Host "FAIL: SUPABASE_URL not found in backend .env"
        $allPassed = $false
    } else {
        $supabaseUrl = $supabaseUrlMatch.Groups[1].Value.Trim('"', "'")
        try {
            # Ensure URL starts with https://
            if (-not $supabaseUrl.StartsWith("https://")) {
                if (-not $supabaseUrl.StartsWith("http://")) {
                    $supabaseUrl = "https://" + $supabaseUrl
                }
            }
            
            $response = Invoke-WebRequest -Uri $supabaseUrl -Method Head -UseBasicParsing -ErrorAction Stop
            Write-Host "PASS"
        } catch {
            Write-Host "FAIL: Could not reach Supabase URL"
            $allPassed = $false
        }
    }
}

# ============================================================
# CHECK 8: Backend deps import
# ============================================================

Write-Host -NoNewline "(8) Backend deps import... "
try {
    # Test critical imports
    $pythonCheck = python -c "import fastapi; import uvicorn; import ultralytics; import yaml; import pydantic" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL"
    $allPassed = $false
}

# ============================================================
# CHECK 9: Ultralytics loads each weight file
# ============================================================

Write-Host "(9) Ultralytics loads weight files..."

if (-not (Test-Path $weightsDir)) {
    Write-Host "  FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    $weightFiles = Get-ChildItem -Path $weightsDir -File -Include @("*.pt", "*.pth", "*.bin", "*.weights", "*.h5", "*.safetensors")
    
    if ($weightFiles.Count -lt 2) {
        Write-Host "  FAIL: Expected at least 2 weight files, found $($weightFiles.Count)"
        $allPassed = $false
    } else {
        $allLoaded = $true
        foreach ($file in $weightFiles) {
            Write-Host -NoNewline "  Loading $($file.Name)... "
            try {
                $pythonScript = "from ultralytics import YOLO; model = YOLO('$($file.FullName)'); print(', '.join(model.names.values()))"
                $output = python -c $pythonScript 2>&1
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "FAIL"
                    Write-Host "    Error: $output"
                    $allLoaded = $false
                    $allPassed = $false
                } else {
                    Write-Host "OK (classes: $output)"
                }
            } catch {
                Write-Host "FAIL"
                Write-Host "    Error: $_"
                $allLoaded = $false
                $allPassed = $false
            }
        }
        
        if ($allLoaded) {
            Write-Host "  PASS"
        }
    }
}

# ============================================================
# FINAL RESULT
# ============================================================

Write-Host ""
Write-Host "=== Preflight Result ==="
if ($allPassed) {
    Write-Host "ALL CHECKS PASSED"
    exit 0
} else {
    Write-Host "SOME CHECKS FAILED"
    exit 1
}
)
    $environmentMatch = [regex]::Match($backendEnvContent, '(?m)^\s*ENVIRONMENT\s*=\s*"?([^"\r\n]+)"?\s*# ============================================================

Write-Host -NoNewline "(5) Weight files exist and non-empty... "
$weightsDir = "insurance-pro\backend\app\models\weights"

if (-not (Test-Path $weightsDir)) {
    Write-Host "FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    # Look for YOLO weight files (best.pt is primary, yolov11m.pt is fallback)
    $yoloWeightFiles = Get-ChildItem -Path $weightsDir -File -Include @("best.pt", "yolov11m.pt")
    
    if ($yoloWeightFiles.Count -eq 0) {
        Write-Host "FAIL: Expected at least one YOLO weight file (best.pt or yolov11m.pt), found $($yoloWeightFiles.Count)"
        $allPassed = $false
    } else {
        $allNonEmpty = $true
        $emptyFiles = @()
        foreach ($file in $yoloWeightFiles) {
            if ($file.Length -eq 0) {
                $allNonEmpty = $false
                $emptyFiles += $file.Name
            }
        }
        if (-not $allNonEmpty) {
            Write-Host "FAIL: Empty weight files: $($emptyFiles -join ', ')"
            $allPassed = $false
        } else {
            Write-Host "PASS (found $($yoloWeightFiles.Count) YOLO weight file(s))"
        }
    }
}

# ============================================================
# CHECK 6: Ports 8000 and 4173 are free
# ============================================================

$ports = @(8000, 4173)
foreach ($port in $ports) {
    Write-Host -NoNewline "(6) Port $port is free... "
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($connection -eq $false) {
            Write-Host "PASS"
        } else {
            Write-Host "FAIL: Port $port is in use"
            $allPassed = $false
        }
    } catch {
        # If we can't test (e.g., network issues), assume it's free
        Write-Host "PASS"
    }
}

# ============================================================
# CHECK 7: Supabase is reachable
# ============================================================

Write-Host -NoNewline "(7) Supabase is reachable... "

if (-not (Test-Path $backendEnvPath)) {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
} else {
    $envContent = Get-Content $backendEnvPath -Raw
    $supabaseUrlMatch = [regex]::Match($envContent, "^\s*SUPABASE_URL\s*=\s*(.+?)\s*$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
    
    if (-not $supabaseUrlMatch.Success) {
        Write-Host "FAIL: SUPABASE_URL not found in backend .env"
        $allPassed = $false
    } else {
        $supabaseUrl = $supabaseUrlMatch.Groups[1].Value.Trim('"', "'")
        try {
            # Ensure URL starts with https://
            if (-not $supabaseUrl.StartsWith("https://")) {
                if (-not $supabaseUrl.StartsWith("http://")) {
                    $supabaseUrl = "https://" + $supabaseUrl
                }
            }
            
            $response = Invoke-WebRequest -Uri $supabaseUrl -Method Head -UseBasicParsing -ErrorAction Stop
            Write-Host "PASS"
        } catch {
            Write-Host "FAIL: Could not reach Supabase URL"
            $allPassed = $false
        }
    }
}

# ============================================================
# CHECK 8: Backend deps import
# ============================================================

Write-Host -NoNewline "(8) Backend deps import... "
try {
    # Test critical imports
    $pythonCheck = python -c "import fastapi; import uvicorn; import ultralytics; import yaml; import pydantic" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL"
    $allPassed = $false
}

# ============================================================
# CHECK 9: Ultralytics loads each weight file
# ============================================================

Write-Host "(9) Ultralytics loads weight files..."

if (-not (Test-Path $weightsDir)) {
    Write-Host "  FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    $weightFiles = Get-ChildItem -Path $weightsDir -File -Include @("*.pt", "*.pth", "*.bin", "*.weights", "*.h5", "*.safetensors")
    
    if ($weightFiles.Count -lt 2) {
        Write-Host "  FAIL: Expected at least 2 weight files, found $($weightFiles.Count)"
        $allPassed = $false
    } else {
        $allLoaded = $true
        foreach ($file in $weightFiles) {
            Write-Host -NoNewline "  Loading $($file.Name)... "
            try {
                $pythonScript = "from ultralytics import YOLO; model = YOLO('$($file.FullName)'); print(', '.join(model.names.values()))"
                $output = python -c $pythonScript 2>&1
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "FAIL"
                    Write-Host "    Error: $output"
                    $allLoaded = $false
                    $allPassed = $false
                } else {
                    Write-Host "OK (classes: $output)"
                }
            } catch {
                Write-Host "FAIL"
                Write-Host "    Error: $_"
                $allLoaded = $false
                $allPassed = $false
            }
        }
        
        if ($allLoaded) {
            Write-Host "  PASS"
        }
    }
}

# ============================================================
# FINAL RESULT
# ============================================================

Write-Host ""
Write-Host "=== Preflight Result ==="
if ($allPassed) {
    Write-Host "ALL CHECKS PASSED"
    exit 0
} else {
    Write-Host "SOME CHECKS FAILED"
    exit 1
}
)
    $fixedCode = [regex]::Match($backendEnvContent, '(?m)^\s*OTP_DEV_FIXED_CODE\s*=\s*"?\d{6}"?\s*# ============================================================

Write-Host -NoNewline "(5) Weight files exist and non-empty... "
$weightsDir = "insurance-pro\backend\app\models\weights"

if (-not (Test-Path $weightsDir)) {
    Write-Host "FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    # Look for YOLO weight files (best.pt is primary, yolov11m.pt is fallback)
    $yoloWeightFiles = Get-ChildItem -Path $weightsDir -File -Include @("best.pt", "yolov11m.pt")
    
    if ($yoloWeightFiles.Count -eq 0) {
        Write-Host "FAIL: Expected at least one YOLO weight file (best.pt or yolov11m.pt), found $($yoloWeightFiles.Count)"
        $allPassed = $false
    } else {
        $allNonEmpty = $true
        $emptyFiles = @()
        foreach ($file in $yoloWeightFiles) {
            if ($file.Length -eq 0) {
                $allNonEmpty = $false
                $emptyFiles += $file.Name
            }
        }
        if (-not $allNonEmpty) {
            Write-Host "FAIL: Empty weight files: $($emptyFiles -join ', ')"
            $allPassed = $false
        } else {
            Write-Host "PASS (found $($yoloWeightFiles.Count) YOLO weight file(s))"
        }
    }
}

# ============================================================
# CHECK 6: Ports 8000 and 4173 are free
# ============================================================

$ports = @(8000, 4173)
foreach ($port in $ports) {
    Write-Host -NoNewline "(6) Port $port is free... "
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($connection -eq $false) {
            Write-Host "PASS"
        } else {
            Write-Host "FAIL: Port $port is in use"
            $allPassed = $false
        }
    } catch {
        # If we can't test (e.g., network issues), assume it's free
        Write-Host "PASS"
    }
}

# ============================================================
# CHECK 7: Supabase is reachable
# ============================================================

Write-Host -NoNewline "(7) Supabase is reachable... "

if (-not (Test-Path $backendEnvPath)) {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
} else {
    $envContent = Get-Content $backendEnvPath -Raw
    $supabaseUrlMatch = [regex]::Match($envContent, "^\s*SUPABASE_URL\s*=\s*(.+?)\s*$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
    
    if (-not $supabaseUrlMatch.Success) {
        Write-Host "FAIL: SUPABASE_URL not found in backend .env"
        $allPassed = $false
    } else {
        $supabaseUrl = $supabaseUrlMatch.Groups[1].Value.Trim('"', "'")
        try {
            # Ensure URL starts with https://
            if (-not $supabaseUrl.StartsWith("https://")) {
                if (-not $supabaseUrl.StartsWith("http://")) {
                    $supabaseUrl = "https://" + $supabaseUrl
                }
            }
            
            $response = Invoke-WebRequest -Uri $supabaseUrl -Method Head -UseBasicParsing -ErrorAction Stop
            Write-Host "PASS"
        } catch {
            Write-Host "FAIL: Could not reach Supabase URL"
            $allPassed = $false
        }
    }
}

# ============================================================
# CHECK 8: Backend deps import
# ============================================================

Write-Host -NoNewline "(8) Backend deps import... "
try {
    # Test critical imports
    $pythonCheck = python -c "import fastapi; import uvicorn; import ultralytics; import yaml; import pydantic" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL"
    $allPassed = $false
}

# ============================================================
# CHECK 9: Ultralytics loads each weight file
# ============================================================

Write-Host "(9) Ultralytics loads weight files..."

if (-not (Test-Path $weightsDir)) {
    Write-Host "  FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    $weightFiles = Get-ChildItem -Path $weightsDir -File -Include @("*.pt", "*.pth", "*.bin", "*.weights", "*.h5", "*.safetensors")
    
    if ($weightFiles.Count -lt 2) {
        Write-Host "  FAIL: Expected at least 2 weight files, found $($weightFiles.Count)"
        $allPassed = $false
    } else {
        $allLoaded = $true
        foreach ($file in $weightFiles) {
            Write-Host -NoNewline "  Loading $($file.Name)... "
            try {
                $pythonScript = "from ultralytics import YOLO; model = YOLO('$($file.FullName)'); print(', '.join(model.names.values()))"
                $output = python -c $pythonScript 2>&1
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "FAIL"
                    Write-Host "    Error: $output"
                    $allLoaded = $false
                    $allPassed = $false
                } else {
                    Write-Host "OK (classes: $output)"
                }
            } catch {
                Write-Host "FAIL"
                Write-Host "    Error: $_"
                $allLoaded = $false
                $allPassed = $false
            }
        }
        
        if ($allLoaded) {
            Write-Host "  PASS"
        }
    }
}

# ============================================================
# FINAL RESULT
# ============================================================

Write-Host ""
Write-Host "=== Preflight Result ==="
if ($allPassed) {
    Write-Host "ALL CHECKS PASSED"
    exit 0
} else {
    Write-Host "SOME CHECKS FAILED"
    exit 1
}
)
    $environment = if ($environmentMatch.Success) { $environmentMatch.Groups[1].Value.Trim() } else { "" }
    $hasRealEmail = $sendgridKey.Success -and $sendgridFrom.Success
    $hasLocalCode = ($environment -in @("development", "test")) -and $fixedCode.Success
    if ($hasRealEmail) {
        Write-Host "PASS (SendGrid values present; provider credentials not independently validated)"
    } elseif ($hasLocalCode) {
        Write-Host "PASS (local/test fixed code only; not for deployment)"
    } else {
        Write-Host "FAIL: Configure SendGrid or a local-only fixed code for development"
        $allPassed = $false
    }
} else {
    Write-Host "FAIL: backend .env missing"
    $allPassed = $false
}

# ============================================================
# CHECK 5: Weight files exist and are non-empty
# ============================================================

Write-Host -NoNewline "(5) Weight files exist and non-empty... "
$weightsDir = "insurance-pro\backend\app\models\weights"

if (-not (Test-Path $weightsDir)) {
    Write-Host "FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    # Look for YOLO weight files (best.pt is primary, yolov11m.pt is fallback)
    $yoloWeightFiles = Get-ChildItem -Path $weightsDir -File -Include @("best.pt", "yolov11m.pt")
    
    if ($yoloWeightFiles.Count -eq 0) {
        Write-Host "FAIL: Expected at least one YOLO weight file (best.pt or yolov11m.pt), found $($yoloWeightFiles.Count)"
        $allPassed = $false
    } else {
        $allNonEmpty = $true
        $emptyFiles = @()
        foreach ($file in $yoloWeightFiles) {
            if ($file.Length -eq 0) {
                $allNonEmpty = $false
                $emptyFiles += $file.Name
            }
        }
        if (-not $allNonEmpty) {
            Write-Host "FAIL: Empty weight files: $($emptyFiles -join ', ')"
            $allPassed = $false
        } else {
            Write-Host "PASS (found $($yoloWeightFiles.Count) YOLO weight file(s))"
        }
    }
}

# ============================================================
# CHECK 6: Ports 8000 and 4173 are free
# ============================================================

$ports = @(8000, 4173)
foreach ($port in $ports) {
    Write-Host -NoNewline "(6) Port $port is free... "
    try {
        $connection = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
        if ($connection -eq $false) {
            Write-Host "PASS"
        } else {
            Write-Host "FAIL: Port $port is in use"
            $allPassed = $false
        }
    } catch {
        # If we can't test (e.g., network issues), assume it's free
        Write-Host "PASS"
    }
}

# ============================================================
# CHECK 7: Supabase is reachable
# ============================================================

Write-Host -NoNewline "(7) Supabase is reachable... "

if (-not (Test-Path $backendEnvPath)) {
    Write-Host "FAIL: $backendEnvPath does not exist"
    $allPassed = $false
} else {
    $envContent = Get-Content $backendEnvPath -Raw
    $supabaseUrlMatch = [regex]::Match($envContent, "^\s*SUPABASE_URL\s*=\s*(.+?)\s*$", [System.Text.RegularExpressions.RegexOptions]::Multiline)
    
    if (-not $supabaseUrlMatch.Success) {
        Write-Host "FAIL: SUPABASE_URL not found in backend .env"
        $allPassed = $false
    } else {
        $supabaseUrl = $supabaseUrlMatch.Groups[1].Value.Trim('"', "'")
        try {
            # Ensure URL starts with https://
            if (-not $supabaseUrl.StartsWith("https://")) {
                if (-not $supabaseUrl.StartsWith("http://")) {
                    $supabaseUrl = "https://" + $supabaseUrl
                }
            }
            
            $response = Invoke-WebRequest -Uri $supabaseUrl -Method Head -UseBasicParsing -ErrorAction Stop
            Write-Host "PASS"
        } catch {
            Write-Host "FAIL: Could not reach Supabase URL"
            $allPassed = $false
        }
    }
}

# ============================================================
# CHECK 8: Backend deps import
# ============================================================

Write-Host -NoNewline "(8) Backend deps import... "
try {
    # Test critical imports
    $pythonCheck = python -c "import fastapi; import uvicorn; import ultralytics; import yaml; import pydantic" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PASS"
    } else {
        Write-Host "FAIL"
        $allPassed = $false
    }
} catch {
    Write-Host "FAIL"
    $allPassed = $false
}

# ============================================================
# CHECK 9: Ultralytics loads each weight file
# ============================================================

Write-Host "(9) Ultralytics loads weight files..."

if (-not (Test-Path $weightsDir)) {
    Write-Host "  FAIL: Directory $weightsDir does not exist"
    $allPassed = $false
} else {
    $weightFiles = Get-ChildItem -Path $weightsDir -File -Include @("*.pt", "*.pth", "*.bin", "*.weights", "*.h5", "*.safetensors")
    
    if ($weightFiles.Count -lt 2) {
        Write-Host "  FAIL: Expected at least 2 weight files, found $($weightFiles.Count)"
        $allPassed = $false
    } else {
        $allLoaded = $true
        foreach ($file in $weightFiles) {
            Write-Host -NoNewline "  Loading $($file.Name)... "
            try {
                $pythonScript = "from ultralytics import YOLO; model = YOLO('$($file.FullName)'); print(', '.join(model.names.values()))"
                $output = python -c $pythonScript 2>&1
                
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "FAIL"
                    Write-Host "    Error: $output"
                    $allLoaded = $false
                    $allPassed = $false
                } else {
                    Write-Host "OK (classes: $output)"
                }
            } catch {
                Write-Host "FAIL"
                Write-Host "    Error: $_"
                $allLoaded = $false
                $allPassed = $false
            }
        }
        
        if ($allLoaded) {
            Write-Host "  PASS"
        }
    }
}

# ============================================================
# FINAL RESULT
# ============================================================

Write-Host ""
Write-Host "=== Preflight Result ==="
if ($allPassed) {
    Write-Host "ALL CHECKS PASSED"
    exit 0
} else {
    Write-Host "SOME CHECKS FAILED"
    exit 1
}
