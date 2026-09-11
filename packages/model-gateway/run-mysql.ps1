# 以 mysql profile 启动 model-gateway,并复用 NestJS .env 中的数据库/JWT/渠道配置。
# 用法: powershell -File run-mysql.ps1   (或分离进程方式启动,见 README)
$ErrorActionPreference = 'Stop'

function Read-EnvFile($path) {
    $vars = @{}
    # 必须显式 UTF8: PowerShell 5.1 默认按 ANSI(GBK)读无 BOM 的 UTF-8,
    # 中文注释行的尾字节会吞掉换行符,导致其后的 KEY=VALUE 被并进注释行
    Get-Content $path -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $vars[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $vars
}

$vars = Read-EnvFile (Join-Path $PSScriptRoot '..\NestJS\.env')

$env:DB_HOST = $vars['DB_HOST'];         if (-not $env:DB_HOST) { $env:DB_HOST = 'localhost' }
$env:DB_PORT = $vars['DB_PORT'];         if (-not $env:DB_PORT) { $env:DB_PORT = '3306' }
$env:DB_USERNAME = $vars['DB_USERNAME']; if (-not $env:DB_USERNAME) { $env:DB_USERNAME = 'root' }
$env:DB_PASSWORD = $vars['DB_PASSWORD']
$env:DB_DATABASE = $vars['DB_DATABASE']; if (-not $env:DB_DATABASE) { $env:DB_DATABASE = 'ai_agent' }
# 与 NestJS 网关同一 JWT 密钥,本网关只校验 NestJS 签发的 token(不签发)。
# 以 JVM 系统属性显式传入(优先级最高,避免环境变量传递的不确定性)
$env:JWT_SECRET = $vars['JWT_SECRET']

# /v1/** 内部服务密钥: 与 NestJS/ai-service 之间的 NESTJS_SERVICE_KEY 同值
$env:GATEWAY_SERVICE_KEY = $vars['NESTJS_SERVICE_KEY']

# 真实渠道种子(渠道表为空时写入,见 DataInitializer.seedRealChannels)。
# 注意: NestJS/ai-service 的 .env 已改为指向本网关,真实上游配置只在这里
# 和 channels 表(管理端「仓库管理」可在线修改)持有。
$env:CHANNEL_COMPANY_BASE_URL = 'http://172.18.200.114:3000/v1'
$env:CHANNEL_COMPANY_API_KEY  = 'sk-qX6O5yjHcWa48ZWjSXkxctZEmejZWOSy7Oasg3l1V5Y846XZ'
$env:CHANNEL_COMPANY_MODELS   = ($vars['MODEL_NAME'] | Where-Object { $_ }) -join ','
$env:CHANNEL_BAILIAN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
$env:CHANNEL_BAILIAN_API_KEY  = 'sk-7c6e65b4d4ee41eb89eaf59f6381edc3'
$bailianModels = @($vars['BAILIAN_MODEL_NAME'], 'text-embedding-v3') | Where-Object { $_ }
$env:CHANNEL_BAILIAN_MODELS   = ($bailianModels -join ',')

& 'D:\maven\apache-maven-3.9.16\bin\mvn.cmd' `
    '-Dmaven.repo.local=D:\maven\repository' `
    'spring-boot:run' `
    '-Dspring-boot.run.profiles=mysql' `
    "-Dspring-boot.run.jvmArguments=-Dgateway.jwt.secret=$($vars['JWT_SECRET']) -Dgateway.service-key=$($vars['NESTJS_SERVICE_KEY'])"
