'use strict';

/* MeGaA Clipper pro features: undo / redo, Whop campaigns + rule checks, the viral-moment finder,
   keyword colours + emojis, pop-ups (B-roll), speaker switches, the earnings tracker and export packs.
   Loaded after app.js and plugged in through its HOOKS. */

const P = { campaigns: [], projectCampaign: null, popups: [], media: new Map(), tracker: [], videoKey: null };

const PRO_ICONS = {
  undo: '<svg viewBox="0 0 24 24"><path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/></svg>',
  redo: '<svg viewBox="0 0 24 24"><path d="M15 14l5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/></svg>',
  money: '<svg viewBox="0 0 24 24"><path d="M12 2v20M17 6.5C17 4.6 14.8 4 12 4S7 5 7 7.5 10 10.5 12 11s5 1.5 5 4-2.2 3.5-5 3.5-5-.6-5-2.5"/></svg>',
  gear: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  spark: '<svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/></svg>',
  posted: '<svg viewBox="0 0 24 24"><path d="M4 12l5 5L20 6"/></svg>',
  pic: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 17l-5-5-9 8"/></svg>',
  go: '<svg viewBox="0 0 24 24"><path d="M8 5l11 7-11 7z"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  box: '<svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4v10l-9 4-9-4z"/><path d="M3 7l9 4 9-4M12 11v10"/></svg>',
};

/* ---------------------------------------------------------------- small helpers */

function modal(id, title, body, wide = false) {
  let node = document.getElementById(id);
  if (node) return node;
  node = document.createElement('div');
  node.className = 'modal';
  node.id = id;
  node.hidden = true;
  node.innerHTML = `<div class="modal-card${wide ? ' wide' : ''}"><div class="modal-head"><h2>${title}</h2>`
    + `<div class="spacer"></div><button class="icon-btn" data-close title="Close (Esc)">${PRO_ICONS.x}</button></div>`
    + `<div class="modal-body">${body}</div></div>`;
  node.addEventListener('click', (e) => { if (e.target === node || e.target.closest('[data-close]')) node.hidden = true; });
  document.body.append(node);
  return node;
}

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  for (const m of document.querySelectorAll('.modal:not(#player)')) if (!m.hidden) m.hidden = true;
}, true);

