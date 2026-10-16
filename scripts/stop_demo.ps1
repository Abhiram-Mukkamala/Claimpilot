#!/usr/bin/env powershell
# stop_demo.ps1 - Stop all processes started by start_demo.ps1
# Usage: .\scripts\stop_demo.ps1

Set-ErrorActionPreference -ErrorAction SilentlyContinue

$pidFile = "$env:TEMP\claimbot_demo_pids.txt"

if (-not (Test-Path $pidFile)) {
    Write-Host "No PID file found at $pidFile. No processes to stop."
    exit 0
}

Write-Host "Stopping demo processes..."

# Function to recursively stop a process and all its children
function Stop-ProcessTree {
    param([int]$ProcessId)
    
    # Get the process
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) {
        return
    }
    
    # First, recursively stop all child processes
    $children = Get-WmiObject Win32_Process -Filter "ParentProcessId = $ProcessId" | Select-Object -ExpandProperty ProcessId
    foreach ($childId in $children) {
        Stop-ProcessTree -ProcessId $childId
    }
    
    # Then stop the process itself
    try {
        $process | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "  Stopped PID $ProcessId ($($process.Name))"
    } catch {
        Write-Warning "  Could not stop PID $ProcessId"
    }
}

# Read PIDs from file
$pids = Get-Content $pidFile -ErrorAction SilentlyContinue
if (-not $pids) {
    Write-Host "PID file is empty. No processes to stop."
    Remove-Item $pidFile -Force
    exit 0
}

# Stop each process tree
foreach ($pid in $pids) {
    if ([int]::TryParse($pid, [ref]$parsedPid)) {
        Stop-ProcessTree -ProcessId $parsedPid
    }
}

# Clean up PID file
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue

Write-Host "All demo processes stopped."
