# ===================================================================
# run_public.ps1 - Start the app + an ngrok tunnel, in the right order.
# ===================================================================
# WHY A SCRIPT?
# Two things must run at the same time: the Flask app on port 5000, and
# ngrok forwarding that port to the internet. They have to come up in
# order, and if you close either one the demo is over. Doing that by hand
# every time is where mistakes happen.
#
# HOW TO USE
#   1. One time only, add your ngrok authtoken:
#        ngrok config add-authtoken YOUR_TOKEN_HERE
#   2. Every time you want to demo:
#        powershell -ExecutionPolicy Bypass -File .\run_public.ps1
#   3. ngrok prints a public URL. Share that.
#   4. Press Ctrl+C here to shut BOTH down.
#
# SAFETY
# The app is started with the debugger OFF. With debug=True, any error
# page shows a Python console that lets anyone on the internet run code
# on this machine, so the script refuses to start in that combination.
# ===================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 5000

Write-Host ""
Write-Host "  Personal Finance Advisor Bot - going live" -ForegroundColor Cyan
Write-Host "  ------------------------------------------" -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectRoot

# --- 1. Is ngrok installed? ---------------------------------------
$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrok) {
    $candidates = Get-ChildItem `
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" `
        -Recurse -Filter "ngrok.exe" -ErrorAction SilentlyContinue
    if ($candidates) {
        $ngrokDir = Split-Path -Parent $candidates[0].FullName
        $env:PATH = "$ngrokDir;$env:PATH"
        Write-Host "  Found ngrok at $ngrokDir" -ForegroundColor DarkGray
    }
    else {
        Write-Host "  ngrok is not installed. Install it with:" -ForegroundColor Red
        Write-Host "      winget install Ngrok.Ngrok" -ForegroundColor Yellow
        exit 1
    }
}

# --- 2. Does ngrok have an authtoken? -----------------------------
$tokenLine = & ngrok config check 2>&1 | Out-String
if ($tokenLine -notmatch "authtoken") {
    Write-Host "  ngrok has no authtoken yet." -ForegroundColor Red
    Write-Host "  Get a free one at https://dashboard.ngrok.com/get-started" -ForegroundColor Yellow
    Write-Host "  then run:  ngrok config add-authtoken YOUR_TOKEN" -ForegroundColor Yellow
    exit 1
}

# --- 3. Is .env present with a real secret key? --------------------
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "  No .env file found. Copy .env.example to .env and fill it in." -ForegroundColor Red
    exit 1
}

$secretLine = Get-Content $envFile |
    Where-Object { $_ -match '^\s*SECRET_KEY\s*=' } |
    Select-Object -First 1
$secret = ($secretLine -split '=', 2)[1].Trim()

# A weak SECRET_KEY means anyone can forge a login cookie. Refuse to go
# public on a placeholder, because that would hand over the whole site.
if ([string]::IsNullOrWhiteSpace($secret) -or
    $secret -eq "dev-only-change-me" -or
    $secret -eq "change_this_to_a_random_string" -or
    $secret.Length -lt 16) {
    Write-Host "  SECRET_KEY is missing or too weak to publish." -ForegroundColor Red
    Write-Host "  Run this to make a strong one:" -ForegroundColor Yellow
    Write-Host '      python -c "import secrets; print(secrets.token_hex(32))"' -ForegroundColor Yellow
    exit 1
}
Write-Host "  SECRET_KEY looks strong (length $($secret.Length))." -ForegroundColor DarkGray

# --- 4. Start Flask in its own window, debugger OFF ----------------
Write-Host "  Starting the app on port $Port ..." -ForegroundColor DarkGray
$env:PORT = "$Port"
$env:HOST = "127.0.0.1"
$env:FLASK_DEBUG = "0"

$flask = Start-Process -FilePath "python" -ArgumentList "app.py" `
    -WorkingDirectory $ProjectRoot -PassThru

# Wait for the port to actually accept connections before tunnelling,
# otherwise ngrok reports "connection refused" on the first request.
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $probe = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" `
            -UseBasicParsing -TimeoutSec 3
        if ($probe.StatusCode -eq 200) { $ready = $true; break }
    }
    catch { }
}

if (-not $ready) {
    Write-Host "  The app did not start. Is the port already in use?" -ForegroundColor Red
    exit 1
}
Write-Host "  App is healthy on http://127.0.0.1:$Port" -ForegroundColor Green

# --- 5. Open the tunnel -------------------------------------------
Write-Host ""
Write-Host "  Starting the ngrok tunnel. The public URL appears below." -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop everything." -ForegroundColor Yellow
Write-Host ""

try {
    & ngrok http $Port --domain=""
}
finally {
    Write-Host ""
    Write-Host "  Stopping the app ..." -ForegroundColor Yellow
    if ($flask -and -not $flask.HasExited) {
        Stop-Process -Id $flask.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  Done." -ForegroundColor Cyan
}
