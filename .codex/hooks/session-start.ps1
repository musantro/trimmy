$ErrorActionPreference = "Stop"

$repoRoot = (& git rev-parse --show-toplevel).Trim()
$script = Join-Path $repoRoot ".codex/hooks/session-start.sh"

$bashCandidates = @(
    (Join-Path $env:ProgramFiles "Git/bin/bash.exe")
)

if ($env:ProgramFiles -ne ${env:ProgramFiles(x86)}) {
    $bashCandidates += Join-Path ${env:ProgramFiles(x86)} "Git/bin/bash.exe"
}

$bash = $bashCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $bash) {
    $bash = (Get-Command bash -ErrorAction Stop).Source
}

& $bash $script
exit $LASTEXITCODE
