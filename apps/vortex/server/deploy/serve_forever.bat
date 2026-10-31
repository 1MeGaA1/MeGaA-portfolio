@echo off
rem ============================================================
rem  Vortex server - keep-alive loop.
rem  Runs VortexServer.exe (or run_server.py when running from source) and starts
rem  it again 5 seconds after it ever exits or crashes. Task Scheduler runs THIS
rem  file at boot (see install_autostart.bat). Exit code 2 = port already in use
rem  (another copy is running) -> we stop instead of fighting over the port.
rem ============================================================
title Vortex Server
cd /d "%~dp0"
:loop
rem full path on purpose: cmd may not search the current folder for programs
rem (NoDefaultCurrentDirectoryInExePath), and Task Scheduler starts us from C:\Windows\system32
if exist "%~dp0VortexServer.exe" (
    "%~dp0VortexServer.exe" %*
) else (
    python "%~dp0run_server.py" %*
)
if %errorlevel%==2 (
    echo Another Vortex server already owns the port. Not restarting.
    exit /b 2
)
echo.
echo Vortex server stopped with code %errorlevel% - restarting in 5 seconds...
rem ping as a sleep: 'timeout' aborts when stdin is redirected (services, scripts)
ping -n 6 127.0.0.1 >nul
goto loop
