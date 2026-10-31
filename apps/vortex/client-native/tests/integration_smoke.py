"""In-process test of the native Controller against the live server (no GUI window needed).
Verifies: connect -> welcome, login -> sessionChanged, staff topup -> sessionChanged,
staff end -> sessionEnded, staff restart -> app.exit(3)."""
import json, os, sys, threading, time, urllib.request
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
NAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(NAT)); sys.path.insert(0, str(NAT.parent / "client"))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from vortex_client import config as vc
CFG = NAT / "client.json"
vc.CONFIG_PATH = CFG; vc.CATALOG_PATH = NAT / "catalog.json"
NAME = "NATIVE-TEST-%d" % os.getpid()
json.dump({"server":"ws://127.0.0.1:8787","station_name":NAME,"station_key":"","fullscreen":False,
           "kiosk":False,"block_alt_tab_in_session":False,"local_exit_pin":"","debug":True}, open(CFG,"w"))
from vortex_client.config import load_config
from vortex_native.controller import Controller

API = "http://127.0.0.1:8787/api"
def api(path, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API+path, data=data, method=method)
    req.add_header("Content-Type","application/json")
    if token: req.add_header("Authorization","Bearer "+token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return json.load(r), 200
    except urllib.error.HTTPError as e:
        return None, e.code

token = api("/auth/login","POST",{"username":"admin","password":"admin"})[0]["token"]
for s in api("/stations", token=token)[0]["stations"]:
    if s["name"] == NAME: api(f"/stations/{s['id']}","DELETE",token=token)
m = [x for x in api("/members", token=token)[0]["members"] if x["username"]=="nova_rider"]
mid = m[0]["id"] if m else api("/members","POST",{"email":"nova@vortex.gg","password":"secret","username":"nova_rider"},token)[0]["id"]
# ensure member is free and has time
for s in api("/sessions?active=true", token=token)[0]["sessions"]:
    if s.get("member") and s["member"]["id"]==mid: api(f"/stations/{s['station']['id']}/session","DELETE",token=token)
api(f"/members/{mid}/topup","POST",{"seconds":3600,"amount":2000},token)

app = QGuiApplication(sys.argv)
cfg = load_config()
ctrl = Controller(cfg, app)
events = {"welcome":0,"session":[],"ended":[]}
ctrl.welcomeReceived.connect(lambda s: events.__setitem__("welcome", events["welcome"]+1))
ctrl.sessionChanged.connect(lambda s: events["session"].append(s["remaining_seconds"] if s else None))
ctrl.sessionEnded.connect(lambda r,m: events["ended"].append(r))
ctrl.loginResult.connect(lambda ok,e,m: print(f"   loginResult ok={ok} {m}", flush=True))

# drive the scenario from a worker thread; Qt delivers signals to the main loop
result = {"code": None}
def scenario():
    try:
        ctrl.link.start()
        for _ in range(20):
            time.sleep(0.5)
            if ctrl.link.online: break
        st = [s for s in api("/stations", token=token)[0]["stations"] if s["name"]==NAME]
        sid = st[0]["id"] if st else None
        print(f">> online={ctrl.link.online} sid={sid} welcome={events['welcome']}", flush=True)
        ctrl.login("nova@vortex.gg","secret")
        time.sleep(2)
        print(f">> after login, sessions seen: {events['session']}", flush=True)
        api(f"/members/{mid}/topup","POST",{"seconds":600},token)      # staff top-up
        time.sleep(2)
        print(f">> after topup, sessions seen: {events['session']}", flush=True)
        api(f"/stations/{sid}/session","DELETE",token=token)           # staff end
        time.sleep(2)
        print(f">> ended events: {events['ended']}", flush=True)
        # restart command -> controller.quit(3) -> app.exit(3)
        api(f"/stations/{sid}/command","POST",{"name":"restart"},token)
    except Exception as e:
        print("scenario error", e, flush=True)

threading.Thread(target=scenario, daemon=True).start()
# safety: quit after 20s if restart didn't
QTimer.singleShot(20000, lambda: app.exit(99))
code = app.exec()
print(">> app exit code:", code)
login_ok = any(v == 3600 for v in events["session"])
topup_ok = any((v or 0) >= 4100 for v in events["session"])
ended_ok = "admin" in events["ended"]
restart_ok = code == 3
print(f">> RESULT login={login_ok} topup={topup_ok} ended={ended_ok} restart_exit={restart_ok}")
sys.exit(0 if (login_ok and topup_ok and ended_ok and restart_ok) else 1)
