Set-Location -Path $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " [DEBUG] Starte marimo Launch-Skript" -ForegroundColor Cyan
Write-Host " [DEBUG] PSScriptRoot: $PSScriptRoot" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan

# 1. Output-Limit & Port definieren
$env:MARIMO_OUTPUT_MAX_BYTES = "104857600"
$marimoPort = 2718
Write-Host "[1/8] Port: $marimoPort | MaxBytes: $env:MARIMO_OUTPUT_MAX_BYTES" -ForegroundColor Green

# 2. .env Datei laden
$envFile = "$PSScriptRoot\.env"
if (Test-Path $envFile) {
    Write-Host "[2/8] .env Datei gefunden und geladen." -ForegroundColor Green
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $key, $val = $line.Split("=", 2)
            [System.Environment]::SetEnvironmentVariable($key.Trim(), $val.Trim(), "Process")
        }
    }
} else {
    Write-Host "[2/8] Keine .env Datei vorhanden (übersprungen)." -ForegroundColor Yellow
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

if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
    Write-Host "[3/8] FEHLER: Kein Python Executable gefunden!" -ForegroundColor Red
    Pause
    Exit
} else {
    Write-Host "[3/8] Python Executable: $pythonExe" -ForegroundColor Green
}

# 4. marimo starten mit --watch
$portActive = (Get-NetTCPConnection -LocalPort $marimoPort -State Listen -ErrorAction SilentlyContinue)

if ($portActive) {
    Write-Host "[4/8] marimo lauscht bereits auf Port $marimoPort." -ForegroundColor Yellow
} else {
    Write-Host "[4/8] Starte marimo Prozess mit File-Watcher (--watch)..." -ForegroundColor Green

    $stdoutLog = "$PSScriptRoot\marimo_stdout.log"
    $stderrLog = "$PSScriptRoot\marimo_stderr.log"

    # CLI-Parameter inklusive --watch für automatisches Neuladen modifizierter .py Dateien
    $args = "-m marimo edit --watch --host 127.0.0.1 --port $marimoPort --headless --no-token"

    $proc = Start-Process -FilePath $pythonExe `
                          -ArgumentList $args `
                          -WorkingDirectory $PSScriptRoot `
                          -RedirectStandardOutput $stdoutLog `
                          -RedirectStandardError $stderrLog `
                          -PassThru

    Write-Host "      Prozess gestartet (PID: $($proc.Id))" -ForegroundColor DarkGray
}

# 5. Port-Check
Write-Host "[5/8] Warte auf Socket-Verbindung (127.0.0.1:$marimoPort)..." -ForegroundColor Green
$portOpen = $false

for ($i = 1; $i -le 30; $i++) {
    if ($proc -and $proc.HasExited) {
        Write-Host "      [!] Python-Prozess hat sich vorzeitig beendet (ExitCode: $($proc.ExitCode))" -ForegroundColor Red
        break
    }

    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect("127.0.0.1", $marimoPort, $null, $null)
    $success = $iar.AsyncWaitHandle.WaitOne(200, $false)

    if ($success -and $client.Connected) {
        $client.EndConnect($iar)
        $client.Close()
        $client.Dispose()
        $portOpen = $true
        Write-Host "      Verbindung hergestellt!" -ForegroundColor Green
        break
    }

    $client.Close()
    $client.Dispose()
    Start-Sleep -Milliseconds 200
}

if (-not $portOpen) {
    Write-Host "[5/8] FEHLER: Server konnte nicht erreicht werden!" -ForegroundColor Red
    Start-Sleep -Milliseconds 300

    if (Test-Path "$PSScriptRoot\marimo_stderr.log") {
        Write-Host "--- FEHLERMELDUNG AUS PYTHON (stderr) ---" -ForegroundColor Red
        Get-Content "$PSScriptRoot\marimo_stderr.log" | Write-Host -ForegroundColor Red
        Write-Host "-----------------------------------------" -ForegroundColor Red
    }
    Pause
    Exit
}

# 6. Firefox öffnen
$firefoxPath = "C:\Program Files\Mozilla Firefox\firefox.exe"
if (-not (Test-Path $firefoxPath)) {
    $firefoxPath = "C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
}

if (Test-Path $firefoxPath) {
    Write-Host "[6/8] Starte Firefox: $firefoxPath" -ForegroundColor Green
    Start-Process -FilePath $firefoxPath -ArgumentList "--new-window http://localhost:$marimoPort"
} else {
    Write-Host "[6/8] Firefox nicht gefunden, öffne Standard-URL..." -ForegroundColor Yellow
    Start-Process "http://localhost:$marimoPort"
}

# 7. Win32 User-API importieren
Write-Host "[7/8] Lade Win32-API für Fensterplatzierung..." -ForegroundColor Green
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
"@ -ErrorAction SilentlyContinue

# 8. Firefox-Fenster positionieren
Write-Host "[8/8] Suche Firefox-Fenster..." -ForegroundColor Green
$foundWindow = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Milliseconds 300
    $ffProc = Get-Process firefox -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } |
        Sort-Object StartTime -Descending |
        Select-Object -First 1

    if ($ffProc) {
        $hwnd = $ffProc.MainWindowHandle
        Write-Host "      Fenster Handle gefunden: $hwnd" -ForegroundColor DarkGray
        [Win32]::ShowWindow($hwnd, 9)       # SW_RESTORE
        [Win32]::SetWindowPos($hwnd, [IntPtr]::Zero, 0, 0, 1920, 1080, 0x0040)
        [Win32]::ShowWindow($hwnd, 3)       # SW_MAXIMIZE
        [Win32]::SetForegroundWindow($hwnd)
        $foundWindow = $true
        break
    }
}

if ($foundWindow) {
    Write-Host "Fertig! marimo läuft auf Monitor 1 mit Auto-Reload (--watch)." -ForegroundColor Cyan
} else {
    Write-Host "Fenster konnte nicht automatisch platziert werden (Browser läuft trotzdem)." -ForegroundColor Yellow
}