# Beendet alle laufenden JupyterLab- und Notebook-Kernel-Prozesse
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match "jupyter-lab|jupyterlab" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "JupyterLab wurde sicher beendet." -ForegroundColor Yellow
