param(
    [string[]]$Models = @("VLMGPT5Config", "VLMGPT410414Config", "VLMQwen3VLPlus"),
    [int]$RunTimes = 3,
    [string]$Config = "config.toml"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

foreach ($model in $Models) {
    Write-Host "Running official episodes for model: $model"
    & (Join-Path $PSScriptRoot "run_preliminary.ps1") -Model $model -RunTimes $RunTimes -Config $Config
    if ($LASTEXITCODE -ne 0) { throw "Model run failed: $model" }
}

uv run python scripts/model_benchmark.py
exit $LASTEXITCODE
