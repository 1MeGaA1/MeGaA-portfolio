@echo off
rem Vortex native kiosk watchdog: relaunch unless an admin exited (code 0).
cd /d "%~dp0"
:loop
python run_native.py
if %errorlevel%==0 goto end
timeout /t 2 /nobreak >nul
goto loop
:end
