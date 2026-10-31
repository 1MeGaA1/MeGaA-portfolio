@echo off
rem ============================================================
rem  Vortex - one click: start the server (if needed) + open the admin panel
rem ============================================================
title Vortex Launcher
cd /d "%~dp0server"

rem Is the Vortex server already listening on port 8787?
netstat -an | findstr "LISTENING" | findstr ":8787" >nul 2>&1
if errorlevel 1 (
    echo Starting the Vortex server in its own window...
    start "Vortex Server" cmd /k python run_server.py
    echo Waiting a few seconds for it to come up...
    timeout /t 4 /nobreak >nul
) else (
    echo Vortex server is already running.
)

echo Opening the admin panel in your browser...
start "" "http://localhost:8787/admin/"
exit
