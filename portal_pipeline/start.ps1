param(
    [Parameter(Mandatory = $true)] [string] $Source,
    [int] $Port = 8766
)
$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
if (-not (Test-Path -LiteralPath (Join-Path $sourcePath '_Reference\Resume_Content_Master.json'))) {
    throw 'Source must be the existing Resume repository.'
}
py -B (Join-Path $PSScriptRoot 'server.py') --source $sourcePath --port $Port
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
