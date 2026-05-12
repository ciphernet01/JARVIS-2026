$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $root 'backend'
$overlayRoot = $PSScriptRoot
$frontendBuild = Join-Path $root 'frontend\build\index.html'

function Test-PortOpen {
    param([int]$Port)
    try {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        return [bool]$listener
    } catch {
        return $false
    }
}

if (-not (Test-PortOpen -Port 8001)) {
    Start-Process -WindowStyle Hidden -FilePath powershell.exe -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-Command',
        "Set-Location '$backendRoot'; python -m uvicorn server:app --host 0.0.0.0 --port 8001"
    ) | Out-Null
}

Start-Sleep -Seconds 2

if (-not (Test-Path $frontendBuild)) {
    Write-Host 'Frontend build not found. Build the React app before using the desktop overlay.'
}

Start-Process -WindowStyle Hidden -FilePath powershell.exe -ArgumentList @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-Command',
    "Set-Location '$overlayRoot'; npm start"
) | Out-Null
