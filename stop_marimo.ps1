# Beendet alle laufenden marimo-Server und zugehörigen Prozesse
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "marimo.*(edit|run)" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "marimo wurde sicher beendet." -ForegroundColor Yellow