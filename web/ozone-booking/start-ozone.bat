@echo off
title Ozone Studios - Local Server
cd /d "%~dp0"

echo.
echo ============================================
echo   OZONE STUDIOS  -  LOCAL DEV SERVER
echo ============================================
echo.
echo   Public site:  http://localhost:5174/
echo   Admin panel:  http://localhost:5174/admin/index.html
echo.
echo   Keep this window open while you use the site.
echo   Close it (or press Ctrl+C) to stop the server.
echo.
echo ============================================
echo.

REM Open the browser after a 2-second delay so the server has time to start.
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5174/"

REM Try Python first (most reliable on Windows). 'py' launcher comes with the
REM official installer; 'python' is the PATH fallback.
where py >nul 2>nul
if %errorlevel%==0 (
  py -m http.server 5174
  goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -m http.server 5174
  goto :end
)

REM Fallback to Node.js / npx if Python isn't installed.
where npx >nul 2>nul
if %errorlevel%==0 (
  npx -y http-server . -p 5174 -c-1 --silent
  goto :end
)

echo.
echo --------------------------------------------
echo   ERROR: No web server runtime found.
echo --------------------------------------------
echo.
echo   This launcher needs either Python or Node.js.
echo   Install one of these and double-click the .bat
echo   again:
echo.
echo     Python:   https://www.python.org/downloads/
echo               (during install, check "Add Python to PATH")
echo.
echo     Node.js:  https://nodejs.org/
echo               (the LTS version is fine)
echo.
echo --------------------------------------------
echo.
pause

:end
