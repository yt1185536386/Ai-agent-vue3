# 启动 v3agent 全部常驻服务（分离进程，避免 Bash 后台任务被每 turn 杀掉）
$root = 'D:\selfFile\python\vue3\v3agent\packages'

# ========== 0. 清理残留进程（治本：防止 watch 僵尸进程抢端口） ==========
# 历史教训：只杀监听端口的子进程会让 nest --watch / uvicorn --reload 的
# 父进程存活并自动重拉实例，新旧互抢导致 EADDRINUSE 死循环。
$ports = @(26010, 26011, 26012, 26013, 26015, 26016)

# 0a. 杀掉当前占用这些端口的进程树
foreach ($p in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Write-Host "清理端口 $p 占用进程 PID=$($c.OwningProcess)"
        & taskkill /PID $c.OwningProcess /T /F | Out-Null
    }
}

# 0b. 杀掉本项目残留的 node(nest --watch / vite / npm 子进程)、
#     python(uvicorn --reload 父进程)、java(spring-boot:run)
$patterns = @(
    @{ Name = 'node';   Like = '*v3agent*packages*' },
    @{ Name = 'python'; Like = '*uvicorn*app.main*' },
    @{ Name = 'java';   Like = '*v3agent*' },
    @{ Name = 'cmd';    Like = '*spring-boot:run*' }
)
foreach ($pat in $patterns) {
    Get-CimInstance Win32_Process -Filter "Name='$($pat.Name).exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like $pat.Like } |
        ForEach-Object {
            Write-Host "清理残留进程 $($pat.Name).exe PID=$($_.ProcessId)"
            & taskkill /PID $_.ProcessId /T /F | Out-Null
        }
}
Start-Sleep -Seconds 2

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

# 1. ai-service (26010)
Start-ServiceProcess 'ai-service' (Join-Path $root 'ai-service') 'powershell' @(
    '-Command', '& .\.venv\Scripts\activate; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 26010'
)

# 2. NestJS (26011)
Start-ServiceProcess 'NestJS' (Join-Path $root 'NestJS') 'cmd' @('/c', 'npm run start:dev')

# 3. my-vue-app-ts (26012)
Start-ServiceProcess 'my-vue-app-ts' (Join-Path $root 'my-vue-app-ts') 'cmd' @('/c', 'npm run dev')

# 4. ServerManegeUI (26013)
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

# 6. rag-service (26016)
$rag = Join-Path $root 'rag-service'
Start-ServiceProcess 'rag-service' $rag $mvn @(
    '-Dmaven.repo.local=D:\maven\repository',
    'spring-boot:run',
    "-Dspring-boot.run.jvmArguments=-DGATEWAY_SERVICE_KEY=$serviceKey -DJWT_SECRET=$jwtSecret -DMODEL_CHANNEL_KEY=bailian -DVECTOR_DIMENSION=1024 -DVECTOR_MODE=memory"
)

Write-Host ''
Write-Host '等待 Java 服务就绪...'
if (-not (Wait-Port -Port 26015 -TimeoutSeconds 240)) {
    Write-Warning 'model-gateway (26015) 未在 240 秒内就绪，请检查 D:\selfFile\python\vue3\v3agent\packages\model-gateway\dev-err.log'
} else {
    Write-Host 'model-gateway (26015) 已就绪'
}

if (-not (Wait-Port -Port 26016 -TimeoutSeconds 240)) {
    Write-Warning 'rag-service (26016) 未在 240 秒内就绪，请检查 D:\selfFile\python\vue3\v3agent\packages\rag-service\dev-err.log'
} else {
    Write-Host 'rag-service (26016) 已就绪'
}

Write-Host ''
Write-Host '全部服务已分离启动，请等待 10-20 秒后访问:'
Write-Host '  业务端 http://localhost:26012'
Write-Host '  管理端 http://localhost:26013'
Write-Host '  NestJS  http://localhost:26011'
Write-Host '  ai-service http://localhost:26010'
Write-Host '  model-gateway http://localhost:26015'
Write-Host '  rag-service http://localhost:26016'
