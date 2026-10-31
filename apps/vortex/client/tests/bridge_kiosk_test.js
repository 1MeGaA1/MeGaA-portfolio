// Exercise vortex-bridge.js's mode detection + kiosk transport with a faked environment.
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(__dirname + '/../ui/vortex-bridge.js', 'utf8');

function run(setup) {
  const calls = [];
  const listeners = {};
  const win = {
    addEventListener: (ev, fn) => { (listeners[ev] = listeners[ev] || []).push(fn); },
    location: { href: 'file:///C:/x/ui/index.html', search: '', protocol: 'file:', host: '' },
    console,
  };
  const api = {};
  for (const m of ['login', 'register', 'logout', 'launch', 'admin_exit', 'local_expired', 'get_state', 'peripherals']) {
    api[m] = (...args) => { calls.push([m, ...args]); return Promise.resolve(m === 'get_state' ? { online: true, station: { name: 'PC-01' } } : { ok: true, echoed: args }); };
  }
  setup(win, api);
  const sandbox = {
    window: win, console, URLSearchParams,
    document: { title: 'Vortex Gaming Network' },
    setTimeout, clearInterval, setInterval,
    location: win.location,
    localStorage: undefined,
    WebSocket: function () { throw new Error('no ws in this test'); },
  };
  win.document = sandbox.document;
  win.setTimeout = setTimeout; win.clearInterval = clearInterval; win.setInterval = setInterval;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: 'vortex-bridge.js' });
  return { win, api, calls, listeners, get Vortex() { return win.Vortex; } };
}

const checks = [];
const ok = (name, cond) => checks.push([name, !!cond]);

async function main() {
  // A) Real kiosk: WebView2 + pywebview.api present at load.
  {
    const r = run((win, api) => { win.chrome = { webview: {} }; win.pywebview = { api }; });
    ok('A kiosk mode', r.Vortex.mode === 'kiosk');
    ok('A ready', r.Vortex.ready === true);
    await new Promise(res => setTimeout(res, 0));   // let useKiosk's getState() microtask flush
    ok('A getState routed to pywebview.api', r.calls.some(c => c[0] === 'get_state'));
    const res = await r.Vortex.login('nova@vortex.gg', 'secret');
    ok('A login routed with args', r.calls.some(c => c[0] === 'login' && c[1] === 'nova@vortex.gg' && c[2] === 'secret'));
    ok('A login result passthrough', res && res.ok === true);
    const ax = await r.Vortex.adminExit('1234');
    ok('A adminExit routed', r.calls.some(c => c[0] === 'admin_exit' && c[1] === '1234'));
    ok('A adminExit result', ax && ax.ok === true);
  }
  // B) WebView2 present, pywebview.api arrives later via pywebviewready (real startup race).
  {
    const r = run((win) => { win.chrome = { webview: {} }; });      // no pywebview yet
    ok('B kiosk mode before ready', r.Vortex.mode === 'kiosk');
    ok('B not ready yet', r.Vortex.ready === false);
    r.win.pywebview = { api: r.api };
    (r.listeners['pywebviewready'] || []).forEach(fn => fn());
    ok('B ready after event', r.Vortex.ready === true);
    await r.Vortex.getState();
    ok('B getState routed after ready', r.calls.some(c => c[0] === 'get_state'));
  }
  // C) Plain browser (no WebView2, no pywebview) -> browser mode, must not throw.
  {
    const r = run(() => {});
    ok('C browser mode', r.Vortex.mode === 'browser');
    ok('C ready', r.Vortex.ready === true);
  }
  // D) Forced kiosk-off via ?kiosk=0 even inside WebView2 -> browser mode.
  {
    const r = run((win, api) => { win.chrome = { webview: {} }; win.pywebview = { api }; win.location.search = '?kiosk=0'; });
    ok('D ?kiosk=0 forces browser', r.Vortex.mode === 'browser');
  }

  let pass = 0;
  for (const [name, good] of checks) { console.log((good ? 'PASS ' : 'FAIL ') + name); if (good) pass++; }
  console.log(`\n${pass}/${checks.length} checks passed`);
  process.exit(pass === checks.length ? 0 : 1);
}
main().catch(e => { console.error(e); process.exit(2); });
