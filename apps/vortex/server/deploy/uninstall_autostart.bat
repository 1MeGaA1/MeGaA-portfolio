@echo off
rem  Stop the Vortex server and remove it from Windows startup. Run as Administrator.
net session >nul 2>&1 || (echo Please run this file as Administrator. & pause & exit /b 1)
schtasks /end /tn "Vortex Server" >nul 2>&1
schtasks /delete /tn "Vortex Server" /f >nul 2>&1
taskkill /f /im VortexServer.exe >nul 2>&1
echo Vortex server stopped and removed from startup.
pause
