param(
    [int]$BackendPort = 5011,
    [int]$FrontendPort = 3011
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root '.runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null

foreach ($port in @($BackendPort, $FrontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Stop the existing service or choose another port."
    }
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Python environment is missing. Run: uv sync --extra test' }
if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) { throw 'Frontend dependencies are missing. Run: cd frontend; npm ci' }

$backend = Start-Process -FilePath $python -ArgumentList 'app.py' `
    -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtime 'backend.stdout.log') `
    -RedirectStandardError (Join-Path $runtime 'backend.stderr.log')
$env:VITE_PORT = [string]$FrontendPort
$env:VITE_BACKEND_PORT = [string]$BackendPort
$frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1','--port',[string]$FrontendPort `
    -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtime 'frontend.stdout.log') `
    -RedirectStandardError (Join-Path $runtime 'frontend.stderr.log')

Set-Content -Encoding ascii (Join-Path $runtime 'backend.pid') $backend.Id
Set-Content -Encoding ascii (Join-Path $runtime 'frontend.pid') $frontend.Id

$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$BackendPort/ready" -TimeoutSec 2
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    throw "Backend did not become ready. See $runtime\backend.stderr.log"
}
Write-Host "Banana Slides is ready: http://127.0.0.1:$FrontendPort"
Write-Host "Health: http://127.0.0.1:$BackendPort/ready"
