Set-Location -Path $PSScriptRoot

# 1. Lokales IPython-Verzeichnis im Projekt setzen
$env:IPYTHONDIR = "$PSScriptRoot\.ipython"

# 2. .env Datei laden (falls vorhanden)
$envFile = "$PSScriptRoot\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $val = $line.Split("=", 2)
            [System.Environment]::SetEnvironmentVariable($key.Trim(), $val.Trim(), "Process")
        }
    }
}

# 3. Python Executable finden
$pythonExe = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "$PSScriptRoot\venv\Scripts\python.exe"
}
if (-not (Test-Path $pythonExe)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonExe = $cmd.Source }
}

# 4. Prüfen, ob JupyterLab bereits läuft; sonst starten
$existingJupyter = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "jupyterlab|jupyter-lab" }

if (-not $existingJupyter) {
    Start-Process -FilePath $pythonExe -ArgumentList "-m jupyterlab --no-browser --port=8888" -WindowStyle Hidden
}

# Warten, bis Port 8888 antwortet
$portOpen = $false
for ($i = 0; $i -lt 25; $i++) {
    $tcp = Test-NetConnection -ComputerName "localhost" -Port 8888 -WarningAction SilentlyContinue
    if ($tcp.TcpTestSucceeded) {
        $portOpen = $true
        break
    }
    Start-Sleep -Milliseconds 400
}

# 5. Firefox öffnen
$firefoxPath = "C:\Program Files\Mozilla Firefox\firefox.exe"
if (-not (Test-Path $firefoxPath)) {
    $firefoxPath = "C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
}

Start-Process -FilePath $firefoxPath -ArgumentList "--new-window http://localhost:8888/lab"

# 6. Win32 User-API importieren (inkl. SW_RESTORE & Monitor-Handling)
Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
  }
"@

# 7. JupyterLab-Fenster suchen, ent-maximieren, auf Screen 1 (0,0) setzen und maximieren
$maxRetries = 25
$found = $false

for ($i = 0; $i -lt $maxRetries; $i++) {
    Start-Sleep -Milliseconds 400

    $ffProcs = Get-Process firefox -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowHandle -ne [IntPtr]::Zero -and $_.MainWindowTitle -match "JupyterLab"
    }

    if ($ffProcs) {
        $hwnd = $ffProcs[0].MainWindowHandle

        # 9 = SW_RESTORE (zwingend nötig, falls Fenster bereits auf Monitor 2 maximiert war)
        [Win32]::ShowWindow($hwnd, 9)
        Start-Sleep -Milliseconds 100

        # Koordinaten 0, 0 = Hauptbildschirm (Monitor 1)
        # 0x0040 = SWP_SHOWWINDOW
        [Win32]::SetWindowPos($hwnd, [IntPtr]::Zero, 0, 0, 1920, 1080, 0x0040)
        Start-Sleep -Milliseconds 100

        # 3 = SW_MAXIMIZE (jetzt auf Monitor 1 maximieren)
        [Win32]::ShowWindow($hwnd, 3)
        [Win32]::SetForegroundWindow($hwnd)

        $found = $true
        break
    }
}