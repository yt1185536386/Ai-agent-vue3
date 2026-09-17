$base = 'D:\selfFile\python\vue3\v3agent\packages'

Start-Process -FilePath "$base\ai-service\.venv\Scripts\python.exe" `
  -ArgumentList '-m','uvicorn','app.main:app','--reload','--host','127.0.0.1','--port','26010' `
  -WorkingDirectory "$base\ai-service" `
  -RedirectStandardOutput "$base\ai-service\dev-out.log" `
  -RedirectStandardError  "$base\ai-service\dev-err.log" `
  -WindowStyle Hidden

Start-Process -FilePath 'npm.cmd' `
  -ArgumentList 'run','start:dev' `
  -WorkingDirectory "$base\NestJS" `
  -RedirectStandardOutput "$base\NestJS\dev-out.log" `
  -RedirectStandardError  "$base\NestJS\dev-err.log" `
  -WindowStyle Hidden

Start-Process -FilePath 'npm.cmd' `
  -ArgumentList 'run','dev' `
  -WorkingDirectory "$base\my-vue-app-ts" `
  -RedirectStandardOutput "$base\my-vue-app-ts\dev-out.log" `
  -RedirectStandardError  "$base\my-vue-app-ts\dev-err.log" `
  -WindowStyle Hidden

Write-Output 'started'
11111111111111111111111111111111111111111111111