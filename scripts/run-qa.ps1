# Autonomous QA loop. Run from the Codex worktree (D:\projects\driftline-qa).
param([int]$Rounds = 8)
Set-Location (Join-Path $PSScriptRoot "..")
$prompt = Get-Content scripts\qa-prompt.txt -Raw
New-Item -ItemType Directory -Force logs | Out-Null
for ($i = 1; $i -le $Rounds; $i++) {
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
  Write-Host "=== qa round $i/$Rounds ($stamp)"
  $prompt | codex exec --full-auto - 2>&1 | Tee-Object -FilePath "logs\qa-session-$i.raw.log"
  $br = (git branch --show-current).Trim()
  "[$stamp] round $i on $br`n$(git log -1 --stat --format='%h %s')`n" | Add-Content logs\rounds.raw.log
  if ($br -eq "qa/first-pass") { git push -u origin HEAD } else { Write-Host "not on qa/first-pass ($br), skipping push" }
  if (-not (Select-String -Path tests\qa\QA_PLAN.md -Pattern '^- \[ \]' -Quiet)) { Write-Host "QA plan complete"; break }
}
