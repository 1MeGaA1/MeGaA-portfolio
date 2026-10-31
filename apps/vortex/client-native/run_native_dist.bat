@echo off
rem Keep the Vortex kiosk running: restart it whenever it exits, unless a staff member closed
rem it with the exit PIN (exit code 0). Full path: cmd may not search the current folder.
cd /d "%~dp0"
:loop
"%~dp0VortexClientNative.exe"
if %errorlevel%==0 goto end
ping -n 3 127.0.0.1 >nul
goto loop
:end
