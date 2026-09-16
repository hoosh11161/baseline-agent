param(
    [string]$Model = "VLMGPT5Config",
    [int]$RunTimes = 5,
    [string]$Config = "config.toml"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvExe = $uvCommand.Source
} else {
    $uvExe = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe"
}
if (-not (Test-Path -LiteralPath $uvExe)) {
    throw "uv was not found. Install it with: winget install --id astral-sh.uv --exact"
}

if (-not (Test-Path -LiteralPath $Config)) {
    Copy-Item -LiteralPath "config.toml.example" -Destination $Config
    Write-Host "Created $Config from config.toml.example"
}

& $uvExe run python scripts/generate_pb2.py
if ($LASTEXITCODE -ne 0) { throw "protobuf generation failed" }

& $uvExe run python scripts/preflight.py
if ($LASTEXITCODE -ne 0) { throw "preflight found a hard failure" }

& $uvExe run arenaagent --agent_name preliminary_baseline_agent --config $Config --vlm_model $Model --run_times $RunTimes
exit $LASTEXITCODE
