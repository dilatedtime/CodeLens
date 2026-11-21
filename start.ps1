$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$runtime = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    python -m venv (Join-Path $backendRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python environment' }
}
& $runtime -m pip install -r (Join-Path $backendRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
Push-Location $backendRoot
try {
    & $runtime -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
} finally { Pop-Location }
Push-Location $frontendRoot
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
$apiProcess = Start-Process -FilePath $runtime -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru
$nodePath = (Get-Command node.exe).Source
$vitePath = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'
$uiProcess = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'),'preview','--host','127.0.0.1','--port','4173','--strictPort') -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru
Write-Host 'CodeLens: http://127.0.0.1:4173'
Write-Host "API PID: $($apiProcess.Id), UI PID: $($uiProcess.Id)"
Write-Host 'Press Enter to stop the two processes started by this script.'
try { Read-Host | Out-Null } finally {
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
    if (-not $uiProcess.HasExited) { Stop-Process -Id $uiProcess.Id }
}
