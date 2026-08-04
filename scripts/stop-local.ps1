$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root '.runtime'

function Stop-ProcessTree([int]$ProcessId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { Stop-ProcessTree $child.ProcessId }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($process -and ($process.CommandLine -like "*$root*" -or $process.Name -in @('npm.cmd','node.exe','python.exe','cmd.exe'))) {
        Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue
    }
}

foreach ($name in @('frontend','backend')) {
    $pidFile = Join-Path $runtime "$name.pid"
    if (Test-Path $pidFile) {
        $savedPid = [int](Get-Content $pidFile)
        Stop-ProcessTree $savedPid
        Remove-Item -LiteralPath $pidFile -Force
    }
}
Write-Host 'Banana Slides local services stopped.'
