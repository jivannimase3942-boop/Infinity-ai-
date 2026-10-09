@echo off
setlocal enabledelayedexpansion
set "ROOT=%~dp0"

echo ============================================================
echo   Infinity AI - Private Offline AI Workspace
echo   "Your AI. Your files. Your machine."
echo ============================================================
echo.

set "OLLAMA_MODELS=%ROOT%ollama-models"
set "OLLAMA_HOST=127.0.0.1:11435"
set "OLLAMA_CONTEXT_LENGTH=4096"
set "INFINITY_OLLAMA_URL=http://127.0.0.1:11435"
set "PYTHONPATH=%ROOT%libs;%ROOT%app"
set "PYTHONDONTWRITEBYTECODE=1"

echo [1/4] Checking local AI environment...
netstat -ano | findstr "127.0.0.1:11435" | findstr LISTENING >nul
if %errorlevel%==0 (
  echo Local AI engine is already running on port 11435.
  goto ready
)

echo [2/4] Starting private AI engine...
start "" /min "%ROOT%bin\ollama\ollama.exe" serve

set /a tries=0
:wait
curl.exe -s http://127.0.0.1:11435 >nul 2>&1
if %errorlevel%==0 goto ready
set /a tries+=1
if %tries% GEQ 35 goto fail
timeout /t 1 >nul
goto wait

:ready
echo [3/4] AI Engine is ready.
echo [4/4] Launching Infinity AI Desktop Workspace...
cd /d "%ROOT%app"
"%ROOT%bin\python\python.exe" app.py
if errorlevel 1 (
  echo.
  echo The app closed with an error. Read the message above.
  pause
)
goto cleanup

:fail
echo.
echo Notice: Ollama did not respond on 127.0.0.1:11435 within timeout.
echo Starting Infinity AI in offline fallback mode...
cd /d "%ROOT%app"
"%ROOT%bin\python\python.exe" app.py
if errorlevel 1 (
  echo.
  echo The app closed with an error.
  pause
)

:cleanup
powershell -NoProfile -Command "Get-Process ollama -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '%ROOT%*' } | Stop-Process -Force"
exit /b 0