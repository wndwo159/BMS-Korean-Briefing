# Runs without a console; never changes or injects into a BMS executable.
$ErrorActionPreference = 'Stop'
$base = $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $base 'install.json') -Raw | ConvertFrom-Json
$root = [IO.Path]::GetFullPath($manifest.bms_root).TrimEnd('\')
$sha = [Security.Cryptography.SHA256]::Create()
$id = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($base.ToLowerInvariant())))).Replace('-','')
$mutex = New-Object Threading.Mutex($false, "Local\BMSKRLauncherWatch-$id")
if (-not $mutex.WaitOne(0)) { $mutex.Dispose(); exit }
$exe = Join-Path $base 'BMS-Korean-Briefing.exe'
$log = Join-Path $base 'data\launcher-watch.log'
try {
 Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Launcher detection started"
 while ($true) {
  try {
   $manifest = Get-Content -LiteralPath (Join-Path $base 'install.json') -Raw | ConvertFrom-Json
   if ($manifest.launch_mode -eq 'disabled') { break }
   $processes = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%Launcher%' OR Name = 'Falcon BMS.exe' OR Name = 'BMS-Korean-Briefing.exe'")
   $active = @($processes | Where-Object {
    $_.ExecutablePath -and (
     $_.ExecutablePath -ieq (Join-Path $root 'Bin\x64\Falcon BMS.exe') -or
     ($_.ExecutablePath.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase) -and $_.Name -match 'launcher')
    )
   })
   $service = @($processes | Where-Object { $_.ExecutablePath -ieq $exe })
   if ($active.Count -gt 0 -and $service.Count -eq 0) {
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Detected: $($active.Name -join ', '); attaching briefing service"
    Start-Process -FilePath $exe -ArgumentList '--attach-bms' -WorkingDirectory $base -WindowStyle Hidden
   }
  } catch {
   Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) $($_.Exception.Message)"
  }
  Start-Sleep -Seconds 2
 }
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
