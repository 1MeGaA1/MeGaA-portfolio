/* Vortex admin panel — talks to /api (REST) and /ws/admin (live station board). */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pad = (n) => String(n).padStart(2, '0');

  const state = {
    token: null, staff: null,
    settings: { cafe_name: 'Vortex', currency: '', auto_register_stations: true, min_session_seconds: 60 },
    stations: [], stationsAt: 0,
    members: [], groups: [], packages: [],
    products: [], orders: [], ordersFp: '', events: [],
    page: 'dashboard', ws: null, wsTimer: null, dashTimer: null, salesMode: 'today', memberQuery: '',
  };

  // ------------------------------------------------------------------ storage
  const store = {
    get() { try { return localStorage.getItem('vortex_token') || sessionStorage.getItem('vortex_token'); } catch (e) { return null; } },
    set(token, remember) { try { (remember ? localStorage : sessionStorage).setItem('vortex_token', token); } catch (e) { /* private mode */ } },
    clear() { try { localStorage.removeItem('vortex_token'); sessionStorage.removeItem('vortex_token'); } catch (e) { /* ignore */ } },
  };

  // ------------------------------------------------------------------ api
  async function api(path, { method = 'GET', body } = {}) {
    const headers = { Accept: 'application/json' };
    if (state.token) headers.Authorization = 'Bearer ' + state.token;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch('/api' + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch (e) {
      throw { error: 'network', message: 'Cannot reach the server.' };
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) {
      if (res.status === 401 && state.token && !path.startsWith('/auth/')) logout(false);
      if (res.status === 422 && data && data.detail) {
        const d = Array.isArray(data.detail) ? data.detail[0] : data.detail;
        throw { error: 'validation', message: (d && d.msg) ? `${(d.loc || []).slice(-1)[0]}: ${d.msg}` : 'Invalid input.' };
      }
      throw (data && data.error) ? data : { error: 'http_' + res.status, message: (data && data.message) || res.statusText };
    }
    return data;
  }

  // ------------------------------------------------------------------ formatting
  const cur = () => state.settings.currency || '';
  const fmtMoney = (minor) => ((minor || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + (cur() ? ' ' + cur() : '');
  const fmtClock = (secs) => {
    secs = Math.max(0, Math.floor(secs || 0));
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
    return `${h}:${pad(m)}:${pad(s)}`;
  };
  const fmtHM = (secs) => {
    const neg = secs < 0; secs = Math.abs(Math.floor(secs || 0));
    const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60);
    return (neg ? '-' : '') + (h ? `${h}h ${pad(m)}m` : `${m}m`);
  };
  const fmtTime = (iso) => { if (!iso) return '—'; const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const fmtDateTime = (iso) => { if (!iso) return '—'; const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const tierPill = (tier) => `<span class="pill pill-${String(tier || 'bronze').toLowerCase()}">${esc(tier || 'BRONZE')}</span>`;
  const groupPill = (g) => `<span class="pill ${/vip/i.test(g || '') ? 'pill-vip' : 'pill-reg'}">${esc(g || '—')}</span>`;
  const statusPill = (s) => ({
    free: '<span class="pill pill-free">FREE</span>',
    in_session: '<span class="pill pill-session">IN SESSION</span>',
    offline: '<span class="pill pill-offline">OFFLINE</span>',
    locked: '<span class="pill pill-locked">LOCKED</span>',
  }[s] || `<span class="pill">${esc(s)}</span>`);

  function liveRemaining(session) {
    if (!session) return 0;
    const drift = (Date.now() - state.stationsAt) / 1000;
    return Math.max(0, session.remaining_seconds - drift);
  }
  function remainingClass(secs) { return secs < 600 ? 'critical' : secs < 1800 ? 'warning' : ''; }

  // ------------------------------------------------------------------ toast + modal
  let toastTimer = null;
  function toast(text, kind = '') {
    const el = $('#toast');
    el.textContent = text;
    el.className = 'toast show ' + kind;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = 'toast'; }, kind === 'error' ? 4200 : 2600);
  }
  const fail = (e) => toast(e && e.message ? e.message : String(e), 'error');

  function openModal({ label = '', title = '', desc = '', body = '', buttons = [], wide = false, onOpen }) {
    const wrap = $('#modal-content');
    wrap.className = 'modal-content' + (wide ? ' wide' : '');
    wrap.innerHTML = `
      <div class="modal-head">
        <div><div class="modal-label">${esc(label)}</div><div class="modal-title">${esc(title)}</div></div>
        <button class="modal-close" data-close>✕</button>
      </div>
      ${desc ? `<div class="modal-desc">${desc}</div>` : ''}
      <div class="modal-body">${body}</div>
      ${buttons.length ? `<div class="modal-buttons">${buttons.map((b, i) => `<button class="btn ${b.cls || 'btn-ghost'}" data-btn="${i}">${esc(b.text)}</button>`).join('')}</div>` : ''}
    `;
    $('#modal').classList.add('active');
    $$('[data-close]', wrap).forEach((b) => b.addEventListener('click', closeModal));
    buttons.forEach((b, i) => {
      $(`[data-btn="${i}"]`, wrap).addEventListener('click', async (ev) => {
        const btn = ev.currentTarget;
        if (!b.onClick) return closeModal();
        btn.disabled = true;
        try { const keep = await b.onClick(wrap); if (keep !== true) closeModal(); }
        catch (e) { fail(e); }
        finally { btn.disabled = false; }
      });
    });
    if (onOpen) onOpen(wrap);
    const first = $('input, select, textarea', wrap);
    if (first) setTimeout(() => first.focus(), 30);
    return wrap;
  }
  function closeModal() { $('#modal').classList.remove('active'); $('#modal-content').innerHTML = ''; }
  const confirmModal = (title, desc, onYes, cls = 'btn-magenta', text = 'CONFIRM') =>
    openModal({ label: '// CONFIRM', title, desc, buttons: [{ text: 'CANCEL' }, { text, cls, onClick: onYes }] });

  // ------------------------------------------------------------------ sale picker (packages + custom minutes)
  function salePickerHtml(groupId, { allowNegative = false } = {}) {
    const pk = state.packages.filter((p) => p.enabled && (p.group_id == null || p.group_id === groupId));
    return `
      <div class="pkg-grid" id="sale-packages">
        ${pk.map((p) => `<button type="button" class="pkg-btn" data-pkg="${p.id}"><div class="pkg-name">${esc(p.name)}</div><div class="pkg-price">${fmtMoney(p.price)}</div></button>`).join('')}
      </div>
      <div class="form-row">
        <div><label class="form-label">Custom minutes</label><input type="number" id="sale-minutes" ${allowNegative ? '' : 'min="1"'} placeholder="e.g. 90"></div>
        <div><label class="form-label">Amount (${esc(cur() || 'money')}) · optional</label><input type="number" id="sale-amount" min="0" step="0.01" placeholder="auto from rate"></div>
      </div>
      <label class="form-label">Note · optional</label>
      <input type="text" id="sale-note" placeholder="paid cash / promo / correction">
      <div class="price-preview" id="sale-preview">// choose a package or type minutes</div>
    `;
  }
  function wireSalePicker(wrap, groupId) {
    const sel = { package_id: null };
    const group = state.groups.find((g) => g.id === groupId) || state.groups[0];
    const rate = group ? group.rate_per_hour : 0;
    const minutes = $('#sale-minutes', wrap), amount = $('#sale-amount', wrap), preview = $('#sale-preview', wrap);
    const refresh = () => {
      if (sel.package_id) {
        const p = state.packages.find((x) => x.id === sel.package_id);
        preview.textContent = `// ${p.name} · ${fmtHM(p.seconds)} · ${fmtMoney(amount.value ? Math.round(amount.value * 100) : p.price)}`;
      } else if (minutes.value) {
        const secs = Math.round(Number(minutes.value) * 60);
        const auto = Math.round(secs * rate / 3600);
        preview.textContent = `// ${fmtHM(secs)} · ${fmtMoney(amount.value ? Math.round(amount.value * 100) : auto)}${amount.value ? '' : ` (${fmtMoney(rate)}/hour)`}`;
      } else preview.textContent = '// choose a package or type minutes';
    };
    $$('.pkg-btn', wrap).forEach((b) => b.addEventListener('click', () => {
      const id = Number(b.dataset.pkg);
      sel.package_id = sel.package_id === id ? null : id;
      $$('.pkg-btn', wrap).forEach((x) => x.classList.toggle('active', Number(x.dataset.pkg) === sel.package_id));
      if (sel.package_id) minutes.value = '';
      refresh();
    }));
    minutes.addEventListener('input', () => { if (minutes.value) { sel.package_id = null; $$('.pkg-btn', wrap).forEach((x) => x.classList.remove('active')); } refresh(); });
    amount.addEventListener('input', refresh);
    return () => {
      const body = { note: $('#sale-note', wrap).value.trim() };
      if (sel.package_id) body.package_id = sel.package_id;
      else if (minutes.value) body.seconds = Math.round(Number(minutes.value) * 60);
      else throw { message: 'Choose a package or enter minutes.' };
      if (amount.value !== '') body.amount = Math.round(Number(amount.value) * 100);
      return body;
    };
  }

  // ------------------------------------------------------------------ auth
  async function login(ev) {
    ev.preventDefault();
    const err = $('#error-msg'), btn = $('#submit-btn');
    const username = $('#admin-id').value.trim(), password = $('#admin-pw').value;
    if (!username || !password) { err.textContent = 'ENTER STAFF ID + PASSWORD'; err.classList.add('active'); return; }
    btn.disabled = true; btn.textContent = 'AUTHENTICATING…';
    try {
      const res = await api('/auth/login', { method: 'POST', body: { username, password } });
      state.token = res.token; state.staff = res.staff;
      store.set(res.token, $('#remember').checked);
      err.classList.remove('active');
      await enterConsole();
    } catch (e) {
      err.textContent = (e.message || 'AUTH FAILED').toUpperCase();
      err.classList.add('active');
    } finally {
      btn.disabled = false; btn.textContent = 'AUTHENTICATE';
    }
  }

  async function logout(callServer = true) {
    if (callServer && state.token) { try { await api('/auth/logout', { method: 'POST' }); } catch (e) { /* ignore */ } }
    state.token = null; state.staff = null; store.clear();
    if (state.ws) { state.ws.onclose = null; state.ws.close(); state.ws = null; }
    clearTimeout(state.wsTimer); clearInterval(state.dashTimer);
    showScreen('admin-login');
    $('#admin-pw').value = '';
    setTimeout(() => $('#admin-id').focus(), 80);
  }

  function showScreen(id) {
    $$('.screen').forEach((s) => s.classList.remove('active'));
    $('#' + id).classList.add('active');
  }

  async function enterConsole() {
    const me = await api('/me');
    state.staff = me.staff; state.settings = me.settings;
    $('#foot-staff').textContent = state.staff.username.toUpperCase();
    $('#dash-cafe').textContent = state.settings.cafe_name.toUpperCase();
    document.title = `VORTEX · ADMIN · ${state.settings.cafe_name}`;
    await loadPricing();
    showScreen('admin-console');
    connectWS();
    showPage('dashboard');
  }

  // ------------------------------------------------------------------ live socket
  function setNet(ok, text) {
    $('#net-dot').style.color = ok ? 'var(--green)' : 'var(--red)';
    $('#net-text').textContent = text || (ok ? 'SERVER LINK ONLINE' : 'RECONNECTING…');
  }
  function connectWS() {
    if (!state.token) return;
    clearTimeout(state.wsTimer);
    state._wsOpened = false;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    let ws;
    try { ws = new WebSocket(`${proto}://${location.host}/ws/admin?token=${encodeURIComponent(state.token)}`); }
    catch (e) { setNet(false); state.wsTimer = setTimeout(connectWS, 3000); return; }
    state.ws = ws;
    ws.onopen = () => { state._wsOpened = true; setNet(true); };
    ws.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.type === 'stations') {
        state.stations = msg.stations; state.stationsAt = Date.now();
        // Re-render only when something other than the countdown changed,
        // so staff never lose a button under their cursor.
        const fp = JSON.stringify(msg.stations.map((s) => [s.id, s.name, s.group, s.ip, s.status, s.locked, s.enabled, s.online,
          s.session && [s.session.id, s.session.kind, s.session.budget_seconds, s.session.member && s.session.member.id]]));
        if (fp !== state.stationsFp) {
          state.stationsFp = fp;
          renderStations(); renderDashboardLive();
        }
        updateFooter();
      } else if (msg.type === 'orders') {
        // Pending shop queue — sent on connect and whenever an order is created/done/cancelled.
        state.orders = msg.orders || [];
        renderOrders();
      }
    };
    ws.onclose = () => {
      setNet(false);
      if (!state.token) return;
      if (!state._wsOpened) {
        // Handshake rejected (commonly a stale login token after a server restart).
        // Verify the token: api() drops us to the login screen on 401, else retry.
        api('/me').then(() => { state.wsTimer = setTimeout(connectWS, 2500); }).catch(() => {});
        return;
      }
      state.wsTimer = setTimeout(connectWS, 2500);
    };
    ws.onerror = () => { try { ws.close(); } catch (e) { /* ignore */ } };
  }
  setInterval(() => { if (state.ws && state.ws.readyState === 1) state.ws.send(JSON.stringify({ type: 'ping' })); }, 25000);

  function updateFooter() {
    const s = state.stations;
    $('#foot-sessions').textContent = s.filter((x) => x.status === 'in_session').length;
    $('#foot-online').textContent = s.filter((x) => x.online).length;
    $('#foot-total').textContent = s.length;
  }

  // ------------------------------------------------------------------ navigation
  const pageTitles = { dashboard: 'DASHBOARD', stations: 'STATIONS', members: 'MEMBERS', pricing: 'PRICING', sales: 'SALES', shop: 'SHOP', events: 'EVENTS', settings: 'SETTINGS' };
  const loaders = { dashboard: loadDashboard, stations: renderStations, members: loadMembers, pricing: renderPricing, sales: loadSales, shop: loadShop, events: loadEvents, settings: loadSettings };
  function showPage(id) {
    state.page = id;
    $$('.page').forEach((p) => p.classList.toggle('active', p.id === id));
    $$('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.page === id));
    $('#topbar-title').textContent = pageTitles[id] || id.toUpperCase();
    clearInterval(state.dashTimer);
    if (id === 'dashboard') state.dashTimer = setInterval(loadDashboard, 15000);
    Promise.resolve(loaders[id] && loaders[id]()).catch(fail);
  }

  // ------------------------------------------------------------------ dashboard
  async function loadDashboard() {
    const d = await api('/dashboard');
    $('#st-revenue').textContent = fmtMoney(d.revenue_today);
    $('#st-sold-sub').textContent = `${fmtHM(d.seconds_sold_today)} sold`;
    $('#st-sessions-today').textContent = d.sessions_today;
    $('#st-members').textContent = d.members_total;
    $('#st-members-sub').textContent = `+${d.members_today} today`;
    renderDashboardLive();
    const ev = await api('/audit?limit=12');
    $('#dash-events').innerHTML = eventsTable(ev.events);
  }
  function renderDashboardLive() {
    const s = state.stations;
    const online = s.filter((x) => x.online).length;
    const inSession = s.filter((x) => x.status === 'in_session');
    const locked = s.filter((x) => x.locked).length;
    $('#st-session').textContent = `${inSession.length} / ${online}`;
    $('#st-session-sub').textContent = `${online} of ${s.length} stations online`;
    $('#st-free').textContent = s.filter((x) => x.status === 'free').length;
    $('#st-offline').textContent = s.filter((x) => !x.online).length;
    $('#st-locked-sub').textContent = `${locked} locked by staff`;
    if (!inSession.length) { $('#dash-sessions').innerHTML = '<div class="empty">NO ACTIVE SESSIONS</div>'; return; }
    $('#dash-sessions').innerHTML = `<table class="data-table"><thead><tr><th>Station</th><th>User</th><th>Time left</th><th>Started</th><th style="text-align:right">Action</th></tr></thead><tbody>
      ${inSession.map((st) => {
        const ses = st.session, rem = liveRemaining(ses);
        return `<tr><td>${groupPill(st.group)} <span class="station-name">${esc(st.name)}</span></td>
          <td>${userCell(ses)}${activitySub(st)}</td>
          <td><span class="time-left ${remainingClass(rem)}" data-remaining="${st.id}">${fmtClock(rem)}</span></td>
          <td class="mono" style="color:var(--text-muted)">${fmtTime(ses.started_at)}</td>
          <td class="actions"><button class="btn-link" data-act="topup" data-id="${st.id}">TOP UP</button><button class="btn-link danger" data-act="end" data-id="${st.id}">END</button></td></tr>`;
      }).join('')}</tbody></table>`;
    wireStationActions($('#dash-sessions'));
  }
  const userCell = (ses) => !ses ? '—'
    : ses.kind === 'guest' ? '<span class="pill pill-guest">GUEST</span>'
    : `<span class="member-link" data-member="${ses.member.id}">${esc(ses.member.username)}</span> ${tierPill(ses.member.tier)}`;

  // Live "what is this PC doing right now" — a small sub-line under the user.
  function activitySub(st) {
    const a = st.activity;
    if (!a) return st.status === 'in_session' ? '<div class="sub" style="color:var(--text-dim)">▶ on the Vortex menu</div>' : '';
    const label = a.foreground || a.title || '';
    const others = (a.running || []).filter((r) => r && r !== a.foreground);
    let html = label
      ? `<div class="sub" style="color:var(--green)" title="${esc(a.title || '')}">▶ ${esc(label)}</div>`
      : '<div class="sub" style="color:var(--text-dim)">▶ on the Vortex menu</div>';
    if (others.length) html += `<div class="sub">open: ${esc(others.join(', '))}</div>`;
    return html;
  }

  function eventsTable(events) {
    if (!events.length) return '<div class="empty">NOTHING LOGGED YET</div>';
    return `<table class="data-table"><thead><tr><th>Time</th><th>Action</th><th>Detail</th><th>By</th></tr></thead><tbody>
      ${events.map((e) => `<tr><td class="mono" style="color:var(--text-muted)">${fmtDateTime(e.at)}</td><td class="mono">${esc(e.action)}</td><td>${esc(e.detail || '')}</td><td class="mono" style="color:var(--text-dim)">${esc(e.staff || 'system')}</td></tr>`).join('')}
    </tbody></table>`;
  }

  // ------------------------------------------------------------------ stations
  function renderStations() {
    const s = state.stations;
    $('#stations-desc').textContent = `// ${s.length} STATIONS · ${s.filter((x) => x.online).length} ONLINE · LIVE FEED`;
    if (!s.length) { $('#stations-table').innerHTML = '<div class="empty">NO STATIONS YET — START THE VORTEX CLIENT ON A PC</div>'; return; }
    const groups = [...new Set(s.map((x) => x.group || 'UNGROUPED'))];
    let rows = '';
    for (const g of groups) {
      rows += `<tr class="section-tag ${/vip/i.test(g) ? 'vip' : 'regular'}"><td colspan="7">// ${esc(g.toUpperCase())}</td></tr>`;
      for (const st of s.filter((x) => (x.group || 'UNGROUPED') === g)) {
        const ses = st.session, rem = liveRemaining(ses);
        const acts = [];
        if (st.status === 'in_session') {
          acts.push(`<button class="btn-link" data-act="topup" data-id="${st.id}">TOP UP</button>`);
          acts.push(`<button class="btn-link danger" data-act="end" data-id="${st.id}">END</button>`);
        } else if (st.online) {
          acts.push(`<button class="btn-link green" data-act="start" data-id="${st.id}">START</button>`);
        }
        acts.push(st.locked
          ? `<button class="btn-link amber" data-act="unlock" data-id="${st.id}">UNLOCK</button>`
          : `<button class="btn-link" data-act="lock" data-id="${st.id}">LOCK</button>`);
        if (st.online) acts.push(`<button class="btn-link" data-act="message" data-id="${st.id}">MSG</button>`);
        acts.push(`<button class="btn-link" data-act="more" data-id="${st.id}">⋯</button>`);
        rows += `<tr class="${st.enabled ? '' : 'row-dim'}">
          <td><span class="station-name">${esc(st.name)}</span><div class="sub">${esc(st.hostname || '')}</div></td>
          <td class="mono" style="color:var(--text-muted)">${esc(st.ip || '—')}</td>
          <td>${statusPill(st.status)}${!st.enabled ? ' <span class="pill pill-disabled">DISABLED</span>' : ''}</td>
          <td>${userCell(ses)}${activitySub(st)}</td>
          <td>${ses ? `<span class="time-left ${remainingClass(rem)}" data-remaining="${st.id}">${fmtClock(rem)}</span>` : '<span class="sub">—</span>'}</td>
          <td class="mono" style="color:var(--text-muted)">${ses ? fmtTime(ses.started_at) : (st.last_seen ? 'seen ' + fmtTime(st.last_seen) : '—')}</td>
          <td class="actions">${acts.join('')}</td></tr>`;
      }
    }
    $('#stations-table').innerHTML = `<table class="data-table"><thead><tr><th>Station</th><th>IP</th><th>Status</th><th>User</th><th>Time left</th><th>Started</th><th style="text-align:right">Actions</th></tr></thead><tbody>${rows}</tbody></table>`;
    wireStationActions($('#stations-table'));
  }

  function wireStationActions(root) {
    $$('[data-act]', root).forEach((b) => b.addEventListener('click', () => stationAction(b.dataset.act, Number(b.dataset.id))));
    $$('[data-member]', root).forEach((m) => m.addEventListener('click', () => memberDetails(Number(m.dataset.member))));
  }

  async function stationAction(act, id) {
    const st = state.stations.find((x) => x.id === id);
    if (!st) return;
    try {
      if (act === 'lock' || act === 'unlock') {
        await api(`/stations/${id}/command`, { method: 'POST', body: { name: act } });
        toast(`${st.name} ${act.toUpperCase()}ED`);
      } else if (act === 'end') {
        confirmModal(`End session on ${st.name}?`, 'The customer is logged out and the PC locks immediately. Unused time stays in a member\'s wallet.',
          async () => { await api(`/stations/${id}/session`, { method: 'DELETE' }); toast(`Session on ${st.name} ended`); });
      } else if (act === 'topup') topupStation(st);
      else if (act === 'start') startSession(st);
      else if (act === 'message') messageStation(st);
      else if (act === 'more') stationMore(st);
    } catch (e) { fail(e); }
  }

  function topupStation(st) {
    const who = st.session.kind === 'guest' ? 'guest session' : st.session.member.username;
    openModal({
      label: '// TOP UP', title: `${st.name} · ${who}`, desc: 'Time is added to the running session right away.',
      body: salePickerHtml(st.group_id),
      buttons: [{ text: 'CANCEL' }, { text: 'ADD TIME', cls: 'btn-primary', onClick: async (wrap) => {
        const body = wrap._collect();
        await api(`/stations/${st.id}/session/topup`, { method: 'POST', body });
        toast(`Time added on ${st.name}`);
      } }],
      onOpen: (wrap) => { wrap._collect = wireSalePicker(wrap, st.group_id); },
    });
  }

  function startSession(st) {
    openModal({
      label: '// START SESSION', title: st.name, wide: true,
      body: `
        <div class="tabs"><div class="tab active" data-tab="guest">GUEST · WALK-IN</div><div class="tab" data-tab="member">MEMBER</div></div>
        <div data-pane="guest">${salePickerHtml(st.group_id)}</div>
        <div data-pane="member" hidden>
          <label class="form-label">Find member</label>
          <input type="text" id="ss-search" placeholder="username or email…">
          <div class="scroll" id="ss-results" style="margin-top:10px"></div>
          <div class="hint">Members log in themselves on the station. Starting from here is for when they forgot their password or the counter handles it.</div>
        </div>`,
      buttons: [{ text: 'CANCEL' }, { text: 'START', cls: 'btn-primary', onClick: async (wrap) => {
        if (wrap._tab === 'guest') {
          const sale = wrap._collect();
          const body = { package_id: sale.package_id, guest_minutes: sale.seconds ? Math.round(sale.seconds / 60) : undefined, amount: sale.amount };
          await api(`/stations/${st.id}/session`, { method: 'POST', body });
          toast(`Guest session started on ${st.name}`);
        } else {
          if (!wrap._member) throw { message: 'Pick a member first.' };
          await api(`/stations/${st.id}/session`, { method: 'POST', body: { member_id: wrap._member } });
          toast(`Session started on ${st.name}`);
        }
      } }],
      onOpen: (wrap) => {
        wrap._tab = 'guest'; wrap._collect = wireSalePicker(wrap, st.group_id);
        $$('.tab', wrap).forEach((t) => t.addEventListener('click', () => {
          wrap._tab = t.dataset.tab;
          $$('.tab', wrap).forEach((x) => x.classList.toggle('active', x === t));
          $$('[data-pane]', wrap).forEach((p) => { p.hidden = p.dataset.pane !== wrap._tab; });
        }));
        const search = $('#ss-search', wrap), results = $('#ss-results', wrap);
        let timer = null;
        const run = async () => {
          const q = search.value.trim();
          const res = await api(`/members?q=${encodeURIComponent(q)}&limit=25`);
          results.innerHTML = res.members.length ? `<table class="data-table"><tbody>${res.members.map((m) => `
            <tr data-pick="${m.id}" style="cursor:pointer"><td>${esc(m.username)} ${tierPill(m.tier)}</td><td class="mono" style="color:var(--text-muted)">${esc(m.email)}</td>
            <td class="mono ${m.time_balance_seconds < 60 ? 'pill-disabled' : ''}">${fmtHM(m.time_balance_seconds)}</td><td>${m.active_station ? `<span class="pill pill-session">${esc(m.active_station)}</span>` : ''}</td></tr>`).join('')}</tbody></table>`
            : '<div class="empty">NO MEMBERS FOUND</div>';
          $$('[data-pick]', results).forEach((r) => r.addEventListener('click', () => {
            wrap._member = Number(r.dataset.pick);
            $$('[data-pick]', results).forEach((x) => x.style.outline = x === r ? '1px solid var(--cyan)' : '');
          }));
        };
        search.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => run().catch(fail), 250); });
        run().catch(fail);
      },
    });
  }

  function messageStation(st) {
    openModal({
      label: '// MESSAGE', title: `Send to ${st.name}`,
      body: `<label class="form-label">Title</label><input type="text" id="msg-title" placeholder="Message from staff">
             <label class="form-label">Text</label><input type="text" id="msg-body" placeholder="Your order is ready">
             <label class="switch"><input type="checkbox" id="msg-warn"> SHOW AS WARNING</label>`,
      buttons: [{ text: 'CANCEL' }, { text: 'SEND', cls: 'btn-primary', onClick: async (wrap) => {
        const body = $('#msg-body', wrap).value.trim();
        if (!body) throw { message: 'Type a message.' };
        await api(`/stations/${st.id}/command`, { method: 'POST', body: { name: 'message', title: $('#msg-title', wrap).value.trim(), body, level: $('#msg-warn', wrap).checked ? 'warn' : 'info' } });
        toast(`Message sent to ${st.name}`);
      } }],
    });
  }

  function stationMore(st) {
    openModal({
      label: '// STATION', title: st.name,
      body: `
        <label class="form-label">Name</label><input type="text" id="st-name" value="${esc(st.name)}">
        <label class="form-label">Group</label>
        <select id="st-group">${state.groups.map((g) => `<option value="${g.id}" ${g.id === st.group_id ? 'selected' : ''}>${esc(g.name)} · ${fmtMoney(g.rate_per_hour)}/h</option>`).join('')}</select>
        <label class="switch"><input type="checkbox" id="st-enabled" ${st.enabled ? 'checked' : ''}> ENABLED</label>
        <div class="kv" style="margin-top:14px"><span class="k">Hostname</span><span class="v">${esc(st.hostname || '—')}</span></div>
        <div class="kv"><span class="k">IP</span><span class="v">${esc(st.ip || '—')}</span></div>
        <div class="kv"><span class="k">Last seen</span><span class="v">${fmtDateTime(st.last_seen)}</span></div>
        <div class="actions" style="justify-content:flex-start; margin-top:14px; gap:8px">
          ${st.online ? `<button class="btn btn-ghost" data-cmd="restart">RESTART KIOSK</button><button class="btn btn-ghost" data-cmd="reboot">REBOOT PC</button><button class="btn btn-ghost" data-cmd="shutdown">SHUT DOWN</button>` : ''}
          <button class="btn btn-ghost" data-resetkey>RESET KEY</button>
          <button class="btn btn-danger" data-delete>DELETE</button>
        </div>
        <div class="hint" id="st-keybox"></div>`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE', cls: 'btn-primary', onClick: async (wrap) => {
        await api(`/stations/${st.id}`, { method: 'PATCH', body: { name: $('#st-name', wrap).value.trim(), group_id: Number($('#st-group', wrap).value), enabled: $('#st-enabled', wrap).checked } });
        toast('Station saved');
      } }],
      onOpen: (wrap) => {
        $$('[data-cmd]', wrap).forEach((b) => b.addEventListener('click', () => {
          const cmd = b.dataset.cmd;
          confirmModal(`${cmd.toUpperCase()} ${st.name}?`, cmd === 'restart' ? 'The kiosk app restarts. A running session keeps counting.' : 'The PC will ' + cmd + ' now.',
            async () => { await api(`/stations/${st.id}/command`, { method: 'POST', body: { name: cmd } }); toast(`${cmd} sent to ${st.name}`); });
        }));
        $('[data-resetkey]', wrap).addEventListener('click', async () => {
          try { const r = await api(`/stations/${st.id}/reset-key`, { method: 'POST' }); $('#st-keybox', wrap).innerHTML = `New key (put it in the client's client.json):<br><span class="mono" style="color:var(--cyan)">${esc(r.key)}</span>`; }
          catch (e) { fail(e); }
        });
        $('[data-delete]', wrap).addEventListener('click', () => confirmModal(`Delete ${st.name}?`, 'Stations with history are disabled instead of deleted.',
          async () => { await api(`/stations/${st.id}`, { method: 'DELETE' }); toast('Station removed'); }));
      },
    });
  }

  function addStation() {
    openModal({
      label: '// ADD STATION', title: 'Register a PC by hand', desc: 'Only needed when auto-register is off. The key is shown once.',
      body: `<label class="form-label">Name</label><input type="text" id="new-st-name" placeholder="PC-05">
             <label class="form-label">Group</label><select id="new-st-group">${state.groups.map((g) => `<option value="${g.id}">${esc(g.name)}</option>`).join('')}</select>
             <div class="hint" id="new-st-key"></div>`,
      buttons: [{ text: 'CLOSE' }, { text: 'CREATE', cls: 'btn-primary', onClick: async (wrap) => {
        const r = await api('/stations', { method: 'POST', body: { name: $('#new-st-name', wrap).value.trim(), group_id: Number($('#new-st-group', wrap).value) } });
        $('#new-st-key', wrap).innerHTML = `Created <b>${esc(r.name)}</b>. Station key:<br><span class="mono" style="color:var(--cyan)">${esc(r.key)}</span>`;
        toast('Station created');
        return true;
      } }],
    });
  }

  // countdown tick for every visible time-left cell
  setInterval(() => {
    if (!state.stations.length) return;
    $$('[data-remaining]').forEach((el) => {
      const st = state.stations.find((x) => x.id === Number(el.dataset.remaining));
      if (!st || !st.session) return;
      const rem = liveRemaining(st.session);
      el.textContent = fmtClock(rem);
      el.className = 'time-left ' + remainingClass(rem);
    });
  }, 1000);

  // ------------------------------------------------------------------ members
  async function loadMembers() {
    const res = await api(`/members?q=${encodeURIComponent(state.memberQuery)}&limit=300`);
    state.members = res.members;
    $('#members-desc').textContent = `// ${res.members.length} ACCOUNTS${state.memberQuery ? ' · FILTERED' : ''}`;
    if (!res.members.length) { $('#members-table').innerHTML = '<div class="empty">NO MEMBERS YET — CLICK NEW MEMBER</div>'; return; }
    $('#members-table').innerHTML = `<table class="data-table"><thead><tr><th>ID</th><th>Username</th><th>Email</th><th>Tier</th><th>Time wallet</th><th>Points</th><th>Status</th><th style="text-align:right">Actions</th></tr></thead><tbody>
      ${res.members.map((m) => `<tr class="${m.enabled ? '' : 'row-dim'}">
        <td class="mono">#${m.id}</td>
        <td><span class="member-link" data-member="${m.id}">${esc(m.username)}</span></td>
        <td class="mono" style="color:var(--text-muted)">${esc(m.email)}</td>
        <td>${tierPill(m.tier)}</td>
        <td class="mono ${m.time_balance_seconds < 60 ? 'pill-disabled' : ''}">${fmtHM(m.time_balance_seconds)}</td>
        <td class="mono">${m.points}</td>
        <td>${m.active_station ? `<span class="pill pill-session">${esc(m.active_station)}</span>` : (m.enabled ? '<span class="sub">—</span>' : '<span class="pill pill-disabled">DISABLED</span>')}</td>
        <td class="actions"><button class="btn-link green" data-topup="${m.id}">TOP UP</button><button class="btn-link" data-edit="${m.id}">EDIT</button></td></tr>`).join('')}
    </tbody></table>`;
    const root = $('#members-table');
    $$('[data-topup]', root).forEach((b) => b.addEventListener('click', () => topupMember(Number(b.dataset.topup))));
    $$('[data-edit]', root).forEach((b) => b.addEventListener('click', () => editMember(Number(b.dataset.edit))));
    $$('[data-member]', root).forEach((m) => m.addEventListener('click', () => memberDetails(Number(m.dataset.member))));
  }

  function newMember() {
    openModal({
      label: '// NEW MEMBER', title: 'Register Customer', desc: 'The member logs in on any station with this email (or username) and password.',
      body: `<label class="form-label">Email</label><input type="email" id="nm-email" placeholder="customer@mail.com">
             <label class="form-label">Username · optional</label><input type="text" id="nm-user" placeholder="cyber_claw">
             <div class="form-row"><div><label class="form-label">Password</label><input type="password" id="nm-pw"></div><div><label class="form-label">Confirm</label><input type="password" id="nm-pw2"></div></div>
             <label class="form-label">Tier</label><select id="nm-tier"><option>BRONZE</option><option>SILVER</option><option>GOLD</option><option>PLATINUM</option></select>`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE ACCOUNT', cls: 'btn-primary', onClick: async (wrap) => {
        const pw = $('#nm-pw', wrap).value;
        if (pw !== $('#nm-pw2', wrap).value) throw { message: 'Passwords do not match.' };
        const m = await api('/members', { method: 'POST', body: { email: $('#nm-email', wrap).value.trim(), username: $('#nm-user', wrap).value.trim() || null, password: pw, tier: $('#nm-tier', wrap).value } });
        toast(`Member ${m.username} created`);
        if (state.page === 'members') loadMembers().catch(fail);
        closeModal();
        topupMember(m.id);
        return true;
      } }],
    });
  }

  async function topupMember(id) {
    const m = state.members.find((x) => x.id === id) || await api(`/members/${id}`);
    const st = state.stations.find((x) => x.session && x.session.member && x.session.member.id === id);
    openModal({
      label: '// SELL TIME', title: `${m.username} · wallet ${fmtHM(m.time_balance_seconds)}`,
      desc: st ? `Playing on <b>${esc(st.name)}</b> right now — the session grows immediately.` : 'Negative minutes remove time (correction).',
      body: salePickerHtml(st ? st.group_id : null, { allowNegative: true }),
      buttons: [{ text: 'CANCEL' }, { text: 'ADD TIME', cls: 'btn-primary', onClick: async (wrap) => {
        const r = await api(`/members/${id}/topup`, { method: 'POST', body: wrap._collect() });
        toast(`${m.username} now has ${fmtHM(r.member.time_balance_seconds)}`);
        if (state.page === 'members') loadMembers().catch(fail);
      } }],
      onOpen: (wrap) => { wrap._collect = wireSalePicker(wrap, st ? st.group_id : null); },
    });
  }

  async function editMember(id) {
    const m = await api(`/members/${id}`);
    openModal({
      label: '// EDIT MEMBER', title: m.username,
      body: `<label class="form-label">Email</label><input type="email" id="em-email" value="${esc(m.email)}">
             <label class="form-label">Username</label><input type="text" id="em-user" value="${esc(m.username)}">
             <div class="form-row"><div><label class="form-label">Tier</label><select id="em-tier">${['BRONZE', 'SILVER', 'GOLD', 'PLATINUM'].map((t) => `<option ${t === m.tier ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
             <div><label class="form-label">Points</label><input type="number" id="em-points" value="${m.points}"></div></div>
             <label class="form-label">New password · leave empty to keep</label><input type="password" id="em-pw" autocomplete="new-password">
             <label class="switch"><input type="checkbox" id="em-enabled" ${m.enabled ? 'checked' : ''}> ACCOUNT ENABLED</label>`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE', cls: 'btn-primary', onClick: async (wrap) => {
        await api(`/members/${id}`, { method: 'PATCH', body: { email: $('#em-email', wrap).value.trim(), username: $('#em-user', wrap).value.trim(), tier: $('#em-tier', wrap).value, points: Number($('#em-points', wrap).value), password: $('#em-pw', wrap).value || null, enabled: $('#em-enabled', wrap).checked } });
        toast('Member saved');
        if (state.page === 'members') loadMembers().catch(fail);
      } }],
    });
  }

  async function memberDetails(id) {
    const [m, tx, ss] = await Promise.all([api(`/members/${id}`), api(`/members/${id}/transactions`), api(`/members/${id}/sessions`)]);
    openModal({
      label: '// MEMBER', title: `${m.username} ${m.tier}`, wide: true,
      body: `<div class="grid-2">
          <div><div class="kv"><span class="k">Email</span><span class="v">${esc(m.email)}</span></div>
               <div class="kv"><span class="k">Time wallet</span><span class="v" style="color:var(--cyan)">${fmtHM(m.time_balance_seconds)}</span></div>
               <div class="kv"><span class="k">Points</span><span class="v">${m.points}</span></div>
               <div class="kv"><span class="k">Joined</span><span class="v">${fmtDateTime(m.created_at)}</span></div>
               <div class="kv"><span class="k">Last login</span><span class="v">${fmtDateTime(m.last_login_at)}</span></div></div>
          <div class="scroll"><div class="section-label">// SESSIONS</div>
            ${ss.sessions.length ? `<table class="data-table"><tbody>${ss.sessions.slice(0, 15).map((s) => `<tr><td class="mono" style="color:var(--text-muted)">${fmtDateTime(s.started_at)}</td><td>${esc(s.station ? s.station.name : '')}</td><td class="mono">${s.active ? '<span class="pill pill-session">LIVE</span>' : fmtHM(s.seconds_used || 0)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">NO SESSIONS</div>'}
          </div></div>
        <div class="section-label" style="margin-top:14px">// PURCHASES</div>
        <div class="scroll">${tx.transactions.length ? `<table class="data-table"><tbody>${tx.transactions.map((t) => `<tr><td class="mono" style="color:var(--text-muted)">${fmtDateTime(t.created_at)}</td><td>${esc(t.package_name || (t.kind === 'adjust' ? 'adjustment' : 'custom'))}</td><td class="mono">${fmtHM(t.seconds)}</td><td class="mono">${fmtMoney(t.amount)}</td><td class="sub">${esc(t.staff || '')} ${esc(t.note || '')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">NO PURCHASES</div>'}</div>`,
      buttons: [{ text: 'CLOSE' }, { text: 'TOP UP', cls: 'btn-primary', onClick: () => { closeModal(); topupMember(id); return true; } }],
    });
  }

  // ------------------------------------------------------------------ pricing
  async function loadPricing() {
    const [g, p] = await Promise.all([api('/groups'), api('/packages')]);
    state.groups = g.groups; state.packages = p.packages;
  }
  async function renderPricing() {
    await loadPricing();
    $('#groups-table').innerHTML = `<table class="data-table"><thead><tr><th>Group</th><th>Rate / hour</th><th style="text-align:right"></th></tr></thead><tbody>
      ${state.groups.map((g) => `<tr><td>${groupPill(g.name)}</td><td class="mono">${fmtMoney(g.rate_per_hour)}</td><td class="actions"><button class="btn-link" data-gedit="${g.id}">EDIT</button></td></tr>`).join('')}</tbody></table>`;
    $('#packages-table').innerHTML = `<table class="data-table"><thead><tr><th>Package</th><th>Time</th><th>Price</th><th>Group</th><th style="text-align:right"></th></tr></thead><tbody>
      ${state.packages.map((p) => `<tr class="${p.enabled ? '' : 'row-dim'}"><td>${esc(p.name)}</td><td class="mono">${fmtHM(p.seconds)}</td><td class="mono">${fmtMoney(p.price)}</td><td>${p.group_id ? groupPill((state.groups.find((g) => g.id === p.group_id) || {}).name) : '<span class="sub">ALL</span>'}</td><td class="actions"><button class="btn-link" data-pedit="${p.id}">EDIT</button></td></tr>`).join('')}</tbody></table>`;
    $$('[data-gedit]').forEach((b) => b.addEventListener('click', () => groupForm(state.groups.find((g) => g.id === Number(b.dataset.gedit)))));
    $$('[data-pedit]').forEach((b) => b.addEventListener('click', () => packageForm(state.packages.find((p) => p.id === Number(b.dataset.pedit)))));
  }
  function groupForm(g) {
    openModal({
      label: g ? '// EDIT GROUP' : '// NEW GROUP', title: g ? g.name : 'Station group',
      body: `<label class="form-label">Name</label><input type="text" id="g-name" value="${esc(g ? g.name : '')}" placeholder="VIP">
             <label class="form-label">Rate per hour (${esc(cur())})</label><input type="number" id="g-rate" step="0.01" min="0" value="${g ? (g.rate_per_hour / 100) : ''}">`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE', cls: 'btn-primary', onClick: async (wrap) => {
        const body = { name: $('#g-name', wrap).value.trim(), rate_per_hour: Math.round(Number($('#g-rate', wrap).value) * 100) };
        await api(g ? `/groups/${g.id}` : '/groups', { method: g ? 'PATCH' : 'POST', body });
        toast('Group saved'); renderPricing().catch(fail);
      } }],
    });
  }
  function packageForm(p) {
    openModal({
      label: p ? '// EDIT PACKAGE' : '// NEW PACKAGE', title: p ? p.name : 'Time package',
      body: `<label class="form-label">Name</label><input type="text" id="p-name" value="${esc(p ? p.name : '')}" placeholder="2 hours">
             <div class="form-row"><div><label class="form-label">Minutes</label><input type="number" id="p-min" min="1" value="${p ? Math.round(p.seconds / 60) : ''}"></div>
             <div><label class="form-label">Price (${esc(cur())})</label><input type="number" id="p-price" step="0.01" min="0" value="${p ? (p.price / 100) : ''}"></div></div>
             <label class="form-label">Only for group</label><select id="p-group"><option value="">All groups</option>${state.groups.map((g) => `<option value="${g.id}" ${p && p.group_id === g.id ? 'selected' : ''}>${esc(g.name)}</option>`).join('')}</select>
             ${p ? `<label class="switch"><input type="checkbox" id="p-enabled" ${p.enabled ? 'checked' : ''}> ENABLED (shown when selling)</label>` : ''}`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE', cls: 'btn-primary', onClick: async (wrap) => {
        const body = { name: $('#p-name', wrap).value.trim(), seconds: Math.round(Number($('#p-min', wrap).value) * 60), price: Math.round(Number($('#p-price', wrap).value) * 100), group_id: $('#p-group', wrap).value ? Number($('#p-group', wrap).value) : null };
        if (p) body.enabled = $('#p-enabled', wrap).checked;
        await api(p ? `/packages/${p.id}` : '/packages', { method: p ? 'PATCH' : 'POST', body });
        toast('Package saved'); renderPricing().catch(fail);
      } }],
    });
  }

  // ------------------------------------------------------------------ sales
  async function loadSales() {
    const [tx, ss] = await Promise.all([api(`/transactions?limit=200${state.salesMode === 'today' ? '&today=true' : ''}`), api('/sessions?limit=100')]);
    const total = tx.transactions.reduce((a, t) => a + (t.amount || 0), 0);
    $('#sales-table').innerHTML = tx.transactions.length ? `<table class="data-table"><thead><tr><th>Time</th><th>Type</th><th>Who</th><th>Item</th><th>Time</th><th>Amount</th><th>Staff</th><th>Note</th></tr></thead><tbody>
      ${tx.transactions.map((t) => `<tr><td class="mono" style="color:var(--text-muted)">${fmtDateTime(t.created_at)}</td><td class="mono">${esc(t.kind.toUpperCase())}</td>
        <td>${t.member ? esc(t.member) : (t.station ? `<span class="pill pill-guest">GUEST</span> ${esc(t.station)}` : '—')}</td><td>${esc(t.package_name || 'custom')}</td>
        <td class="mono">${fmtHM(t.seconds)}</td><td class="mono" style="color:var(--cyan)">${fmtMoney(t.amount)}</td><td class="sub">${esc(t.staff || 'kiosk')}</td><td class="sub">${esc(t.note || '')}</td></tr>`).join('')}
      <tr><td colspan="5" class="mono" style="color:var(--text-dim)">TOTAL · ${tx.transactions.length} SALES</td><td class="mono" style="color:var(--magenta)">${fmtMoney(total)}</td><td colspan="2"></td></tr></tbody></table>` : '<div class="empty">NO SALES IN THIS PERIOD</div>';
    $('#sessions-table').innerHTML = ss.sessions.length ? `<table class="data-table"><thead><tr><th>Started</th><th>Ended</th><th>Station</th><th>User</th><th>Used</th><th>Reason</th></tr></thead><tbody>
      ${ss.sessions.map((s) => `<tr><td class="mono" style="color:var(--text-muted)">${fmtDateTime(s.started_at)}</td><td class="mono" style="color:var(--text-muted)">${s.active ? '<span class="pill pill-session">LIVE</span>' : fmtDateTime(s.ended_at)}</td>
        <td>${esc(s.station ? s.station.name : '')}</td><td>${userCell(s)}</td><td class="mono">${s.active ? fmtHM(s.elapsed_seconds) : fmtHM(s.seconds_used || 0)}</td><td class="mono sub">${esc(s.end_reason || '')}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">NO SESSIONS YET</div>';
    $$('[data-member]', $('#sessions-table')).forEach((m) => m.addEventListener('click', () => memberDetails(Number(m.dataset.member))));
  }

  // ------------------------------------------------------------------ settings
  async function loadSettings() {
    const s = await api('/settings');
    state.settings = { ...state.settings, ...s };
    $('#set-cafe').value = s.cafe_name; $('#set-currency').value = s.currency;
    $('#set-min').value = Math.round(s.min_session_seconds / 60); $('#set-autoreg').checked = !!s.auto_register_stations;
    $('#srv-url').textContent = location.origin + '/admin/';
    $('#srv-ws').textContent = `ws://${location.host}/ws/station`;
    try { const h = await fetch('/health').then((r) => r.json()); $('#srv-version').textContent = 'v' + h.version; } catch (e) { /* ignore */ }
    const ev = await api('/audit?limit=100');
    $('#events-table').innerHTML = eventsTable(ev.events);
  }
  async function saveSettings() {
    const s = await api('/settings', { method: 'PUT', body: { cafe_name: $('#set-cafe').value, currency: $('#set-currency').value, min_session_seconds: Math.round(Number($('#set-min').value) * 60), auto_register_stations: $('#set-autoreg').checked } });
    state.settings = { ...state.settings, ...s };
    $('#dash-cafe').textContent = s.cafe_name.toUpperCase();
    toast('Settings saved');
  }

  // ------------------------------------------------------------------ shop · pending orders
  const orderUser = (o) => o.member
    ? `<span class="member-link" data-member="${o.member.id}">${esc(o.member.username)}</span>`
    : '<span class="pill pill-guest">GUEST</span>';
  const orderStatusPill = (s) => ({
    pending: '<span class="pill pill-locked">PENDING</span>',
    done: '<span class="pill pill-free">DONE</span>',
    cancelled: '<span class="pill pill-disabled">CANCELLED</span>',
  }[s] || `<span class="pill">${esc(s)}</span>`);
  const itemCell = (o) => `${esc(o.product_name)} <span class="mono" style="color:var(--text-muted)">×${Number(o.qty) || 1}</span>`;

  async function loadShop() {
    await Promise.all([loadOrders(), loadProducts(), loadOrderHistory()]);
  }
  async function loadOrders() {
    const r = await api('/orders');
    state.orders = r.orders || [];
    renderOrders(true);
  }
  function updateShopDesc() {
    $('#shop-desc').textContent = `// ${state.orders.length} PENDING · ${state.products.filter((p) => p.enabled).length} OF ${state.products.length} PRODUCTS ON THE KIOSK`;
  }

  // Live queue: fed by GET /orders when the page opens and by the socket 'orders' pushes after that.
  // Same trick as renderStations — only touch the DOM when the queue really changed, so a DONE
  // button never disappears under the cursor because of an unrelated push.
  function renderOrders(force = false) {
    const o = state.orders;
    const badge = $('#nav-orders-badge');
    badge.textContent = o.length; badge.hidden = !o.length;
    const fp = JSON.stringify(o.map((x) => [x.id, x.status, x.qty, x.total]));
    if (!force && fp === state.ordersFp) return;
    state.ordersFp = fp;
    updateShopDesc();
    if (!o.length) { $('#orders-table').innerHTML = '<div class="empty">NO PENDING ORDERS</div>'; return; }
    $('#orders-table').innerHTML = `<table class="data-table"><thead><tr><th>Station</th><th>User</th><th>Item</th><th>Total</th><th>Time</th><th style="text-align:right">Actions</th></tr></thead><tbody>
      ${o.map((x) => `<tr>
        <td><span class="station-name">${esc(x.station ? x.station.name : '—')}</span></td>
        <td>${orderUser(x)}</td>
        <td>${itemCell(x)}${x.note ? `<div class="sub">${esc(x.note)}</div>` : ''}</td>
        <td class="mono" style="color:var(--cyan)">${fmtMoney(x.total)}</td>
        <td class="mono" style="color:var(--text-muted)">${fmtTime(x.created_at)}</td>
        <td class="actions"><button class="btn-link green" data-order="done" data-id="${x.id}">DONE</button><button class="btn-link danger" data-order="cancel" data-id="${x.id}">CANCEL</button></td></tr>`).join('')}
    </tbody></table>`;
    const root = $('#orders-table');
    $$('[data-order]', root).forEach((b) => b.addEventListener('click', () => orderAction(b.dataset.order, Number(b.dataset.id))));
    $$('[data-member]', root).forEach((m) => m.addEventListener('click', () => memberDetails(Number(m.dataset.member)).catch(fail)));
  }

  function orderAction(act, id) {
    const o = state.orders.find((x) => x.id === id);
    if (!o) return;
    const run = async () => {
      await api(`/orders/${id}/${act}`, { method: 'POST' });
      toast(act === 'done' ? `${o.product_name} ×${o.qty} delivered · ${fmtMoney(o.total)}` : 'Order cancelled');
      // The server broadcasts the new queue over the socket; refresh anyway in case the link is down.
      loadOrders().catch(() => {});
      if (state.page === 'shop') loadOrderHistory().catch(() => {});
    };
    if (act === 'cancel') {
      confirmModal(`Cancel ${o.product_name} ×${o.qty}?`, `Ordered from <b>${esc(o.station ? o.station.name : 'a station')}</b>. The customer is told the order was cancelled.`, run);
    } else run().catch(fail);
  }

  async function loadOrderHistory() {
    const [d, c] = await Promise.all([api('/orders?status=done&limit=50'), api('/orders?status=cancelled&limit=50')]);
    const when = (x) => String(x.updated_at || x.created_at || '');
    const rows = [...(d.orders || []), ...(c.orders || [])].sort((a, b) => when(b).localeCompare(when(a))).slice(0, 50);
    const root = $('#orders-history');
    root.innerHTML = rows.length ? `<table class="data-table"><thead><tr><th>Time</th><th>Station</th><th>User</th><th>Item</th><th>Total</th><th>Status</th></tr></thead><tbody>
      ${rows.map((x) => `<tr class="${x.status === 'cancelled' ? 'row-dim' : ''}"><td class="mono" style="color:var(--text-muted)">${fmtDateTime(x.updated_at || x.created_at)}</td>
        <td>${esc(x.station ? x.station.name : '—')}</td><td>${orderUser(x)}</td><td>${itemCell(x)}</td>
        <td class="mono">${fmtMoney(x.total)}</td><td>${orderStatusPill(x.status)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">NO ORDERS YET</div>';
    $$('[data-member]', root).forEach((m) => m.addEventListener('click', () => memberDetails(Number(m.dataset.member)).catch(fail)));
  }

  // ------------------------------------------------------------------ shop · products
  const CATEGORIES = ['drinks', 'snacks', 'meals'];
  const catPill = (c) => `<span class="pill pill-cat-${esc(c)}">${esc(String(c || '').toUpperCase())}</span>`;
  // ?v= cache-buster: a re-upload within the same second reuses the file name, and the browser
  // would otherwise keep showing the cached old picture.
  const thumb = (p) => p.image_url
    ? `<img class="thumb" src="${esc(p.image_url)}?v=${state.productsAt || 0}" alt="">`
    : `<div class="thumb thumb-empty">${esc((p.name || '?').charAt(0).toUpperCase())}</div>`;

  async function loadProducts() {
    const r = await api('/products');
    state.products = r.products || [];
    state.productsAt = Date.now();
    renderProducts();
  }
  function renderProducts() {
    const p = state.products;
    updateShopDesc();
    if (!p.length) { $('#products-table').innerHTML = '<div class="empty">NO PRODUCTS YET — CLICK + ADD PRODUCT</div>'; return; }
    $('#products-table').innerHTML = `<table class="data-table"><thead><tr><th></th><th>Product</th><th>Category</th><th>Price</th><th>Best</th><th>Enabled</th><th style="text-align:right">Actions</th></tr></thead><tbody>
      ${p.map((x) => `<tr class="${x.enabled ? '' : 'row-dim'}">
        <td style="width:56px">${thumb(x)}</td>
        <td>${esc(x.name)}<div class="sub">#${x.id} · SORT ${Number(x.sort) || 0}</div></td>
        <td>${catPill(x.category)}</td>
        <td class="mono">${fmtMoney(x.price)}</td>
        <td>${x.best ? '<span class="pill pill-gold">BEST</span>' : '<span class="sub">—</span>'}</td>
        <td>${x.enabled ? '<span class="pill pill-free">ON</span>' : '<span class="pill pill-disabled">OFF</span>'}</td>
        <td class="actions"><button class="btn-link" data-pact="edit" data-id="${x.id}">EDIT</button><button class="btn-link amber" data-pact="picture" data-id="${x.id}">PICTURE</button><button class="btn-link danger" data-pact="delete" data-id="${x.id}">DELETE</button></td></tr>`).join('')}
    </tbody></table>`;
    $$('[data-pact]', $('#products-table')).forEach((b) => b.addEventListener('click', () => productAction(b.dataset.pact, Number(b.dataset.id))));
  }

  function productAction(act, id) {
    const p = state.products.find((x) => x.id === id);
    if (!p) return;
    if (act === 'edit') productForm(p);
    else if (act === 'picture') pictureForm(p);
    else if (act === 'delete') {
      confirmModal(`Delete ${p.name}?`, 'Products that were ordered before are disabled instead of deleted, so order history stays intact.',
        async () => { await api(`/products/${p.id}`, { method: 'DELETE' }); toast(`${p.name} removed`); loadProducts().catch(fail); });
    }
  }

  function productForm(p) {
    const nextSort = state.products.reduce((m, x) => Math.max(m, Number(x.sort) || 0), -1) + 1;
    openModal({
      label: p ? '// EDIT PRODUCT' : '// NEW PRODUCT', title: p ? p.name : 'Shop product',
      body: `<label class="form-label">Name</label><input type="text" id="pr-name" value="${esc(p ? p.name : '')}" placeholder="Coca-Cola">
             <div class="form-row">
               <div><label class="form-label">Category</label><select id="pr-cat">${CATEGORIES.map((c) => `<option value="${c}" ${p && p.category === c ? 'selected' : ''}>${c.toUpperCase()}</option>`).join('')}</select></div>
               <div><label class="form-label">Price (${esc(cur())})</label><input type="number" id="pr-price" step="0.01" min="0" value="${p ? (p.price / 100) : ''}"></div>
               <div><label class="form-label">Sort</label><input type="number" id="pr-sort" value="${p ? (Number(p.sort) || 0) : nextSort}"></div>
             </div>
             <label class="switch"><input type="checkbox" id="pr-best" ${p && p.best ? 'checked' : ''}> BEST SELLER (featured on the kiosk)</label>
             <label class="switch"><input type="checkbox" id="pr-enabled" ${!p || p.enabled ? 'checked' : ''}> ENABLED (shown in the kiosk shop)</label>`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE', cls: 'btn-primary', onClick: async (wrap) => {
        const body = {
          name: $('#pr-name', wrap).value.trim(), category: $('#pr-cat', wrap).value,
          price: Math.round(Number($('#pr-price', wrap).value) * 100) || 0, sort: Math.round(Number($('#pr-sort', wrap).value)) || 0,
          best: $('#pr-best', wrap).checked, enabled: $('#pr-enabled', wrap).checked,
        };
        if (!body.name) throw { message: 'Give the product a name.' };
        await api(p ? `/products/${p.id}` : '/products', { method: p ? 'PATCH' : 'POST', body });
        toast('Product saved'); loadProducts().catch(fail);
      } }],
    });
  }

  // Shrinks any image to fit max×max (aspect kept) and returns it as PNG base64 without the data: prefix.
  function shrinkImage(file, max = 512) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file), img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        const iw = img.naturalWidth || 1, ih = img.naturalHeight || 1;
        const k = Math.min(1, max / Math.max(iw, ih));
        const w = Math.max(1, Math.round(iw * k)), h = Math.max(1, Math.round(ih * k));
        const c = document.createElement('canvas'); c.width = w; c.height = h;
        c.getContext('2d').drawImage(img, 0, 0, w, h);
        const dataUrl = c.toDataURL('image/png');
        resolve({ dataUrl, data: dataUrl.slice(dataUrl.indexOf(',') + 1), width: w, height: h });
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject({ message: 'That file is not a readable image.' }); };
      img.src = url;
    });
  }

  function pictureForm(p) {
    const preview = (src) => src ? `<img src="${esc(src)}" alt="">` : '<span class="sub">NO PICTURE</span>';
    openModal({
      label: '// PICTURE', title: p.name, desc: 'PNG, JPG or WEBP. The picture is shrunk to fit 512×512 in the browser, then uploaded as PNG.',
      body: `<div class="pic-preview" id="pic-preview">${preview(p.image_url ? p.image_url + '?v=' + Date.now() : '')}</div>
             <label class="form-label">Choose a file</label><input type="file" id="pic-file" accept="image/*">
             <div class="hint" id="pic-hint">${p.image_url ? esc(p.image || p.image_url) : 'No picture yet — the kiosk shows the first letter instead.'}</div>`,
      buttons: [{ text: 'CLOSE' },
        ...(p.image_url ? [{ text: 'REMOVE', cls: 'btn-magenta', onClick: async () => {
          await api(`/products/${p.id}/image`, { method: 'DELETE' });
          toast('Picture removed'); loadProducts().catch(fail);
        } }] : []),
        { text: 'UPLOAD', cls: 'btn-primary', onClick: async (wrap) => {
          if (!wrap._image) throw { message: 'Choose a picture first.' };
          await api(`/products/${p.id}/image`, { method: 'POST', body: wrap._image });
          toast('Picture saved'); loadProducts().catch(fail);
        } }],
      onOpen: (wrap) => {
        $('#pic-file', wrap).addEventListener('change', async (ev) => {
          const file = ev.target.files && ev.target.files[0];
          if (!file) return;
          try {
            const img = await shrinkImage(file);
            const stem = (file.name || 'picture').replace(/\.[^.]*$/, '').replace(/[^\w.-]+/g, '_') || 'picture';
            wrap._image = { filename: stem + '.png', data: img.data };
            $('#pic-preview', wrap).innerHTML = preview(img.dataUrl);
            $('#pic-hint', wrap).textContent = `${img.width}×${img.height} PNG · ${Math.max(1, Math.round(img.data.length * 0.75 / 1024))} KB · click UPLOAD`;
          } catch (e) { wrap._image = null; fail(e); }
        });
      },
    });
  }

  // ------------------------------------------------------------------ events (client banners)
  const EVENT_CATS = ['live', 'upcoming', 'weekly', 'weekend', 'tournament', 'offer'];
  const kindPill = (k) => k === 'offer' ? '<span class="pill pill-offer">OFFER</span>' : '<span class="pill pill-reg">EVENT</span>';
  const eventStatusPill = (s) => s === 'live' ? '<span class="pill pill-free">LIVE</span>' : '<span class="pill pill-upcoming">UPCOMING</span>';
  const toggle = (e, field, cls = '') => `<label class="toggle ${cls}"><input type="checkbox" data-toggle="${field}" data-id="${e.id}" ${e[field] ? 'checked' : ''}><span></span></label>`;

  async function loadEvents() {
    const r = await api('/events');
    state.events = r.events || [];
    renderEvents();
  }
  function renderEvents() {
    const ev = state.events;
    $('#events-desc').textContent = `// ${ev.length} EVENTS · ${ev.filter((e) => e.enabled).length} ENABLED · ${ev.filter((e) => e.enabled && e.show_home).length} ON HOME`;
    if (!ev.length) { $('#events-list').innerHTML = '<div class="empty">NO EVENTS — CLICK + ADD EVENT</div>'; return; }
    $('#events-list').innerHTML = `<table class="data-table"><thead><tr><th>Title</th><th>Kind</th><th>Game</th><th>When</th><th>Prize</th><th>Status</th><th>Enabled</th><th>Home</th><th>Events</th><th style="text-align:right">Actions</th></tr></thead><tbody>
      ${ev.map((e) => `<tr class="${e.enabled ? '' : 'row-dim'}">
        <td><span class="station-name">${esc(e.title)}</span>${e.tag ? `<div class="sub">${esc(e.tag)}</div>` : ''}</td>
        <td>${kindPill(e.kind)}</td>
        <td>${esc(e.game || '—')}${e.players ? `<div class="sub">${esc(e.players)}</div>` : ''}</td>
        <td class="mono">${esc(e.when || '—')}</td>
        <td class="mono" style="color:var(--amber)">${esc(e.prize || '—')}</td>
        <td>${eventStatusPill(e.status)}${e.cats && e.cats.length ? `<div class="sub">${esc(e.cats.join(', '))}</div>` : ''}</td>
        <td>${toggle(e, 'enabled')}</td><td>${toggle(e, 'show_home', 'home')}</td><td>${toggle(e, 'show_events')}</td>
        <td class="actions"><button class="btn-link" data-eact="edit" data-id="${e.id}">EDIT</button><button class="btn-link danger" data-eact="delete" data-id="${e.id}">DELETE</button></td></tr>`).join('')}
    </tbody></table>`;
    const root = $('#events-list');
    $$('[data-eact]', root).forEach((b) => b.addEventListener('click', () => eventAction(b.dataset.eact, Number(b.dataset.id))));
    // The three switches PATCH straight away; on failure the switch snaps back.
    $$('[data-toggle]', root).forEach((t) => t.addEventListener('change', async () => {
      const id = Number(t.dataset.id), field = t.dataset.toggle, value = t.checked;
      t.disabled = true;
      try {
        const e = await api(`/events/${id}`, { method: 'PATCH', body: { [field]: value } });
        // Merge only the toggled flag: two quick toggles on one row answer in parallel, and a
        // late response must not overwrite the other flag with a stale full view.
        state.events = state.events.map((x) => (x.id === id ? { ...x, [field]: e[field] } : x));
        renderEvents();
      } catch (err) { t.checked = !value; t.disabled = false; fail(err); }
    }));
  }

  function eventAction(act, id) {
    const e = state.events.find((x) => x.id === id);
    if (!e) return;
    if (act === 'edit') eventForm(e);
    else if (act === 'delete') {
      confirmModal(`Delete ${e.title}?`, 'The event disappears from every client right away. This cannot be undone.',
        async () => { await api(`/events/${id}`, { method: 'DELETE' }); toast('Event deleted'); loadEvents().catch(fail); });
    }
  }

  function eventForm(e) {
    const v = (k) => esc(e ? (e[k] ?? '') : '');
    const cats = e ? (e.cats || []) : ['upcoming'];
    const nextSort = state.events.reduce((m, x) => Math.max(m, Number(x.sort) || 0), -1) + 1;
    openModal({
      label: e ? '// EDIT EVENT' : '// NEW EVENT', title: e ? e.title : 'Event or offer', wide: true,
      body: `<label class="form-label">Title</label><input type="text" id="ev-title" value="${v('title')}" placeholder="VORTEX CUP 2026 · WEEK 3">
             <div class="form-row">
               <div><label class="form-label">Kind</label><select id="ev-kind"><option value="event" ${e && e.kind === 'offer' ? '' : 'selected'}>EVENT</option><option value="offer" ${e && e.kind === 'offer' ? 'selected' : ''}>OFFER</option></select></div>
               <div><label class="form-label">Status</label><select id="ev-status"><option value="upcoming" ${e && e.status === 'live' ? '' : 'selected'}>UPCOMING</option><option value="live" ${e && e.status === 'live' ? 'selected' : ''}>LIVE</option></select></div>
               <div><label class="form-label">Sort</label><input type="number" id="ev-sort" value="${e ? (Number(e.sort) || 0) : nextSort}"></div>
             </div>
             <div class="form-row">
               <div><label class="form-label">Game</label><input type="text" id="ev-game" value="${v('game')}" placeholder="VALORANT · 5v5"></div>
               <div><label class="form-label">Tag · small label</label><input type="text" id="ev-tag" value="${v('tag')}" placeholder="REGISTRATION OPEN"></div>
             </div>
             <div class="form-row">
               <div><label class="form-label">Players</label><input type="text" id="ev-players" value="${v('players')}" placeholder="256 players"></div>
               <div><label class="form-label">When</label><input type="text" id="ev-when" value="${v('when')}" placeholder="TOMORROW 8PM"></div>
               <div><label class="form-label">Prize</label><input type="text" id="ev-prize" value="${v('prize')}" placeholder="EGP 5,000"></div>
             </div>
             <label class="form-label">Categories · client filter chips</label>
             <div class="cat-grid">${EVENT_CATS.map((c) => `<label class="switch"><input type="checkbox" data-cat="${c}" ${cats.includes(c) ? 'checked' : ''}> ${c.toUpperCase()}</label>`).join('')}</div>
             <label class="form-label">Visibility</label>
             <label class="switch"><input type="checkbox" id="ev-enabled" ${!e || e.enabled ? 'checked' : ''}> ENABLED</label>
             <label class="switch"><input type="checkbox" id="ev-home" ${e && e.show_home ? 'checked' : ''}> SHOW ON HOME BANNER</label>
             <label class="switch"><input type="checkbox" id="ev-events" ${!e || e.show_events ? 'checked' : ''}> SHOW ON EVENTS PAGE</label>`,
      buttons: [{ text: 'CANCEL' }, { text: 'SAVE', cls: 'btn-primary', onClick: async (wrap) => {
        const body = {
          title: $('#ev-title', wrap).value.trim(), kind: $('#ev-kind', wrap).value, status: $('#ev-status', wrap).value,
          sort: Math.round(Number($('#ev-sort', wrap).value)) || 0,
          game: $('#ev-game', wrap).value.trim(), tag: $('#ev-tag', wrap).value.trim(), players: $('#ev-players', wrap).value.trim(),
          when: $('#ev-when', wrap).value.trim(), prize: $('#ev-prize', wrap).value.trim(),
          cats: $$('[data-cat]', wrap).filter((c) => c.checked).map((c) => c.dataset.cat),
          enabled: $('#ev-enabled', wrap).checked, show_home: $('#ev-home', wrap).checked, show_events: $('#ev-events', wrap).checked,
        };
        if (!body.title) throw { message: 'Give the event a title.' };
        await api(e ? `/events/${e.id}` : '/events', { method: e ? 'PATCH' : 'POST', body });
        toast('Event saved'); loadEvents().catch(fail);
      } }],
    });
  }

  async function setAllEvents(enable) {
    const r = await api(enable ? '/events/enable-all' : '/events/disable-all', { method: 'POST' });
    state.events = r.events || [];
    renderEvents();
    toast(enable ? 'All events enabled' : 'All events removed from the clients');
  }

  // ------------------------------------------------------------------ boot
  function updateClock() {
    const d = new Date();
    $('#topbar-time').textContent = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  updateClock(); setInterval(updateClock, 1000);

  $('#login-form').addEventListener('submit', login);
  $('#btn-logout').addEventListener('click', () => logout(true));
  $('#btn-new-member').addEventListener('click', newMember);
  $('#btn-add-station').addEventListener('click', addStation);
  $('#btn-add-group').addEventListener('click', () => groupForm(null));
  $('#btn-add-package').addEventListener('click', () => packageForm(null));
  $('#btn-add-product').addEventListener('click', () => productForm(null));
  $('#btn-add-event').addEventListener('click', () => eventForm(null));
  $('#btn-enable-events').addEventListener('click', () => setAllEvents(true).catch(fail));
  $('#btn-disable-events').addEventListener('click', () => confirmModal('Disable all events?', 'Every event and offer disappears from the client Home banner and Events page until you enable them again.', () => setAllEvents(false)));
  $('#btn-save-settings').addEventListener('click', () => saveSettings().catch(fail));
  $('#btn-save-password').addEventListener('click', async () => {
    try { await api('/staff/password', { method: 'POST', body: { current_password: $('#pw-current').value, new_password: $('#pw-new').value } }); $('#pw-current').value = $('#pw-new').value = ''; toast('Password changed'); } catch (e) { fail(e); }
  });
  $('#btn-save-pin').addEventListener('click', async () => {
    try { await api('/staff/pin', { method: 'POST', body: { password: $('#pin-password').value, pin: $('#pin-new').value.trim() } }); $('#pin-password').value = $('#pin-new').value = ''; toast('Exit PIN updated'); } catch (e) { fail(e); }
  });
  $$('.nav-item').forEach((n) => n.addEventListener('click', () => showPage(n.dataset.page)));
  $$('[data-sales]').forEach((t) => t.addEventListener('click', () => { state.salesMode = t.dataset.sales; $$('[data-sales]').forEach((x) => x.classList.toggle('active', x === t)); loadSales().catch(fail); }));
  let searchTimer = null;
  $('#member-search').addEventListener('input', (e) => { state.memberQuery = e.target.value; clearTimeout(searchTimer); searchTimer = setTimeout(() => loadMembers().catch(fail), 250); });
  $('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

  $('#login-server').textContent = 'SERVER · ' + location.host;
  fetch('/health').then((r) => r.json()).then((h) => { $('#login-version').textContent = 'v' + h.version; }).catch(() => {});

  (async () => {
    const token = store.get();
    if (token) {
      state.token = token;
      try { await enterConsole(); return; } catch (e) { state.token = null; store.clear(); }
    }
    setTimeout(() => $('#admin-id').focus(), 50);
  })();
})();
