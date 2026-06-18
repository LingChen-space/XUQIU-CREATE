# Demand Mining Agent - One-click startup.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $root "start-services.ps1")
Start-Process "http://localhost:5174"
