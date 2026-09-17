# 启动 v3agent 全链路服务(分离进程,避免 Bash 后台任务被每 turn 杀掉)
$root = "D:\selfFile\python\vue3\v3agent\packages"

function Start-ServiceProcess($name, $wd, $cmd, $argList) {
    $out = Join-Path $wd 'dev-out.log'
    $err = Join-Path $wd 'dev-err.log'
    Write-Host "正在启动 $name ... 日志: $out / $err"
    Start-Process -FilePath $cmd -ArgumentList $argList -WorkingDirectory $wd -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
}

# 1. ai-service (26010)
Start-ServiceProcess "ai-service" (Join-Path $root 'ai-service') "powershell" @(
    '-Command', '& .\.venv\Scripts\activate; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 26010'
)

# 2. NestJS (26011)
Start-ServiceProcess "NestJS" (Join-Path $root 'NestJS') 'cmd' @('/c', 'npm run start:dev')

# 3. my-vue-app-ts (26012)
Start-ServiceProcess "my-vue-app-ts" (Join-Path $root 'my-vue-app-ts') 'cmd' @('/c', 'npm run dev')

# 4. ServerManegeUI (26013)
Start-ServiceProcess "ServerManegeUI" (Join-Path $root 'ServerManegeUI') 'cmd' @('/c', 'npm run dev')

# 5. model-gateway (26015) - mysql profile
$mg = Join-Path $root 'model-gateway'
Start-ServiceProcess "model-gateway" $mg 'powershell' @('-File', (Join-Path $mg 'run-mysql.ps1'))

Write-Host "全部服务已分离启动,请等待 20-40 秒后访问:"
Write-Host "  业务端 http://localhost:26012"
Write-Host "  管理端 http://localhost:26013"
Write-Host "  NestJS http://localhost:26011"
Write-Host "  ai-service http://localhost:26010"
Write-Host "  model-gateway http://localhost:26015"
