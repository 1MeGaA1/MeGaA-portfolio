@echo off
rem  Allow the gaming PCs to reach the Vortex server (TCP 8787) through Windows Firewall.
rem  Run once, as Administrator (right-click -> Run as administrator).
net session >nul 2>&1 || (echo Please run this file as Administrator. & pause & exit /b 1)
netsh advfirewall firewall delete rule name="Vortex Server" >nul 2>&1
netsh advfirewall firewall add rule name="Vortex Server" dir=in action=allow protocol=TCP localport=8787 profile=any
if errorlevel 1 (echo FAILED to add the firewall rule. & pause & exit /b 1)
echo.
echo Firewall rule "Vortex Server" added: TCP 8787 inbound allowed.
pause
