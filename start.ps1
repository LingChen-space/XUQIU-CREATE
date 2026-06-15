# Demand Mining Agent - One-click Startup
# Launches Frontend(5173), Backend(8000), Monitor(8001)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Demand Mining Agent - Starting..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Monitor Service (8001)
Write-Host "`n[1/3] Starting Monitor Service (8001)..." -ForegroundColor Yellow
$monitorDir = Join-Path $root "监控脚本"
$monitorPython = Join-Path $monitorDir ".venv\Scripts\python.exe"
Start-Process -FilePath $monitorPython -ArgumentList "server.py","--port","8001" -WorkingDirectory $monitorDir -WindowStyle Minimized
Write-Host "   Monitor Service started" -ForegroundColor Green

# 2. Backend API (8000)
Write-Host "`n[2/3] Starting Backend API (8000)..." -ForegroundColor Yellow
$backendDir = Join-Path $root "backend"
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" -WorkingDirectory $backendDir -WindowStyle Minimized
Write-Host "   Backend API started" -ForegroundColor Green

# 3. Frontend (5173)
Write-Host "`n[3/3] Starting Frontend (5173)..." -ForegroundColor Yellow
$frontendDir = Join-Path $root "frontend"
$nodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
if (-not $nodeExe) { $nodeExe = "F:\node.js\node.exe" }
$viteJs = Join-Path $frontendDir "node_modules\vite\bin\vite.js"
Start-Process -FilePath $nodeExe -ArgumentList $viteJs,"--host","0.0.0.0" -WorkingDirectory $frontendDir -WindowStyle Minimized
Write-Host "   Frontend started" -ForegroundColor Green

Start-Sleep -Seconds 6

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Checking services..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ports = @{5173="Frontend"; 8000="Backend"; 8001="Monitor"}
foreach ($p in $ports.Keys) {
    $listening = netstat -ano | Select-String ":$p " | Select-String "LISTENING"
    if ($listening) {
        Write-Host "  [$p] $($ports[$p]) - OK" -ForegroundColor Green
    } else {
        Write-Host "  [$p] $($ports[$p]) - FAILED" -ForegroundColor Red
    }
}

Write-Host "`nOpen: http://localhost:5173" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Start-Process "http://localhost:5173"
