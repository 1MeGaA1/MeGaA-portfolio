VORTEX SERVER - counter / server PC
====================================
Nothing to install: VortexServer.exe is self-contained (no Python needed).

FIRST TIME (as Administrator):
  1. open_firewall.bat       allow TCP 8787 through Windows Firewall
  2. install_autostart.bat   start with Windows + keep alive, starts it now too
  3. check_server.bat        shows status + the LAN address for the gaming PCs

Admin panel : http://<this-pc-ip>:8787/admin/    login admin / admin
Status page : http://<this-pc-ip>:8787/status    big green ALL SYSTEMS OK, or what is wrong (no login)
Change the password and the kiosk exit PIN in Settings before opening day.

Data        : data\vortex.db (database), data\media (pictures), data\server.log
Back up     : the whole data\ folder. Stop the server first (stop_server.bat).
Settings    : data\server.json (port, cafe name, currency). Restart after editing.

Gaming PCs  : client.json -> "server": "ws://<this-pc-ip>:8787"

Day to day  : check_server.bat / start_server.bat / stop_server.bat
Remove      : uninstall_autostart.bat
