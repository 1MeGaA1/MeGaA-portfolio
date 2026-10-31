@echo off
rem  Start the Vortex server in the background (through the startup task if it is
rem  installed, otherwise in a visible window).
cd /d "%~dp0"
netstat -an | findstr "LISTENING" | findstr ":8787 " >nul 2>&1 && (echo Vortex server is already running. & pause & exit /b 0)
schtasks /query /tn "Vortex Server" >nul 2>&1
if errorlevel 1 (
    start "Vortex Server" cmd /k "%~dp0serve_forever.bat"
) else (
    schtasks /run /tn "Vortex Server" >nul
)
ping -n 7 127.0.0.1 >nul
call "%~dp0check_server.bat"
