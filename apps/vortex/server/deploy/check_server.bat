@echo off
rem  Is the Vortex server up? Prints the addresses to give the gaming PCs and opens
rem  the admin panel. Pass "quiet" to skip opening the browser.
cd /d "%~dp0"
set "PORT=8787"
echo.
echo ---- Vortex server check --------------------------------------
curl -s -m 5 http://localhost:%PORT%/health >nul 2>&1
if errorlevel 1 (
    echo   STATUS : NOT RUNNING on port %PORT%
    echo   Look at data\server.log for the reason, or run start_server.bat
    echo ---------------------------------------------------------------
    if /i not "%~1"=="quiet" pause
    exit /b 1
)
for /f "delims=" %%H in ('curl -s -m 5 http://localhost:%PORT%/health') do set "HEALTH=%%H"
echo   STATUS : RUNNING   %HEALTH%
echo   Admin  : http://localhost:%PORT%/admin/      (on this PC)
echo   Status : http://localhost:%PORT%/status      (green = everything OK; open from any PC)
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /c:"IPv4"') do (
    for /f "tokens=* delims= " %%B in ("%%A") do echo   LAN    : http://%%B:%PORT%/admin/     ^<- gaming PCs use  ws://%%B:%PORT%
)
echo ---------------------------------------------------------------
if /i not "%~1"=="quiet" start "" "http://localhost:%PORT%/admin/"
exit /b 0