const money = (v) => `$${(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const count = (v) => (v || 0).toLocaleString();
const today = () => new Date().toISOString().slice(0, 10);

/* ---------------------------------------------------------------- top bar */

$('.top-right').insertAdjacentHTML('afterbegin', `
  <div class="tool-group">
    <button class="icon-btn" id="btn-undo" title="Undo (Ctrl+Z)" disabled>${PRO_ICONS.undo}</button>
    <button class="icon-btn" id="btn-redo" title="Redo (Ctrl+Y)" disabled>${PRO_ICONS.redo}</button>
  </div>
  <button class="camp-chip" id="btn-campaign" title="Whop campaign for this video – its rules are checked for every clip">
    <span class="camp-dot"></span><span id="camp-name">No campaign</span>
  </button>
  <button class="icon-btn" id="btn-earnings" title="Earnings tracker">${PRO_ICONS.money}</button>
  <button class="icon-btn" id="btn-settings" title="Settings">${PRO_ICONS.gear}</button>`);

/* ---------------------------------------------------------------- undo / redo */

const H = { undo: [], redo: [], current: null, pending: null, stable: 0, restoring: false };

function editorSnapshot() {
  return S.videoKey ? JSON.stringify({ editing: S.editing, clip: clipFields() }) : null;
}

/* every 250 ms: once the editor has stayed the same for a moment, that state becomes an undo step
   (so dragging a slider makes one step, not hundreds) */
setInterval(() => {
  if (H.restoring || !S.videoKey) return;
  const snap = editorSnapshot();
  if (snap !== H.pending) { H.pending = snap; H.stable = 0; return; }
  if (++H.stable === 1 && snap !== H.current) {
    if (H.current) { H.undo.push(H.current); if (H.undo.length > 150) H.undo.shift(); }
    H.current = snap;
    H.redo = [];
    historyButtons();
  }
}, 250);

function historyButtons() {
  $('#btn-undo').disabled = !H.undo.length;
  $('#btn-redo').disabled = !H.redo.length;
}

function restoreSnapshot(snap) {
  H.restoring = true;
  const { editing, clip } = JSON.parse(snap);
  applyClipFields(clip);
  setEditing(editing);
  el.fName.value = clip.name;
  H.current = H.pending = snap;
  H.restoring = false;
  historyButtons();
}

function undo() {
  if (!H.undo.length) return;
  H.redo.push(H.current);
  restoreSnapshot(H.undo.pop());
}

function redo() {
  if (!H.redo.length) return;
  H.undo.push(H.current);
  restoreSnapshot(H.redo.pop());
}

function resetHistory() {
  H.undo = []; H.redo = []; H.current = H.pending = null;
  historyButtons();
}

$('#btn-undo').onclick = undo;
$('#btn-redo').onclick = redo;
document.addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey)) return;
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.isContentEditable;
  if (typing) return;  // text boxes keep their own undo
  const key = e.key.toLowerCase();
  if (key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
  else if (key === 'y' || (key === 'z' && e.shiftKey)) { e.preventDefault(); redo(); }
}, true);

/* ---------------------------------------------------------------- campaigns + rule checks */

const campaignModal = modal('campaigns', 'Whop campaigns', `
  <div class="camp-layout">
    <div class="camp-side">
      <div class="camp-list" id="camp-list"></div>
      <button class="btn ghost small" id="camp-new">+ New campaign</button>
    </div>
    <form class="camp-form" id="camp-form" autocomplete="off">
      <input type="hidden" name="id">
      <label class="field"><span class="label">Name</span><input class="input" name="name" placeholder="e.g. Kanine podcast clips"></label>
      <div class="form-row">
        <label class="field"><span class="label">Pay per 1,000 views ($)</span><input class="input mono" name="cpm" type="number" step="0.01" min="0" value="1"></label>
        <label class="field"><span class="label">Max speed (0 = any)</span><input class="input mono" name="max_speed" type="number" step="0.05" min="0" max="2" value="0"></label>
      </div>
      <div class="form-row">
        <label class="field"><span class="label">Min length (s)</span><input class="input mono" name="min_len" type="number" min="0" value="0"></label>
        <label class="field"><span class="label">Max length (s)</span><input class="input mono" name="max_len" type="number" min="0" value="0"></label>
      </div>
      <label class="field"><span class="label">Required tags in the post caption</span><input class="input" name="tags" placeholder="#ad @brandname #partner"></label>
      <label class="field"><span class="label">Required watermark text</span><input class="input" name="watermark" placeholder="leave empty if none"></label>
      <label class="switch"><input type="checkbox" name="no_hook"><span></span>No text on top (hook not allowed)</label>
      <label class="switch"><input type="checkbox" name="need_captions"><span></span>Captions are required</label>
      <label class="field"><span class="label">Notes</span><textarea class="input" name="notes" rows="2" placeholder="anything else from the campaign brief"></textarea></label>
      <div class="sub-row">
        <button class="btn primary small" type="submit">Save campaign</button>
        <button class="btn ghost small" type="button" id="camp-use">Use for this video</button>
        <div class="spacer"></div>
        <button class="btn ghost small danger-btn" type="button" id="camp-delete">Delete</button>
      </div>
    </form>
  </div>`, true);

const campForm = $('#camp-form');

async function loadCampaigns() {
  try {
    P.campaigns = (await api.get('/api/campaigns')).campaigns;
  } catch { P.campaigns = []; }
  renderCampaignList();
  campaignChip();
}

function currentCampaign() {
  return P.campaigns.find((c) => c.id === P.projectCampaign) || null;
}

function campaignSummary(c) {
  const len = c.min_len || c.max_len ? `${c.min_len || 0}–${c.max_len || '∞'}s` : 'any length';
  return `${money(c.cpm)} / 1k views · ${len}`;
}

function renderCampaignList() {
  const list = $('#camp-list');
  if (!P.campaigns.length) {
    list.innerHTML = '<div class="hint">No campaigns yet. Fill in the form to add your first Whop campaign.</div>';
    return;
  }
  list.innerHTML = P.campaigns.map((c) => `
    <button class="camp-item${c.id === campForm.elements.id.value ? ' on' : ''}" data-id="${c.id}">
      <span class="camp-item-name">${escapeHtml(c.name)}${c.id === P.projectCampaign ? ' <span class="pill ready">in use</span>' : ''}</span>
      <span class="hint mono">${campaignSummary(c)}</span>
    </button>`).join('');
}

function fillCampaignForm(c) {
  const f = campForm.elements;
  f.id.value = c?.id || '';
  f.name.value = c?.name || '';
  f.cpm.value = c?.cpm ?? 1;
  f.max_speed.value = c?.max_speed ?? 0;
  f.min_len.value = c?.min_len ?? 0;
  f.max_len.value = c?.max_len ?? 0;
  f.tags.value = c?.tags || '';
  f.watermark.value = c?.watermark || '';
  f.no_hook.checked = !!c?.no_hook;
  f.need_captions.checked = !!c?.need_captions;
  f.notes.value = c?.notes || '';
  $('#camp-delete').hidden = !c;
  $('#camp-use').hidden = !c || !S.videoKey;
  renderCampaignList();
}

$('#camp-list').onclick = (e) => {
  const item = e.target.closest('.camp-item');
  if (item) fillCampaignForm(P.campaigns.find((c) => c.id === item.dataset.id));
};
$('#camp-new').onclick = () => { fillCampaignForm(null); campForm.elements.name.focus(); };
campForm.onsubmit = async (e) => {
  e.preventDefault();
  const f = campForm.elements;
  const data = {
    id: f.id.value || null, name: f.name.value, cpm: +f.cpm.value, max_speed: +f.max_speed.value,
    min_len: +f.min_len.value, max_len: +f.max_len.value, tags: f.tags.value, watermark: f.watermark.value,
    no_hook: f.no_hook.checked, need_captions: f.need_captions.checked, notes: f.notes.value,
  };
  try {
    const { campaign } = await api.post('/api/campaigns', data);
    await loadCampaigns();
    fillCampaignForm(campaign);
    toast(`Saved “${campaign.name}”`, 'ok');
  } catch (err) { toast(err.message, 'error'); }
};
$('#camp-delete').onclick = async () => {
  const id = campForm.elements.id.value;
  const c = P.campaigns.find((x) => x.id === id);
  if (!c || !confirm(`Delete the campaign “${c.name}”?`)) return;
  await api.post('/api/campaigns/delete', { id });
  if (P.projectCampaign === id) await setProjectCampaign(null);
  await loadCampaigns();
  fillCampaignForm(null);
};
$('#camp-use').onclick = async () => {
  const id = campForm.elements.id.value;
  await setProjectCampaign(P.projectCampaign === id ? null : id);
};

async function setProjectCampaign(id) {
  try {
    await api.post('/api/project-campaign', { id });
    P.projectCampaign = id;
    campaignChip();
    renderCampaignList();
    S.cardsSig = '';
    await refresh();
    toast(id ? `This video now uses “${currentCampaign()?.name}” – clips are checked against its rules` : 'Campaign removed from this video', 'ok');
  } catch (err) { toast(err.message, 'error'); }
}

function campaignChip() {
  const c = currentCampaign();
  $('#camp-name').textContent = c ? c.name : 'No campaign';
  $('#btn-campaign').classList.toggle('on', !!c);
  $('#camp-use').textContent = c && c.id === campForm.elements.id.value ? 'Stop using for this video' : 'Use for this video';
}

$('#btn-campaign').onclick = () => {
  fillCampaignForm(currentCampaign() || P.campaigns[0] || null);
  campaignModal.hidden = false;
};

/* the same rules as library.check_clip, run live on the clip being edited */
function checkClip(clip, camp, duration) {
  if (!camp) return [];
  const out = [];
  if (camp.min_len && duration < camp.min_len - 0.05) out.push({ level: 'error', text: `Too short: ${duration.toFixed(1)}s – needs ${camp.min_len}s+` });
  if (camp.max_len && duration > camp.max_len + 0.05) out.push({ level: 'error', text: `Too long: ${duration.toFixed(1)}s – max ${camp.max_len}s` });
  const tags = (camp.tags || '').split(/[\s,]+/).filter(Boolean);
  const post = (clip.post_caption || '').toLowerCase();
  const missing = tags.filter((t) => !post.includes(t.toLowerCase()));
  if (missing.length) out.push({ level: 'warn', text: `Post caption is missing ${missing.join(' ')}` });
  if (camp.watermark && !(clip.watermark || '').toLowerCase().includes(camp.watermark.toLowerCase())) {
    out.push({ level: 'error', text: `Watermark must include “${camp.watermark}”` });
  }
  if (camp.no_hook && (clip.hook || '').trim()) out.push({ level: 'error', text: 'Hook text on top is not allowed' });
  if (camp.need_captions && clip.captions === false) out.push({ level: 'error', text: 'Captions are required' });
  if (camp.max_speed && (clip.speed || 1) > camp.max_speed + 0.001) out.push({ level: 'error', text: `Speed above ${camp.max_speed}×` });
  return out;
}

$('[data-pane="clip"]').insertAdjacentHTML('afterbegin', '<div class="rule-box" id="rule-box" hidden></div>');

function liveChecks() {
  const camp = currentCampaign();
  if (!camp || S.inT == null || S.outT == null) return null;
  return checkClip(clipFields(), camp, editState().duration);
}

setInterval(() => {
  const box = $('#rule-box');
  const camp = currentCampaign();
  const checks = liveChecks();
  if (!camp || !checks) { box.hidden = true; return; }
  box.hidden = false;
  const html = checks.length
    ? checks.map((c) => `<div class="rule ${c.level}">${c.level === 'error' ? '✕' : '!'} ${escapeHtml(c.text)}</div>`).join('')
    : '<div class="rule ok">✓ Fits all the campaign rules</div>';
  const full = `<div class="rule-title">${escapeHtml(camp.name)}</div>${html}`;
  if (box.innerHTML !== full) box.innerHTML = full;
}, 400);

/* warn before rendering a clip that breaks the campaign's rules */
const renderOneHandler = el.btnRenderOne.onclick;
el.btnRenderOne.onclick = (e) => {
  const errors = (liveChecks() || []).filter((c) => c.level === 'error');
  if (errors.length && !confirm(`This clip breaks the campaign rules:\n\n• ${errors.map((c) => c.text).join('\n• ')}\n\nRender anyway?`)) return;
  renderOneHandler(e);
};
const renderAllHandler = el.btnRenderAll.onclick;
el.btnRenderAll.onclick = (e) => {
  const bad = S.clips.filter((c) => (c.checks || []).some((x) => x.level === 'error'));
  if (bad.length && !confirm(`${bad.length} clip${bad.length === 1 ? '' : 's'} break the campaign rules (${bad.map((c) => c.name).join(', ')}).\n\nRender all anyway?`)) return;
  renderAllHandler(e);
};

/* ---------------------------------------------------------------- viral-moment finder */

$('.transcript .panel-head .search').insertAdjacentHTML('beforebegin',
  `<button class="btn ghost small moments-btn" id="btn-moments" title="Find the best clips in this video">${PRO_ICONS.spark}Moments</button>`);

const momentsModal = modal('moments', 'Viral moments', `
  <div class="mo-controls">
    <label class="mo-opt"><span class="label">Clips</span><input class="input mono" id="mo-count" type="number" min="1" max="30" value="10"></label>
    <label class="mo-opt"><span class="label">Min s</span><input class="input mono" id="mo-min" type="number" min="5" value="20"></label>
    <label class="mo-opt"><span class="label">Max s</span><input class="input mono" id="mo-max" type="number" min="5" value="60"></label>
    <div class="spacer"></div>
    <button class="btn primary small" id="mo-find">Find (free)</button>
    <button class="btn ghost small" id="mo-ai" title="Uses Claude through your API key – about $0.10–0.20 per hour of video">${PRO_ICONS.spark}AI picks</button>
  </div>
  <div class="mo-head"><span class="hint" id="mo-note">Free picks score every sentence-to-sentence stretch for a strong opening line, keywords, energy and a punchy ending.</span>
    <button class="btn ghost small" id="mo-add-all" hidden>Add all to queue</button></div>
  <div class="mo-list" id="mo-list"></div>`, true);

P.moments = [];

$('#btn-moments').onclick = () => {
  if (!S.lines.length) { toast('Transcribe the video first.', 'info'); return; }
  const camp = currentCampaign();
  if (camp && camp.min_len) $('#mo-min').value = camp.min_len;
  if (camp && camp.max_len) $('#mo-max').value = camp.max_len;
  momentsModal.hidden = false;
  if (!P.moments.length) findMoments();
};

function momentOptions() {
  return { count: +$('#mo-count').value || 10, min: +$('#mo-min').value || 20, max: +$('#mo-max').value || 60 };
}

P.momentsSeq = 0;

async function findMoments() {
  const o = momentOptions();
  const seq = ++P.momentsSeq;  // an older, slower search must not overwrite a newer one
  $('#mo-list').innerHTML = '<div class="mo-wait">Scoring the transcript…</div>';
  try {
    const res = await api.get(`/api/moments?count=${o.count}&min=${o.min}&max=${o.max}`);
    if (seq !== P.momentsSeq) return;
    P.moments = res.moments;
    $('#mo-note').textContent = 'Free picks: ranked by opening line, keywords, energy, pace and ending.';
    renderMoments();
  } catch (err) { $('#mo-list').innerHTML = ''; toast(err.message, 'error'); }
}

async function aiMoments() {
  const settings = await api.get('/api/settings');
  if (!settings.has_key) {
    toast('Add your Anthropic API key in Settings first.', 'info', { label: 'Settings', fn: openSettings });
    return;
  }
  const o = momentOptions();
  const seq = ++P.momentsSeq;
  $('#mo-list').innerHTML = '<div class="mo-wait"><span class="spin"></span>Claude is reading the transcript… (about a minute)</div>';
  $('#mo-ai').disabled = true;
  try {
    const res = await api.post('/api/moments-ai', o);
    if (seq !== P.momentsSeq) return;
    P.moments = res.moments;
    $('#mo-note').textContent = `AI picks by Claude · this request cost about $${res.cost.toFixed(2)}.`;
    renderMoments();
  } catch (err) {
    $('#mo-list').innerHTML = '';
    toast(err.message, 'error');
  } finally { $('#mo-ai').disabled = false; }
}

function renderMoments() {
  $('#mo-add-all').hidden = !P.moments.length;
  if (!P.moments.length) { $('#mo-list').innerHTML = '<div class="mo-wait">No moments found – try a shorter min length.</div>'; return; }
  $('#mo-list').innerHTML = P.moments.map((m, i) => `
    <div class="mo-row" data-i="${i}">
      <div class="mo-score" style="--s:${m.score}%"><span>${m.score}</span></div>
      <div class="mo-main">
        <div class="mo-hook">${escapeHtml(m.hook)}</div>
        <div class="mo-meta mono">${fmt(m.start)} → ${fmt(m.end)} · ${(m.end - m.start).toFixed(0)}s · ${escapeHtml(m.why.join(' · '))}</div>
        ${m.post_caption ? `<div class="mo-post">${escapeHtml(m.post_caption)}</div>` : ''}
      </div>
      <button class="btn ghost small" data-mo="preview">${PRO_ICONS.go}Preview</button>
      <button class="btn primary small" data-mo="add">Add</button>
    </div>`).join('');
}

async function addMoment(m) {
  newClip(false);
  setRange(m.start, m.end);
  el.fHook.value = m.hook || '';
  el.fPost.value = m.post_caption || '';
  await addClip(false);
}

$('#mo-find').onclick = findMoments;
$('#mo-ai').onclick = aiMoments;
$('#mo-list').onclick = async (e) => {
  const row = e.target.closest('.mo-row');
  const act = e.target.closest('[data-mo]')?.dataset.mo;
  if (!row || !act) return;
  const m = P.moments[+row.dataset.i];
  if (act === 'preview') {
    newClip(false);
    setRange(m.start, m.end);
    el.fHook.value = m.hook || '';
    el.fPost.value = m.post_caption || '';
    momentsModal.hidden = true;
    seek(m.start);
    video.play().catch(() => {});
  } else {
    await addMoment(m);
    e.target.closest('[data-mo]').outerHTML = '<span class="pill ready">Added</span>';
  }
};
$('#mo-add-all').onclick = async () => {
  for (const m of P.moments) await addMoment(m);
  momentsModal.hidden = true;
  toast(`Added ${P.moments.length} clips to the queue – check them, then Render all.`, 'ok');
};

/* ---------------------------------------------------------------- settings (API key) */

const settingsModal = modal('settings', 'Settings', `
  <label class="field"><span class="label">Anthropic API key <span class="dim">· for AI moment picks</span></span>
    <input class="input mono" id="set-key" type="password" placeholder="sk-ant-…" autocomplete="off"></label>
  <div class="hint" id="set-key-hint"></div>
  <p class="hint">AI picks send the transcript text (not the video) to Claude Opus 5.5 and cost about $0.10–0.20 per hour
    of video. If Claude declines a request, it's retried automatically on a fallback model. The key is stored only on this PC
    (clipper/data/settings.json). Get a key at console.anthropic.com.</p>
  <div class="sub-row"><button class="btn primary small" id="set-save">Save</button>
    <button class="btn ghost small" id="set-clear">Remove key</button></div>`);

async function openSettings() {
  const s = await api.get('/api/settings');
  $('#set-key').value = '';
  $('#set-key-hint').textContent = s.has_key ? `A key is saved (${s.key_hint}).` : 'No key saved – AI picks are off; free picks still work.';
  settingsModal.hidden = false;
}
$('#btn-settings').onclick = openSettings;
$('#set-save').onclick = async () => {
  const key = $('#set-key').value.trim();
  if (!key) { toast('Paste your API key first.', 'info'); return; }
  await api.post('/api/settings', { api_key: key });
  settingsModal.hidden = true;
  toast('API key saved.', 'ok');
};
$('#set-clear').onclick = async () => {
  await api.post('/api/settings', { api_key: '' });
  openSettings();
};

/* ---------------------------------------------------------------- keyword colours + emojis */

const KW_COLORS = ['#39FF14', '#00E5FF', '#FF2BD6', '#FFD400', '#FF3B30', '#FF9500'];

$('#color-field').insertAdjacentHTML('afterend', `
  <div class="field" id="kw-field">
    <label class="switch big"><input type="checkbox" id="kw-on"><span></span>Colour keywords</label>
    <div class="swatches" id="kw-colors"></div>
    <label class="switch big"><input type="checkbox" id="kw-emojis"><span></span>Emojis on keywords 💰🔥🤯</label>
    <span class="hint">Money, numbers and strong words get their own colour; a matching emoji pops up above the captions.</span>
  </div>`);

function renderKw() {
  $('#kw-on').checked = S.kw.on;
  $('#kw-emojis').checked = S.kw.emojis;
  $('#kw-colors').innerHTML = KW_COLORS.map((c) =>
    `<button class="swatch${S.kw.color === c ? ' on' : ''}" data-color="${c}" style="background:${c}"></button>`).join('');
  $('#kw-colors').classList.toggle('dim-off', !S.kw.on);
}
$('#kw-on').onchange = () => { S.kw.on = $('#kw-on').checked; renderKw(); };
$('#kw-emojis').onchange = () => { S.kw.emojis = $('#kw-emojis').checked; renderKw(); };
$('#kw-colors').onclick = (e) => {
  const b = e.target.closest('button');
  if (b) { S.kw.color = b.dataset.color; S.kw.on = true; renderKw(); }
};

/* ffmpeg can't draw colour emojis, so the window draws each one once and saves it as a picture */
async function ensureEmojiPictures() {
  try {
    const { emojis } = await api.get('/api/emoji-needed');
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 160;
    const c = canvas.getContext('2d');
    for (const emoji of emojis) {
      c.clearRect(0, 0, 160, 160);
      c.font = '128px "Segoe UI Emoji"';
      c.textAlign = 'center';
      c.textBaseline = 'middle';
      c.fillText(emoji, 80, 88);
      await api.post('/api/emoji', { emoji, png: canvas.toDataURL('image/png') });
    }
  } catch { /* emojis are optional – the render simply skips any that are missing */ }
}

/* ---------------------------------------------------------------- speaker switches */

$('#crop-field').insertAdjacentHTML('afterend', `
  <div class="field" id="kf-field">
    <span class="label">Speaker switches</span>
    <div class="sub-row">
      <button class="btn ghost small" id="kf-add">+ Switch here</button>
      <span class="hint grow">Add a switch at the playhead, then drag the preview to frame the other person.</span>
    </div>
    <div class="kf-list" id="kf-list"></div>
  </div>`);

function renderKeyframes() {
  const active = framePos().idx;
  const html = S.keyframes.map((k, i) => `
    <div class="kf-row${i === active ? ' on' : ''}" data-i="${i}">
      <span class="mono">${fmt(k.t)}</span><span class="hint grow">frame at ${Math.round(k.x * 100)}% · ${Math.round(k.y * 100)}%</span>
      <button class="icon-btn" data-kf="go" title="Go there">${PRO_ICONS.go}</button>
      <button class="icon-btn danger" data-kf="del" title="Remove">${PRO_ICONS.x}</button>
    </div>`).join('');
  const list = $('#kf-list');
  if (list.dataset.html !== html) { list.innerHTML = html; list.dataset.html = html; }
}
setInterval(renderKeyframes, 300);

$('#kf-add').onclick = () => {
  const t = round(video.currentTime, 2);
  if (S.inT == null || t < S.inT || t > S.outT) { toast('Move the playhead inside the clip first.', 'info'); return; }
  if (S.keyframes.some((k) => Math.abs(k.t - t) < 0.1)) { toast('There is already a switch here.', 'info'); return; }
  const pos = framePos();
  S.keyframes.push({ t, x: pos.x, y: pos.y });
  S.keyframes.sort((a, b) => a.t - b.t);
  renderKeyframes();
  toast('Switch added – now drag the preview to frame the other person.', 'ok');
};
$('#kf-list').onclick = (e) => {
  const row = e.target.closest('.kf-row');
  const act = e.target.closest('[data-kf]')?.dataset.kf;
  if (!row || !act) return;
  const i = +row.dataset.i;
  if (act === 'go') seek(S.keyframes[i].t + 0.02);
  else S.keyframes.splice(i, 1);
  renderKeyframes();
};

/* ---------------------------------------------------------------- pop-ups (pictures / GIFs / videos) */

$('#e-watermark').closest('.field').insertAdjacentHTML('beforebegin', `
  <div class="field" id="pop-field">
    <span class="label">Pop-ups <span class="dim">· picture, GIF or video on top</span></span>
    <div class="sub-row">
      <button class="btn ghost small" id="pop-add">${PRO_ICONS.pic}Add at playhead</button>
      <span class="hint grow">Shows for a moment where the playhead is – memes, reactions, B-roll.</span>
    </div>
    <div class="pop-list" id="pop-list"></div>
  </div>`);

const isVideoFile = (path) => /\.(mp4|mov|webm|mkv|m4v)$/i.test(path);

function popupMedia(p) {
  if (!P.media.has(p.path)) {
    const url = `/media/file?path=${encodeURIComponent(p.path)}`;
    let node;
    if (isVideoFile(p.path)) {
      node = document.createElement('video');
      node.muted = true;
      node.playsInline = true;
      node.preload = 'auto';
      node.src = url;
    } else {
      node = new Image();
      node.src = url;
    }
    P.media.set(p.path, node);
  }
  return P.media.get(p.path);
}

function renderPopups() {
  $('#pop-list').innerHTML = P.popups.map((p, i) => `
    <div class="pop-row" data-i="${i}">
      <div class="pop-top">
        <span class="pop-name" title="${escapeHtml(p.path)}">${escapeHtml(p.path.split(/[\\/]/).pop())}</span>
        <span class="mono hint">@ ${fmt(p.at)}</span>
        <button class="icon-btn" data-pop="go" title="Go there">${PRO_ICONS.go}</button>
        <button class="icon-btn danger" data-pop="del" title="Remove">${PRO_ICONS.x}</button>
      </div>
      <div class="pop-controls">
        <label><span class="hint">Seconds</span><input class="input mono" data-pop="dur" type="number" min="0.3" max="10" step="0.1" value="${p.dur}"></label>
        <label><span class="hint">Size</span><input class="range" data-pop="size" type="range" min="20" max="100" value="${Math.round(p.size * 100)}"></label>
        <div class="segmented three" data-pop="pos">${['top', 'center', 'bottom'].map((pos) =>
          `<button data-value="${pos}" class="${p.pos === pos ? 'on' : ''}">${pos}</button>`).join('')}</div>
      </div>
    </div>`).join('');
}

$('#pop-add').onclick = async () => {
  const at = round(video.currentTime, 2);
  if (S.inT == null || at < S.inT || at > S.outT) { toast('Move the playhead inside the clip first.', 'info'); return; }
  try {
    const res = await api.post('/api/pick-popup');
    if (!res.path) return;
    P.popups.push({ id: Math.random().toString(36).slice(2, 10), at, dur: 1.5, path: res.path, pos: 'center', size: 0.8 });
    P.popups.sort((a, b) => a.at - b.at);
    renderPopups();
  } catch (err) { toast(err.message, 'error'); }
};
$('#pop-list').addEventListener('click', (e) => {
  const row = e.target.closest('.pop-row');
  const btn = e.target.closest('button[data-pop], .segmented[data-pop] button');
  if (!row || !btn) return;
  const p = P.popups[+row.dataset.i];
  const act = btn.dataset.pop;
  if (act === 'go') seek(p.at);
  else if (act === 'del') { P.popups.splice(+row.dataset.i, 1); renderPopups(); }
  else if (btn.dataset.value) { p.pos = btn.dataset.value; renderPopups(); }
});
$('#pop-list').addEventListener('input', (e) => {
  const row = e.target.closest('.pop-row');
  if (!row) return;
  const p = P.popups[+row.dataset.i];
  if (e.target.dataset.pop === 'dur') p.dur = clamp(+e.target.value || 1.5, 0.3, 10);
  if (e.target.dataset.pop === 'size') p.size = clamp(+e.target.value / 100, 0.2, 1);
});

/* draws the pop-ups in the preview, like clipper.edit_graph: fade in/out over 0.15 s */
function drawPopups(c, { t, inClip, ed }) {
  const active = new Set();
  if (inClip) {
    for (const p of P.popups) {
      const local = (t - p.at) / ed.speed;  // seconds since this pop-up appeared
      if (local < 0 || local > p.dur) continue;
      const m = popupMedia(p);
      const isVideo = m instanceof HTMLVideoElement;
      if (isVideo) {
        active.add(m);
        if (Math.abs(m.currentTime - local) > 0.3) m.currentTime = local;
        if (!video.paused && m.paused) m.play().catch(() => {});
        if (video.paused && !m.paused) m.pause();
      }
      const iw = isVideo ? m.videoWidth : m.naturalWidth, ih = isVideo ? m.videoHeight : m.naturalHeight;
      if (!iw || (isVideo && m.readyState < 2)) continue;
      const w = CW * p.size, h = w * ih / iw;
      const y = p.pos === 'top' ? 330 * K : p.pos === 'bottom' ? CH - h - 700 * K : (CH - h) / 2;
      c.globalAlpha = clamp(Math.min(local / 0.15, (p.dur - local) / 0.15), 0, 1);
      c.drawImage(m, (CW - w) / 2, y, w, h);
      c.globalAlpha = 1;
    }
  }
  for (const m of P.media.values()) if (m instanceof HTMLVideoElement && !active.has(m) && !m.paused) m.pause();
}

/* ---------------------------------------------------------------- earnings tracker */

const trackerModal = modal('tracker', 'Earnings tracker', `
  <div class="tr-tiles" id="tr-tiles"></div>
  <div class="tr-cols">
    <div class="tr-block"><div class="label">By campaign</div><div id="tr-campaigns"></div></div>
    <div class="tr-block"><div class="label">What works best</div><div id="tr-best"></div></div>
  </div>
  <div class="label tr-label">Posted clips <span class="dim">· type the views as they grow</span></div>
  <div class="tr-table-wrap"><table class="tr-table" id="tr-table"></table></div>`, true);

const postedModal = modal('posted', 'Mark as posted', `
  <div class="hint" id="po-clip"></div>
  <span class="label">Platform</span>
  <div class="segmented four" id="po-platform">${['TikTok', 'Reels', 'Shorts', 'X'].map((p, i) =>
    `<button data-value="${p}" class="${i ? '' : 'on'}">${p}</button>`).join('')}</div>
  <label class="field"><span class="label">Link to the post</span><input class="input" id="po-url" placeholder="https://www.tiktok.com/@you/video/…"></label>
  <label class="field"><span class="label">Views so far</span><input class="input mono" id="po-views" type="number" min="0" value="0"></label>
  <div class="sub-row"><button class="btn primary small" id="po-save">Save to tracker</button></div>`);

P.postClip = null;
$('#po-platform').onclick = (e) => {
  const b = e.target.closest('button');
  if (b) for (const x of $('#po-platform').children) x.classList.toggle('on', x === b);
};
$('#po-save').onclick = async () => {
  const clip = P.postClip;
  const platform = $('#po-platform .on')?.dataset.value || 'TikTok';
  // the finished length (edits, deleted parts, teaser and speed included), else the range's
  const plan = typeof clip.status?.length === 'number' ? clip.status.length : clip.end - clip.start;
  try {
    await api.post('/api/tracker', {
      campaign: P.projectCampaign, project: S.videoKey, clip: clip.name, platform, url: $('#po-url').value.trim(),
      posted: today(), views: +$('#po-views').value || 0, style: clip.caption_style || 'classic', layout: clip.layout,
      length: round(plan, 1), hook: clip.hook || '', teaser: clip.intro_start != null,
    });
    postedModal.hidden = true;
    toast(`${clip.name} added to the earnings tracker.`, 'ok', { label: 'Open', fn: openTracker });
  } catch (err) { toast(err.message, 'error'); }
};

function earned(entry, campaigns) {
  if (entry.earned != null) return entry.earned;
  const camp = campaigns.find((c) => c.id === entry.campaign);
  return camp ? entry.views / 1000 * camp.cpm : 0;
}

async function openTracker() {
  const data = await api.get('/api/tracker');
  P.tracker = data.entries;
  P.campaigns = data.campaigns;
  renderTracker();
  trackerModal.hidden = false;
}
$('#btn-earnings').onclick = openTracker;

function renderTracker() {
  const entries = P.tracker, camps = P.campaigns;
  const totalViews = entries.reduce((s, e) => s + e.views, 0);
  const totalMoney = entries.reduce((s, e) => s + earned(e, camps), 0);
  const top = [...entries].sort((a, b) => b.views - a.views)[0];
  $('#tr-tiles').innerHTML = `
    <div class="tr-tile"><span class="label">Est. earnings</span><span class="tr-big">${money(totalMoney)}</span></div>
    <div class="tr-tile"><span class="label">Total views</span><span class="tr-big">${count(totalViews)}</span></div>
    <div class="tr-tile"><span class="label">Clips posted</span><span class="tr-big">${entries.length}</span></div>
    <div class="tr-tile"><span class="label">Best clip</span><span class="tr-mid">${top ? `${escapeHtml(top.clip)} · ${count(top.views)}` : '—'}</span></div>`;

  const byCamp = {};
  for (const e of entries) {
    const key = e.campaign || '';
    byCamp[key] = byCamp[key] || { views: 0, money: 0, clips: 0 };
    byCamp[key].views += e.views; byCamp[key].money += earned(e, camps); byCamp[key].clips += 1;
  }
  $('#tr-campaigns').innerHTML = Object.entries(byCamp).map(([id, v]) => `
    <div class="tr-line"><span class="grow">${escapeHtml(camps.find((c) => c.id === id)?.name || 'No campaign')}</span>
      <span class="mono hint">${v.clips} clips · ${count(v.views)} views</span><span class="mono tr-money">${money(v.money)}</span></div>`).join('')
    || '<div class="hint">Nothing posted yet.</div>';

  // average views by caption style, layout and teaser – what to make more of
  const groups = [
    ['Caption style', (e) => S.styles?.[e.style]?.label || e.style],
    ['Layout', (e) => e.layout],
    ['Teaser', (e) => (e.teaser ? 'with teaser' : 'no teaser')],
  ];
  $('#tr-best').innerHTML = entries.length ? groups.map(([label, keyOf]) => {
    const g = {};
    for (const e of entries) { const k = keyOf(e) || '—'; g[k] = g[k] || []; g[k].push(e.views); }
    const best = Object.entries(g).map(([k, v]) => [k, v.reduce((a, b) => a + b, 0) / v.length, v.length])
      .sort((a, b) => b[1] - a[1])[0];
    return `<div class="tr-line"><span class="grow">${label}</span><span class="mono">${escapeHtml(best[0])}</span>`
      + `<span class="mono hint">avg ${count(Math.round(best[1]))} views (${best[2]})</span></div>`;
  }).join('') : '<div class="hint">Post a few clips and track their views to see what works.</div>';

  $('#tr-table').innerHTML = `<thead><tr><th>Date</th><th>Clip</th><th>Campaign</th><th>Platform</th><th>Views</th><th>Earned</th><th></th></tr></thead><tbody>`
    + entries.map((e) => `<tr data-id="${e.id}">
      <td class="mono">${escapeHtml(e.posted || '')}</td>
      <td>${e.url ? `<a href="${escapeHtml(e.url)}" target="_blank" rel="noopener">${escapeHtml(e.clip || '')}</a>` : escapeHtml(e.clip || '')}
        <div class="hint">${escapeHtml(e.hook || '')}</div></td>
      <td>${escapeHtml(camps.find((c) => c.id === e.campaign)?.name || '—')}</td>
      <td>${escapeHtml(e.platform || '')}</td>
      <td><input class="input mono tr-views" type="number" min="0" value="${e.views}"></td>
      <td class="mono tr-money">${money(earned(e, camps))}</td>
      <td><button class="icon-btn danger" data-tr="del" title="Remove">${PRO_ICONS.x}</button></td></tr>`).join('')
    + '</tbody>';
}

$('#tr-table').addEventListener('change', async (e) => {
  if (!e.target.classList.contains('tr-views')) return;
  const entry = P.tracker.find((x) => x.id === e.target.closest('tr').dataset.id);
  entry.views = Math.max(0, Math.round(+e.target.value || 0));
  await api.post('/api/tracker', entry);
  renderTracker();
});
$('#tr-table').addEventListener('click', async (e) => {
  if (e.target.closest('[data-tr="del"]')) {
    const id = e.target.closest('tr').dataset.id;
    if (!confirm('Remove this clip from the tracker?')) return;
    await api.post('/api/tracker/delete', { id });
    P.tracker = P.tracker.filter((x) => x.id !== id);
    renderTracker();
  }
});

/* ---------------------------------------------------------------- export pack */

$('#btn-folder').insertAdjacentHTML('beforebegin', `
  <button class="btn ghost small" id="btn-export" title="Copy every rendered clip + captions.txt into one folder">${PRO_ICONS.box}Export pack</button>
  <button class="btn ghost small" id="btn-export-zip" title="Same, as one ZIP file">ZIP</button>`);

async function exportPack(zip) {
  try {
    const res = await api.post('/api/export', { zip });
    toast(`Exported to ${res.path.split(/[\\/]/).slice(-2).join('\\')}`, 'ok');
  } catch (err) { toast(err.message, 'error'); }
}
$('#btn-export').onclick = () => exportPack(false);
$('#btn-export-zip').onclick = () => exportPack(true);

/* ---------------------------------------------------------------- plugging into app.js */

HOOKS.fields.push(() => ({ keyframes: S.keyframes.map((k) => ({ ...k })), popups: P.popups.map((p) => ({ ...p })) }));

HOOKS.apply.push((clip) => {
  S.keyframes = (clip.keyframes || []).map((k) => ({ ...k }));
  P.popups = (clip.popups || []).map((p) => ({ ...p }));
  S.kw = { on: !!clip.kw_highlight, color: clip.kw_color || '#39FF14', emojis: !!clip.emojis };
  renderKw();
  renderKeyframes();
  renderPopups();
});

HOOKS.reset.push(() => {
  S.keyframes = [];
  P.popups = [];
  renderKeyframes();
  renderPopups();
});

HOOKS.overlay.push(drawPopups);

HOOKS.card.push((card, clip) => {
  const checks = clip.checks || [];
  if (checks.length) {
    const errors = checks.filter((c) => c.level === 'error').length;
    const badge = document.createElement('span');
    badge.className = `pill ${errors ? 'rule-bad' : 'rule-warn'}`;
    badge.textContent = `⚠ ${checks.length}`;
    badge.title = checks.map((c) => c.text).join('\n');
    card.querySelector('.card-top').insertBefore(badge, card.querySelector('.card-top .pill'));
  }
  const ready = clip.status?.state === 'ready';
  card.querySelector('.card-actions .spacer').insertAdjacentHTML('beforebegin',
    `<button class="icon-btn" data-pro="posted" title="Mark as posted (earnings tracker)" ${ready ? '' : 'disabled'}>${PRO_ICONS.posted}</button>`);
});

/* card buttons added here are handled before app.js's own card click (which would open the clip) */
el.cards.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-pro]');
  if (!btn) return;
  e.stopPropagation();
  const clip = S.clips.find((c) => c.name === btn.closest('.card').dataset.name);
  if (btn.dataset.pro === 'posted' && clip) {
    P.postClip = clip;
    $('#po-clip').textContent = `${clip.name} · ${clip.hook || clip.post_caption || ''}`;
    $('#po-url').value = '';
    $('#po-views').value = 0;
    postedModal.hidden = false;
  }
}, true);

HOOKS.state.push((state) => {
  const v = state.video;
  if (v.key !== P.videoKey) {  // another video: fresh undo history and campaign
    P.videoKey = v.key;
    resetHistory();
    P.moments = [];
  }
  if ((v.campaign || null) !== P.projectCampaign) {
    P.projectCampaign = v.campaign || null;
    campaignChip();
  }
});

renderKw();
renderPopups();
loadCampaigns();
ensureEmojiPictures();
