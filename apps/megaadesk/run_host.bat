@echo off
rem MeGaADesk - start the host (the PC being controlled). Pure stdlib, no installs.
cd /d "%~dp0"
echo ============================================
echo   MeGaADesk Host
echo ============================================
echo   1) LAN       (viewer connects directly)
echo   2) Internet  (via your relay / VPS)
echo.
set /p MODE=Choose 1 or 2:
set /p PW=Session password:
if "%MODE%"=="2" goto relay

set /p PORT=Listen port [7777]:
if "%PORT%"=="" set PORT=7777
echo.
echo Tell the viewer your LAN IP (run ipconfig) and port %PORT%.
python host.py --password "%PW%" --listen --port %PORT%
goto end

:relay
set /p RELAY=Relay host:port (e.g. 203.0.113.9:7000):
set /p ID=This PC's ID (e.g. MYPC01):
echo.
echo Registering as '%ID%' on %RELAY% ...
python host.py --password "%PW%" --relay %RELAY% --id %ID%

:end
pause
