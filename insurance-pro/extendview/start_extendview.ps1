# Launch both ClaimPilot ExtendView Streamlit servers:
#   - Customer Extended View on http://localhost:8501 (customer_app.py)
#   - Adjuster Extended View on http://localhost:8502 (agent_app.py)

$ErrorActionPreference = "Stop"
$ExtendViewDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Prefer dedicated .venv-ext, then v3/.venv (which already has torch, sam2, transformers, dsine cached)
$VenvExtPython = Join-Path $ExtendViewDir ".venv-ext\Scripts\python.exe"
$V3VenvPython = "C:\Users\abhir\Downloads\v3\v3\.venv\Scripts\python.exe"

if (Test-Path $VenvExtPython) {
    $PythonExe = $VenvExtPython
} elseif (Test-Path $V3VenvPython) {
    $PythonExe = $V3VenvPython
} else {
    $PythonExe = "python"
}

Write-Host "Using Python runtime: $PythonExe" -ForegroundColor Green
Write-Host "Starting Customer Extended View on http://localhost:8501 ..." -ForegroundColor Cyan
Start-Process -FilePath $PythonExe -ArgumentList "-m streamlit run `"$ExtendViewDir\customer_app.py`" --server.port 8501 --server.headless true" -WorkingDirectory $ExtendViewDir

Write-Host "Starting Adjuster Extended View on http://localhost:8502 ..." -ForegroundColor Cyan
Start-Process -FilePath $PythonExe -ArgumentList "-m streamlit run `"$ExtendViewDir\agent_app.py`" --server.port 8502 --server.headless true" -WorkingDirectory $ExtendViewDir
