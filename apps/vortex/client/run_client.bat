@echo off
rem Vortex kiosk watchdog: restarts the client whenever it exits, unless an admin
rem exited it on purpose (exit code 0).
cd /d "%~dp0"
:loop
python run_client.py
if %errorlevel%==0 goto end
timeout /t 2 /nobreak >nul
goto loop
:end
