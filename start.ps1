# 需求挖掘Agent 一键启动脚本
# 启动前端(5173)、后端(8000)、监控采集服务(8001)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  需求挖掘Agent - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 监控采集服务 (8001)
Write-Host "`n[1/3] 启动监控采集服务 (8001)..." -ForegroundColor Yellow
$monitorDir = Join-Path $root "监控脚本"
$monitorPython = Join-Path $monitorDir ".venv\Scripts\python.exe"
Start-Process -FilePath $monitorPython -ArgumentList "server.py","--port","8001" -WorkingDirectory $monitorDir -WindowStyle Minimized
Write-Host "   监控采集服务已启动" -ForegroundColor Green

# 2. 后端API服务 (8000)
Write-Host "`n[2/3] 启动后端API服务 (8000)..." -ForegroundColor Yellow
$backendDir = Join-Path $root "backend"
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" -WorkingDirectory $backendDir -WindowStyle Minimized
Write-Host "   后端API服务已启动" -ForegroundColor Green

# 3. 前端 (5173)
Write-Host "`n[3/3] 启动前端 (5173)..." -ForegroundColor Yellow
$frontendDir = Join-Path $root "frontend"
$nodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
if (-not $nodeExe) { $nodeExe = "F:\node.js\node.exe" }
$viteJs = Join-Path $frontendDir "node_modules\vite\bin\vite.js"
Start-Process -FilePath $nodeExe -ArgumentList $viteJs,"--host","0.0.0.0" -WorkingDirectory $frontendDir -WindowStyle Minimized
Write-Host "   前端已启动" -ForegroundColor Green

Start-Sleep -Seconds 6

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  检查服务状态..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ports = @{5173="前端"; 8000="后端"; 8001="监控"}
foreach ($p in $ports.Keys) {
    $listening = netstat -ano | Select-String ":$p " | Select-String "LISTENING"
    if ($listening) {
        Write-Host "  [$p] $($ports[$p]) 已就绪" -ForegroundColor Green
    } else {
        Write-Host "  [$p] $($ports[$p]) 未启动，请手动检查" -ForegroundColor Red
    }
}

Write-Host "`n打开浏览器访问: http://localhost:5173" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Start-Process "http://localhost:5173"
