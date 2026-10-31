@echo off
rem MeGaADesk - relay server (run on your VPS; pure stdlib). Open the port in the firewall.
cd /d "%~dp0"
set /p PORT=Relay port [7000]:
if "%PORT%"=="" set PORT=7000
python relay.py --port %PORT%
pause
