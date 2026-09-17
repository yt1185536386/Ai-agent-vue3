# ai-service clean restart script (Windows PowerShell)
# Kill all ai-service processes (including uvicorn --reload parent), then restart
# Usage: cd packages/ai-service; .\restart.ps1

$serviceDir = $PSScriptRoot
$port = 26010
$venvPython = Join-Path $serviceDir '.venv\Scripts\python.exe'

Write-Host "=== ai-service clean restart ===" -ForegroundColor Cyan

# 1. Kill processes listening on port 26010
Write-Host "`n[1/4] Cleaning port $port ..." -ForegroundColor Yellow
$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        Write-Host "  Kill PID=$($c.OwningProcess)"
        & taskkill /PID $c.OwningProcess /T /F | Out-Null
    }
} else {
    Write-Host "  Port $port is free"
}

# 2. Kill residual uvicorn parent processes (prevent auto-reload)
Write-Host "`n[2/4] Cleaning residual uvicorn processes..." -ForegroundColor Yellow
$killed = 0
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*uvicorn*app.main*' -and $_.CommandLine -like '*ai-service*' } |
    ForEach-Object {
        Write-Host "  Kill residual PID=$($_.ProcessId)"
        & taskkill /PID $_.ProcessId /T /F | Out-Null
        $killed++
    }
if ($killed -eq 0) { Write-Host "  No residual uvicorn process" }

# 3. Confirm port is released
Write-Host "`n[3/4] Confirming port $port is released..." -ForegroundColor Yellow
Start-Sleep -Milliseconds 500
$stillUsed = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($stillUsed) {
    Write-Error "Port $port is still occupied, abort"
    exit 1
}
Write-Host "  Port $port released"

# 4. Start ai-service
Write-Host "`n[4/4] Starting ai-service..." -ForegroundColor Yellow
if (-not (Test-Path $venvPython)) {
    Write-Error "Venv not found: $venvPython"
    exit 1
}

$outLog = Join-Path $serviceDir 'dev-out.log'
$errLog = Join-Path $serviceDir 'dev-err.log'

Start-Process -FilePath $venvPython `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', $port `
    -WorkingDirectory $serviceDir `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden

# Wait for port ready
$timeout = 30
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$ready = $false
while ($sw.Elapsed.TotalSeconds -lt $timeout) {
    try {
        $conn = New-Object System.Net.Sockets.TcpClient('localhost', $port)
        if ($conn.Connected) {
            $conn.Close()
            $ready = $true
            break
        }
    } catch {}
    Start-Sleep -Milliseconds 500
}

if ($ready) {
    Write-Host "`n[OK] ai-service started: http://localhost:$port" -ForegroundColor Green
    Write-Host "  Logs: $outLog / $errLog" -ForegroundColor Gray
} else {
    Write-Error "ai-service not ready in ${timeout}s, check log: $errLog"
    exit 1
}
