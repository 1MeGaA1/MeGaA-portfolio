/* vortex-bridge.js — the page's single door to the outside world.
 *
 * Kiosk mode  (index.html?kiosk=1, inside pywebview): every call goes to Python via
 *              window.pywebview.api.*; Python pushes events with Vortex._dispatch(...).
 * Browser mode (plain browser, for development/demo): the page opens the station
 *              WebSocket itself and speaks the same protocol as the Python client;
 *              launching is simulated.
 */
(function () {
  'use strict';

  const listeners = {};
  const params = new URLSearchParams(location.search);
  // Kiosk mode = running inside WebView2 (pywebview). WebView2 always exposes window.chrome.webview;
  // plain browsers never do. ?kiosk=1 / ?kiosk=0 can force either mode when served over http.
  const KIOSK = params.get('kiosk') === '1'
    || (params.get('kiosk') !== '0' && (!!window.pywebview || !!(window.chrome && window.chrome.webview)));

  const Vortex = (window.Vortex = {
    version: '0.1.0',
    mode: KIOSK ? 'kiosk' : 'browser',
    ready: false,
    state: { online: false, station: null, config: null, session: null, client: null, peripherals: null },

    on(event, fn) { (listeners[event] = listeners[event] || []).push(fn); },
    _emit(event, data) {
      (listeners[event] || []).forEach((fn) => { try { fn(data); } catch (e) { console.error('[vortex]', event, e); } });
    },
    _dispatch(event, data) {
      data = data || {};
      if (event === 'welcome' || event === 'state') {
        Object.assign(Vortex.state, data);
        Vortex.state.online = data.online !== false;
      } else if (event === 'session_update') {
        Vortex.state.session = data.session || null;
        Vortex.state.online = true;
      } else if (event === 'session_ended') {
        Vortex.state.session = null;
      } else if (event === 'link') {
        Vortex.state.online = !!data.online;
      } else if (event === 'rejected') {
        Vortex.state.online = false;
      }
      Vortex._emit(event, data);
    },

    // API — every method resolves to a plain object, usually { ok, ... }; never rejects.
    login(login, password) { return call('login', [login, password]); },
    register(email, password, username) { return call('register', [email, password, username || null]); },
    logout() { return call('logout', []); },
    launch(kind, name) { return call('launch', [kind, name]); },
    adminExit(pin) { return call('admin_exit', [pin]); },
    localExpired() { return call('local_expired', []); },
    getState() { return call('get_state', []); },
    peripherals() { return call('peripherals', []); },
  });

  let transport = null;

  function call(method, args) {
    if (!transport) return Promise.resolve({ ok: false, error: 'not_ready', message: 'Vortex is still starting. Try again in a moment.' });
    return Promise.resolve()
      .then(() => transport.call(method, args))
      .catch((e) => ({ ok: false, error: 'bridge', message: String((e && e.message) || e) }));
  }

  // ------------------------------------------------------------------ kiosk transport
  const pyTransport = {
    call(method, args) { return window.pywebview.api[method](...args); },
  };

  // ------------------------------------------------------------------ browser transport
  class WsTransport {
    constructor(url) {
      this.url = url;
      this.ws = null;
      this.online = false;
      this.reqId = 0;
      this.pending = new Map();
      this.stationName = params.get('station') || 'BROWSER-DEV';
      this.stationKey = '';
      try { this.stationKey = localStorage.getItem('vortex_dev_key:' + this.stationName) || ''; } catch (e) { /* ignore */ }
      this.connect();
    }

    connect() {
      let ws;
      try { ws = new WebSocket(this.url + '/ws/station'); } catch (e) { setTimeout(() => this.connect(), 3000); return; }
      this.ws = ws;
      ws.onopen = () => ws.send(JSON.stringify({
        type: 'hello', station_name: this.stationName, station_key: this.stationKey,
        hostname: 'browser', version: Vortex.version + '-browser',
      }));
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch (e) { return; }
        if (msg.req_id != null && this.pending.has(msg.req_id)) {
          this.pending.get(msg.req_id)(msg);
          this.pending.delete(msg.req_id);
          return;
        }
        if (msg.type === 'welcome') {
          if (msg.station_key) {
            this.stationKey = msg.station_key;
            try { localStorage.setItem('vortex_dev_key:' + this.stationName, msg.station_key); } catch (e) { /* ignore */ }
          }
          this.online = true;
          Vortex._dispatch('welcome', {
            online: true, station: msg.station, config: msg.config, session: msg.session,
            client: { station_name: this.stationName, server: this.url, version: Vortex.version + '-browser', kiosk: false },
            peripherals: null,
          });
        } else if (msg.type === 'pong') {
          /* keepalive */
        } else if (msg.type === 'session_update') {
          Vortex._dispatch('session_update', { session: msg.session, event: msg.event });
        } else if (msg.type === 'command') {
          if (msg.name === 'lock' || msg.name === 'unlock') Vortex._dispatch('station_locked', { locked: msg.name === 'lock' });
          else Vortex._dispatch('message', { title: 'Staff command', body: msg.name + ' (simulated in browser mode)', level: 'info' });
        } else if (msg.type === 'error') {
          Vortex._dispatch('rejected', msg);
        } else {
          Vortex._dispatch(msg.type, msg);
        }
      };
      ws.onclose = () => {
        if (this.online) Vortex._dispatch('link', { online: false });
        this.online = false;
        this.pending.forEach((resolve) => resolve({ ok: false, error: 'offline', message: 'The Vortex server is offline. Ask the counter.' }));
        this.pending.clear();
        clearInterval(this.hb);
        setTimeout(() => this.connect(), 2500);
      };
      ws.onerror = () => { try { ws.close(); } catch (e) { /* ignore */ } };
      clearInterval(this.hb);
      this.hb = setInterval(() => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'heartbeat' })); }, 10000);
    }

    request(msg) {
      return new Promise((resolve) => {
        if (!this.ws || this.ws.readyState !== 1) {
          resolve({ ok: false, error: 'offline', message: 'The Vortex server is offline. Ask the counter.' });
          return;
        }
        const id = ++this.reqId;
        msg.req_id = id;
        this.pending.set(id, resolve);
        this.ws.send(JSON.stringify(msg));
        setTimeout(() => {
          if (this.pending.has(id)) { this.pending.delete(id); resolve({ ok: false, error: 'timeout', message: 'The server did not answer. Try again.' }); }
        }, 10000);
      });
    }

    async call(method, args) {
      switch (method) {
        case 'login': return this.request({ type: 'login', login: args[0], password: args[1] });
        case 'register': return this.request({ type: 'register', email: args[0], password: args[1], username: args[2] });
        case 'logout': return this.request({ type: 'logout' });
        case 'admin_exit': {
          const res = await this.request({ type: 'admin_exit', pin: args[0] });
          if (res.ok) setTimeout(() => {
            document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;color:#00e5ff;font-family:monospace;font-size:14px;letter-spacing:2px;">KIOSK EXITED (browser mode) · RELOAD TO START AGAIN</div>';
          }, 500);
          return res;
        }
        case 'launch': {
          const kind = args[0], name = args[1];
          if (!Vortex.state.session) return { ok: false, error: 'no_session', message: 'Log in first.' };
          setTimeout(() => Vortex._dispatch('launch', { name, kind, state: 'starting' }), 0);
          setTimeout(() => Vortex._dispatch('launch', { name, kind, state: 'running' }), 1500);
          setTimeout(() => Vortex._dispatch('launch', { name, kind, state: 'exited', tracked: true }), 6000);
          if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify({ type: 'launch_report', item: name, kind }));
          return { ok: true, simulated: true };
        }
        case 'local_expired': return { ok: true, ignored: true };
        case 'get_state': return Vortex.state;
        case 'peripherals': return null;
        default: return { ok: false, error: 'unknown_method', message: method };
      }
    }
  }

  // ------------------------------------------------------------------ boot
  function useKiosk() {
    transport = pyTransport;
    Vortex.ready = true;
    Vortex.getState().then((s) => Vortex._dispatch('state', s));
  }

  function useBrowser() {
    let server = params.get('server');
    if (!server) {
      server = location.host && location.protocol.startsWith('http')
        ? (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host
        : 'ws://localhost:8787';
    }
    transport = new WsTransport(server);
    Vortex.mode = 'browser';
    Vortex.ready = true;
    Vortex._dispatch('state', { online: false, client: { station_name: transport.stationName, server, version: Vortex.version + '-browser', kiosk: false } });
  }

  if (KIOSK) {
    if (window.pywebview && window.pywebview.api) useKiosk();
    else {
      window.addEventListener('pywebviewready', useKiosk);
      // Safety net: WebView2 without pywebview (should not happen) falls back to browser mode.
      setTimeout(() => { if (!Vortex.ready) { console.warn('[vortex] no pywebview bridge after 8s, using browser mode'); useBrowser(); } }, 8000);
    }
  } else {
    useBrowser();
  }
})();
