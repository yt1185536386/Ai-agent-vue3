# Start model-gateway + rag-service with in-memory vector store
# No Docker/PostgreSQL required

$ErrorActionPreference = "Stop"

$env:GATEWAY_SERVICE_KEY = "rag-dev-key"
$env:JWT_SECRET = "model-gateway-dev-secret-key-please-change-in-prod"

# 如需自动创建百炼渠道，请在当前环境变量中设置：
#   CHANNEL_BAILIAN_BASE_URL, CHANNEL_BAILIAN_API_KEY, CHANNEL_BAILIAN_MODELS
# 这些变量会透传给 model-gateway。

$modelGatewayDir = "D:\selfFile\python\vue3\v3agent\packages\model-gateway"
$ragServiceDir = "D:\selfFile\python\vue3\v3agent\packages\rag-service"
$mvn = "D:\maven\apache-maven-3.9.16\bin\mvn.cmd"

function Wait-Port {
    param($Port, $TimeoutSeconds = 120)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        try {
            $conn = New-Object System.Net.Sockets.TcpClient("localhost", $Port)
            if ($conn.Connected) {
                $conn.Close()
                return $true
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host "Starting model-gateway on port 26015..."
Start-Process -FilePath $mvn `
    -ArgumentList "spring-boot:run", "-Dspring-boot.run.jvmArguments=-DGATEWAY_SERVICE_KEY=$env:GATEWAY_SERVICE_KEY -DJWT_SECRET=$env:JWT_SECRET" `
    -WorkingDirectory $modelGatewayDir `
    -WindowStyle Hidden

if (-not (Wait-Port -Port 26015 -TimeoutSeconds 180)) {
    Write-Error "model-gateway failed to start within 180 seconds"
}
Write-Host "model-gateway is ready"

Write-Host "Starting rag-service on port 26016..."
Start-Process -FilePath $mvn `
    -ArgumentList "spring-boot:run", "-Dspring-boot.run.jvmArguments=-DGATEWAY_SERVICE_KEY=$env:GATEWAY_SERVICE_KEY -DJWT_SECRET=$env:JWT_SECRET -DMODEL_CHANNEL_KEY=bailian -DVECTOR_DIMENSION=1024 -DVECTOR_MODE=memory" `
    -WorkingDirectory $ragServiceDir `
    -WindowStyle Hidden

if (-not (Wait-Port -Port 26016 -TimeoutSeconds 180)) {
    Write-Error "rag-service failed to start within 180 seconds"
}
Write-Host "rag-service is ready"

Write-Host ""
Write-Host "RAG services started:"
Write-Host "  model-gateway: http://localhost:26015"
Write-Host "  rag-service:   http://localhost:26016"
Write-Host ""
Write-Host "Note: set CHANNEL_BAILIAN_BASE_URL, CHANNEL_BAILIAN_API_KEY and CHANNEL_BAILIAN_MODELS"
Write-Host "      before running this script to enable the Bailian channel."
