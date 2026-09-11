# model-gateway 生产/共享库启动脚本
# 以 mysql profile 启动 Java 网关:与 NestJS 共用 ai_agent 库(users/channels 等真实数据),
# 并自动从 packages/NestJS/.env 读取 DB_* / JWT_SECRET / 服务密钥。
# 用法: 在仓库根目录执行  powershell -ExecutionPolicy Bypass -File run-mysql.ps1

$ErrorActionPreference = Stop

$root = $PSScriptRoot
$envFile = Join-Path $root "packages\NestJS\.env"

if (-not (Test-Path $envFile)) {
    Write-Error "找不到 $envFile —— 请先按 README 配置 NestJS/.env"
    exit 1
}

# 从 NestJS/.env 读取所需变量(不回显密钥值)
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([A-Z_]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
    }
}

# 网关需要的三把关键变量(服务密钥与 NESTJS_SERVICE_KEY 同值)
$env:GATEWAY_SERVICE_KEY = [System.Environment]::GetEnvironmentVariable("NESTJS_SERVICE_KEY", "Process")
if (-not $env:GATEWAY_SERVICE_KEY) { Write-Error "NESTJS_SERVICE_KEY 未配置"; exit 1 }
if (-not $env:JWT_SECRET)          { Write-Error "JWT_SECRET 未配置"; exit 1 }

# JAVA_HOME 指向 JDK 21(按需修改)
if (-not $env:JAVA_HOME) { $env:JAVA_HOME = "C:\Program Files\Java\latest\jdk-21" }

Write-Host "以 mysql profile 启动 model-gateway(:6015,共享 ai_agent 库)..."
& "$env:JAVA_HOME\bin\java.exe" -jar (Join-Path $root "packages\model-gateway\target\model-gateway-1.0.0.jar") --spring.profiles.active=mysql
