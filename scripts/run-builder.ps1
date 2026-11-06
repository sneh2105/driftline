# Autonomous builder loop. Run from the main repo (D:\projects\driftline).
param([int]$Rounds = 8)
Set-Location (Join-Path $PSScriptRoot "..")
$prompt = Get-Content scripts\builder-prompt.txt -Raw
New-Item -ItemType Directory -Force logs | Out-Null
for ($i = 1; $i -le $Rounds; $i++) {
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
  Write-Host "=== builder round $i/$Rounds ($stamp)"
  $prompt | claude -p --permission-mode acceptEdits --max-turns 80 2>&1 | Tee-Object -FilePath "logs\builder-session-$i.raw.log"
  $br = (git branch --show-current).Trim()
  "[$stamp] round $i on $br`n$(git log -1 --stat --format='%h %s')`n" | Add-Content logs\rounds.raw.log
  if ($br -eq "feat/auto-build") { git push -u origin HEAD } else { Write-Host "not on feat/auto-build ($br), skipping push" }
  if (-not (Select-String -Path TASKS.md -Pattern '^- \[ \]' -Quiet)) { Write-Host "TASKS.md empty, builder done"; break }
}
