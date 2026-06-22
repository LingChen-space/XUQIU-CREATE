# Reliable startup for the Demand Mining Agent services.
# Starts Monitor (8001), Backend (8000), and Frontend (5174) if they are not already running.

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $Root ".run-logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Python312 = "C:\Users\PC5080\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
if (-not (Test-Path $Python312)) {
    $Python312 = (Get-Command python.exe -ErrorAction Stop).Source
}

$NodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
if (-not $NodeExe -and (Test-Path "F:\node.js\node.exe")) {
    $NodeExe = "F:\node.js\node.exe"
}
if (-not $NodeExe) {
    throw "node.exe was not found."
}

# Some shells expose both Path and PATH, which makes Start-Process fail on Windows.
Remove-Item Env:PATH -ErrorAction SilentlyContinue

function Test-PortListening {
    param([int]$Port)

    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Start-Monitor {
    if (Test-PortListening 8001) {
        Write-Host "Monitor already running on 8001."
        return
    }

    $env:PYTHONPATH = (Join-Path $Root "crawler\.venv\Lib\site-packages") + ";" + (Join-Path $Root "crawler")
    $env:VIRTUAL_ENV = Join-Path $Root "crawler\.venv"

    Start-Process `
        -FilePath $Python312 `
        -ArgumentList @("server.py", "--host", "127.0.0.1", "--port", "8001") `
        -WorkingDirectory (Join-Path $Root "crawler") `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "monitor.out.log") `
        -RedirectStandardError (Join-Path $LogDir "monitor.err.log")
}

function Start-Backend {
    if (Test-PortListening 8000) {
        Write-Host "Backend already running on 8000."
        return
    }

    $env:PYTHONPATH = (Join-Path $Root "backend\.venv\Lib\site-packages") + ";" + (Join-Path $Root "backend")
    $env:VIRTUAL_ENV = Join-Path $Root "backend\.venv"

    Start-Process `
        -FilePath $Python312 `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") `
        -WorkingDirectory (Join-Path $Root "backend") `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "backend.out.log") `
        -RedirectStandardError (Join-Path $LogDir "backend.err.log")
}

function Start-Frontend {
    if (Test-PortListening 5174) {
        Write-Host "Frontend already running on 5174."
        return
    }

    $FrontendDir = Join-Path $Root "frontend"
    $ViteJs = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
    if (-not (Test-Path $ViteJs)) {
        throw "Vite was not found at $ViteJs."
    }

    Start-Process `
        -FilePath $NodeExe `
        -ArgumentList @($ViteJs, "--host", "0.0.0.0") `
        -WorkingDirectory $FrontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "frontend.out.log") `
        -RedirectStandardError (Join-Path $LogDir "frontend.err.log")
}

Start-Monitor
Start-Backend
Start-Frontend

Start-Sleep -Seconds 8

$Services = @(
    @{ Name = "Frontend"; Port = 5174; Url = "http://localhost:5174" },
    @{ Name = "Backend"; Port = 8000; Url = "http://localhost:8000" },
    @{ Name = "Monitor"; Port = 8001; Url = "http://localhost:8001" }
)

foreach ($Service in $Services) {
    if (Test-PortListening $Service.Port) {
        Write-Host "$($Service.Name) OK: $($Service.Url)"
    } else {
        Write-Warning "$($Service.Name) did not start on port $($Service.Port)."
    }
}
