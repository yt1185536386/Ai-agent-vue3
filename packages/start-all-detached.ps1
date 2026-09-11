# 启动 v3agent 全部常驻服务（分离进程，避免 Bash 后台任务被每 turn 杀掉）
$root = 'D:\selfFile\python\vue3\v3agent\packages'

function Read-EnvFile($path) {
    $vars = @{}
    Get-Content $path -Encoding UTF8 | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $vars[$Matches[1]] = $Matches[2].Trim()
        }
    }
    return $vars
}

function Start-ServiceProcess($name, $wd, $cmd, $argList) {
    $out = Join-Path $wd 'dev-out.log'
    $err = Join-Path $wd 'dev-err.log'
    Write-Host "正在启动 $name ... 日志: $out / $err"
    Start-Process -FilePath $cmd -ArgumentList $argList -WorkingDirectory $wd -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
}

function Wait-Port {
    param($Port, $TimeoutSeconds = 180)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        try {
            $conn = New-Object System.Net.Sockets.TcpClient('localhost', $Port)
            if ($conn.Connected) {
                $conn.Close()
                return $true
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

$nestEnv = Read-EnvFile (Join-Path $root 'NestJS\.env')
$jwtSecret = $nestEnv['JWT_SECRET']
$serviceKey = $nestEnv['NESTJS_SERVICE_KEY']
$modelName = $nestEnv['MODEL_NAME']

$mvn = 'D:\maven\apache-maven-3.9.16\bin\mvn.cmd'

# 1. ai-service (6010)
Start-ServiceProcess 'ai-service' (Join-Path $root 'ai-service') 'powershell' @(
    '-Command', '& .\.venv\Scripts\activate; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 6010'
)

# 2. NestJS (6011)
Start-ServiceProcess 'NestJS' (Join-Path $root 'NestJS') 'cmd' @('/c', 'npm run start:dev')

# 3. my-vue-app-ts (6012)
Start-ServiceProcess 'my-vue-app-ts' (Join-Path $root 'my-vue-app-ts') 'cmd' @('/c', 'npm run dev')

# 4. ServerManegeUI (6013)
Start-ServiceProcess 'ServerManegeUI' (Join-Path $root 'ServerManegeUI') 'cmd' @('/c', 'npm run dev')

$mg = Join-Path $root 'model-gateway'
$env:DB_HOST = $nestEnv['DB_HOST']
$env:DB_PORT = $nestEnv['DB_PORT']
$env:DB_USERNAME = $nestEnv['DB_USERNAME']
$env:DB_PASSWORD = $nestEnv['DB_PASSWORD']
$env:DB_DATABASE = $nestEnv['DB_DATABASE']
$env:GATEWAY_SERVICE_KEY = $serviceKey
$env:JWT_SECRET = $jwtSecret
$env:CHANNEL_COMPANY_BASE_URL = 'http://172.18.200.114:3000/v1'
$env:CHANNEL_COMPANY_API_KEY  = 'sk-qX6O5yjHcWa48ZWjSXkxctZEmejZWOSy7Oasg3l1V5Y846XZ'
$env:CHANNEL_COMPANY_MODELS   = $modelName
$env:CHANNEL_BAILIAN_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
$env:CHANNEL_BAILIAN_API_KEY  = 'sk-7c6e65b4d4ee41eb89eaf59f6381edc3'
$env:CHANNEL_BAILIAN_MODELS   = 'qwen-plus,text-embedding-v3'

Start-ServiceProcess 'model-gateway' $mg $mvn @(
    '-Dmaven.repo.local=D:\maven\repository',
    'spring-boot:run',
    '-Dspring-boot.run.profiles=mysql',
    "-Dspring-boot.run.jvmArguments=-Dgateway.jwt.secret=$jwtSecret -Dgateway.service-key=$serviceKey"
)

# 6. rag-service (6016)
$rag = Join-Path $root 'rag-service'
Start-ServiceProcess 'rag-service' $rag $mvn @(
    '-Dmaven.repo.local=D:\maven\repository',
    'spring-boot:run',
    "-Dspring-boot.run.jvmArguments=-DGATEWAY_SERVICE_KEY=$serviceKey -DJWT_SECRET=$jwtSecret -DMODEL_CHANNEL_KEY=bailian -DVECTOR_DIMENSION=1024 -DVECTOR_MODE=memory"
)

Write-Host ''
Write-Host '等待 Java 服务就绪...'
if (-not (Wait-Port -Port 6015 -TimeoutSeconds 240)) {
    Write-Warning 'model-gateway (6015) 未在 240 秒内就绪，请检查 D:\selfFile\python\vue3\v3agent\packages\model-gateway\dev-err.log'
} else {
    Write-Host 'model-gateway (6015) 已就绪'
}

if (-not (Wait-Port -Port 6016 -TimeoutSeconds 240)) {
    Write-Warning 'rag-service (6016) 未在 240 秒内就绪，请检查 D:\selfFile\python\vue3\v3agent\packages\rag-service\dev-err.log'
} else {
    Write-Host 'rag-service (6016) 已就绪'
}

Write-Host ''
Write-Host '全部服务已分离启动，请等待 10-20 秒后访问:'
Write-Host '  业务端 http://localhost:6012'
Write-Host '  管理端 http://localhost:6013'
Write-Host '  NestJS  http://localhost:6011'
Write-Host '  ai-service http://localhost:6010'
Write-Host '  model-gateway http://localhost:6015'
Write-Host '  rag-service http://localhost:6016'
