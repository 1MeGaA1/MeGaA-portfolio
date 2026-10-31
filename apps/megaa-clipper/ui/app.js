'use strict';

/* MeGaA Clipper interface. Talks to clipper_app.py over a small JSON API on 127.0.0.1. */

const $ = (sel, root = document) => root.querySelector(sel);
const OUT_W = 1080;
const CW = 540, CH = 960, K = CW / OUT_W;  // the preview canvas is half the output size

const el = {
  welcome: $('#welcome'), recent: $('#recent'), recentWrap: $('#recent-wrap'),
  projectName: $('#project-name'), projectInfo: $('#project-info'),
  status: $('#status'), statusText: $('#status-text'), topline: $('#topline'), prepChip: $('#prep-chip'),
  lines: $('#lines'), lineCount: $('#line-count'), transcriptEmpty: $('#transcript-empty'),
  search: $('#search'), searchCount: $('#search-count'), follow: $('#follow'),
  lang: $('#lang'), btnTranscribe: $('#btn-transcribe'), btnRetranscribe: $('#btn-retranscribe'),
  phone: $('#phone'), canvas: $('#canvas'), hudTime: $('#hud-time'), hudMode: $('#hud-mode'), phoneMsg: $('#phone-msg'),
  btnPlay: $('#btn-play'), tcNow: $('#tc-now'), tcDur: $('#tc-dur'), btnLoop: $('#btn-loop'), btnSafe: $('#btn-safe'),
  strip: $('#strip'), overview: $('#overview'),
  editTag: $('#edit-tag'), fName: $('#f-name'), fIn: $('#f-in'), fOut: $('#f-out'),
  fLength: $('#f-length'), fLengthHint: $('#f-length-hint'), fLayout: $('#f-layout'),
  cropField: $('#crop-field'), fCrop: $('#f-crop'), fCropVal: $('#f-crop-val'),
  fHook: $('#f-hook'), fPost: $('#f-post'), fCaptions: $('#f-captions'),
  btnAdd: $('#btn-add'), btnRenderOne: $('#btn-render-one'), tabs: $('#tabs'),
  styleGrid: $('#style-grid'), swatches: $('#swatches'), colorField: $('#color-field'),
  fSize: $('#f-size'), fSizeVal: $('#f-size-val'), fPos: $('#f-pos'), fPosVal: $('#f-pos-val'),
  btnCutMode: $('#btn-cut-mode'), music: $('#music'),
  fZoom: $('#f-zoom'), fZoomVal: $('#f-zoom-val'), hookGrid: $('#hook-grid'), hSize: $('#h-size'),
  hSizeVal: $('#h-size-val'), hPos: $('#h-pos'), hPosVal: $('#h-pos-val'), hDur: $('#h-dur'),
  eFinal: $('#e-final'), eFinalHint: $('#e-final-hint'), ePauses: $('#e-pauses'), ePauseMin: $('#e-pause-min'),
  ePauseVal: $('#e-pause-val'), eCutMode: $('#e-cut-mode'), eCutCount: $('#e-cut-count'), eCutClear: $('#e-cut-clear'),
  eZoom: $('#e-zoom'), eZoomAmt: $('#e-zoom-amt'), eZoomVal: $('#e-zoom-val'), eSpeed: $('#e-speed'),
  eProgress: $('#e-progress'), eProgressColors: $('#e-progress-colors'), eMusicPick: $('#e-music-pick'),
  eMusicName: $('#e-music-name'), eMusicClear: $('#e-music-clear'), eMusicVol: $('#e-music-vol'),
  eMusicVal: $('#e-music-val'), eWatermark: $('#e-watermark'), eWmPos: $('#e-wm-pos'),
  teaserField: $('#teaser-field'), eIntro: $('#e-intro'), eIntroA: $('#e-intro-a'), eIntroB: $('#e-intro-b'),
  eIntroPick: $('#e-intro-pick'), eIntroAuto: $('#e-intro-auto'), eIntroPlay: $('#e-intro-play'),
  eIntroInfo: $('#e-intro-info'), eIntroFlash: $('#e-intro-flash'),
  btnMuteMode: $('#btn-mute-mode'), eMuteMode: $('#e-mute-mode'), eMuteCount: $('#e-mute-count'),
  eMuteClear: $('#e-mute-clear'), eMuteSound: $('#e-mute-sound'), eMuteCaptions: $('#e-mute-captions'),
  eCustomRow: $('#e-custom-row'), eSfxName: $('#e-sfx-name'), eSfxPick: $('#e-sfx-pick'),
  eSfxVol: $('#e-sfx-vol'), eSfxVolVal: $('#e-sfx-vol-val'), eSfxVolRow: $('#e-sfx-vol-row'),
  cards: $('#cards'), queueCount: $('#queue-count'), btnRenderAll: $('#btn-render-all'),
  player: $('#player'), playerVideo: $('#player-video'), playerTitle: $('#player-title'), playerCaption: $('#player-caption'),
  toasts: $('#toasts'),
};
const video = $('#src');
const ctx = el.canvas.getContext('2d');

const S = {
  videoKey: null, mediaKey: undefined, transcriptStamp: undefined, peaksStamp: undefined,
  info: null, duration: 0, busy: false,
  lines: [], words: [], wordStarts: [], wordEnds: [], timelines: new Map(),
  styles: null, defaultStyle: 'classic', cap: { style: 'classic', color: null, size: 100, pos: null },
  cutMode: false, cuts: [], drops: [], splits: [], cutAnchor: null, cutAnchorState: true, editCache: { key: null },
  frameZoom: 1, frameY: 0.5, teaserPick: null, inIntro: false, mutes: [], muteMode: false, keyframes: [],
  keywords: {}, emojiSize: 150, kw: { on: false, color: '#39FF14', emojis: false },
  hooks: null, defaultHook: 'white', hookTop: 230, hook: { style: 'white', size: 100, pos: null, duration: 0 },
  edit: {
    removePauses: false, pauseMin: 0.5, zoom: false, zoomAmount: 1.15, speed: 1, progress: false,
    progressColor: '#00E5FF', music: '', musicVolume: 0.15, watermark: '', watermarkPos: 'tr',
    intro: null, introFlash: true, muteSound: 'silence', muteCaptions: true, muteSfx: '', muteSfxVolume: 0.8,
  },
  muteSounds: null, muteHit: -1,
  peaks: null, peakRate: 20, ovBins: null,
  anchor: null, inT: null, outT: null,
  clips: [], editing: null, cardsSig: '', recentSig: '',
  layout: 'crop', cropX: 0.5, loop: true, safe: false,
  finishedSeq: undefined, savingClips: false,
  hits: [], hitIndex: -1, liveLine: -1, stripView: [0, 1], dragWindow: null,
};

/* ---------------------------------------------------------------- helpers */

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d;

function fmt(t) {
  t = Math.round(Math.max(0, t || 0) * 10) / 10;
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60);
  const s = (t % 60).toFixed(1).padStart(4, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

function parseTime(text) {
  const parts = String(text).trim().split(':');
  if (!parts[0] || parts.length > 3) return null;
  let total = 0;
  for (const part of parts) {
    if (!/^\d+(\.\d+)?$/.test(part.trim())) return null;
    total = total * 60 + parseFloat(part);
  }
  return total;
}

function escapeHtml(text) {
  return text.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

function safeName(text) {
  return text.trim().replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 60);
}

/* index of the last item whose key(item) <= t, or -1 */
function lastAtOrBefore(items, t, key) {
  let lo = 0, hi = items.length - 1, found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (key(items[mid]) <= t) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  return found;
}

const api = {
  async get(path) {
    const res = await fetch(path, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  },
  async post(path, body = {}) {
    const res = await fetch(path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  },
};

function toast(message, kind = 'info', action = null) {
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  const text = document.createElement('span');
  text.textContent = message;
  node.append(text);
  const dismiss = () => { node.classList.add('out'); setTimeout(() => node.remove(), 300); };
  if (action) {
    const btn = document.createElement('button');
    btn.className = 'btn ghost small';
    btn.textContent = action.label;
    btn.onclick = () => { action.fn(); dismiss(); };
    node.append(btn);
  }
  el.toasts.append(node);
  setTimeout(dismiss, kind === 'error' ? 9000 : 5000);
}

function setStatus(text, kind = '') {
  el.status.className = `status ${kind}`;
  el.statusText.textContent = text;
  el.status.title = text;
}

/* ---------------------------------------------------------------- server state */

async function refresh() {
  const state = await api.get('/api/state');
  applyState(state);
  return state;
}

async function poll() {
  let delay = 1500;
  try {
    const state = await refresh();
    if (state.job.running || state.prep.state === 'working') delay = 400;
  } catch {
    setStatus('Connection lost', 'error');
    delay = 2500;
  }
  setTimeout(poll, delay);
}

function applyState(state) {
  const v = state.video;
  el.welcome.classList.toggle('hide', !!v);
  if (!v) {
    renderRecent(state.recent);
    applyJob(state.job, state.prep);
    return;
  }
  if (!S.savingClips) S.clips = state.clips;
  if (v.key !== S.videoKey) loadProject(v);
  if (v.media !== S.mediaKey) loadMedia(v.media);
  if (v.transcript !== S.transcriptStamp) loadTranscript(v.transcript);
  if (v.peaks !== S.peaksStamp) loadPeaks(v.peaks);
  applyJob(state.job, state.prep);
  renderCards();
  for (const fn of HOOKS.state) fn(state);
}

function loadProject(v) {
  S.videoKey = v.key;
  S.info = v.info;
  S.duration = v.info.duration;
  S.mediaKey = undefined; S.transcriptStamp = undefined; S.peaksStamp = undefined;
  S.lines = []; S.words = []; S.wordStarts = []; S.wordEnds = []; S.timelines.clear();
  S.peaks = null; S.ovBins = null;
  S.liveLine = -1;
  el.projectName.textContent = v.name;
  el.projectInfo.textContent = `${fmt(v.info.duration)}  ·  ${v.info.width}×${v.info.height}  ·  `
    + `${Math.round(v.info.fps)} fps  ·  ${(v.info.codec || '').toUpperCase()}`;
  el.tcDur.textContent = fmt(v.info.duration);
  document.title = `${v.name} · MeGaA Clipper`;
  newClip(true);
  renderLines();
}

function loadMedia(key) {
  S.mediaKey = key;
  if (!key) {
    video.removeAttribute('src');
    video.load();
    return;
  }
  const resumeAt = video.currentTime || 0;
  video.src = `/media/source?k=${encodeURIComponent(key)}`;
  video.addEventListener('loadedmetadata', () => { if (resumeAt) video.currentTime = resumeAt; }, { once: true });
}

async function loadTranscript(stamp) {
  S.transcriptStamp = stamp;
  if (!stamp) {
    S.lines = []; S.words = [];
    S.timelines.clear();
    renderLines();
    return;
  }
  try {
    const data = await api.get('/api/transcript');
    S.lines = data.lines;
    S.words = data.words;
    S.timelines.clear();
    S.wordStarts = S.words.map((w) => w.s);
    S.wordEnds = S.words.map((w) => w.e).sort((a, b) => a - b);
    renderLines();
  } catch (err) {
    S.transcriptStamp = undefined;
    toast(`Couldn't load the transcript: ${err.message}`, 'error');
  }
}

async function loadPeaks(stamp) {
  S.peaksStamp = stamp;
  if (!stamp) { S.peaks = null; S.ovBins = null; return; }
  try {
    const data = await api.get('/api/peaks');
    S.peaks = Uint8Array.from(data.peaks);
    S.peakRate = data.rate;
    S.ovBins = null;
  } catch {
    S.peaksStamp = undefined;
  }
}

function applyJob(job, prep) {
  S.busy = job.running;
  if (S.finishedSeq === undefined) S.finishedSeq = job.running ? job.seq - 1 : job.seq;
  if (!job.running && job.seq !== S.finishedSeq) {
    S.finishedSeq = job.seq;
    if (job.error) toast(job.error, 'error');
    else if (job.kind === 'render') toast(job.message, 'ok', { label: 'Open folder', fn: openFolder });
    else if (job.kind === 'transcribe') toast('Transcript ready. Click a line to start a clip.', 'ok');
  }

  if (job.running) {
    setStatus(`${job.message} · ${job.progress}%`, 'busy');
    el.topline.style.width = `${Math.max(3, job.progress)}%`;
    el.topline.style.opacity = 1;
  } else {
    el.topline.style.width = '100%';
    el.topline.style.opacity = 0;
    if (job.error) setStatus('Task failed', 'error');
    else if (job.seq > 0) setStatus(job.message, 'done');
    else setStatus('Ready');
  }

  const transcribing = job.running && job.kind === 'transcribe';
  el.btnTranscribe.textContent = transcribing ? `Transcribing ${job.progress}%` : 'Transcribe';
  el.btnTranscribe.disabled = job.running;
  el.btnRetranscribe.disabled = job.running;
  el.btnRenderOne.disabled = job.running;
  el.btnRenderAll.disabled = job.running || !S.clips.length;

  if (prep.state === 'working') {
    el.prepChip.hidden = false;
    el.prepChip.textContent = `${prep.message}${prep.progress ? ` · ${prep.progress}%` : ''}`;
  } else if (prep.state === 'error') {
    el.prepChip.hidden = false;
    el.prepChip.textContent = 'Preview unavailable';
    el.prepChip.title = prep.message;
  } else {
    el.prepChip.hidden = true;
  }

  let msg = '';
  if (S.videoKey && !S.mediaKey) {
    msg = prep.state === 'working' ? `PREPARING PREVIEW${prep.progress ? ` · ${prep.progress}%` : ''}` : 'PREVIEW UNAVAILABLE';
  }
  el.phoneMsg.textContent = msg;
  el.phoneMsg.classList.toggle('show', !!msg);
}

/* ---------------------------------------------------------------- welcome */

function renderRecent(items) {
  const sig = JSON.stringify(items);
  if (sig === S.recentSig) return;
  S.recentSig = sig;
  el.recentWrap.hidden = !items.length;
  el.recent.replaceChildren(...items.map((item) => {
    const node = document.createElement('div');
    node.className = 'recent-item';
    node.innerHTML = `<div class="recent-icon"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/></svg></div>
      <div style="min-width:0"><div class="recent-name"></div><div class="recent-sub"></div></div>`;
    node.querySelector('.recent-name').textContent = item.name;
    node.querySelector('.recent-sub').textContent =
      `${item.clips} clip${item.clips === 1 ? '' : 's'}  ·  ${item.transcript ? 'transcribed' : 'no transcript'}`;
    node.title = item.path;
    node.onclick = () => openVideo(item.path);
    return node;
  }));
}

async function openVideo(path) {
  try {
    const res = await api.post('/api/open', path ? { path } : {});
    if (res.opened) await refresh();
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ---------------------------------------------------------------- transcript */

const PENCIL = '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4"/></svg>';

/* each line is shown word by word, so words can be cut (✂) one at a time */
function renderLines() {
  const frag = document.createDocumentFragment();
  let wi = 0;
  S.lines.forEach((line, i) => {
    const node = document.createElement('div');
    node.className = 'line';
    node.dataset.i = i;
    const spans = [];
    const next = S.lines[i + 1];
    while (wi < S.words.length && S.words[wi].s < line.s - 0.005) wi++;
    while (wi < S.words.length && (next ? S.words[wi].s < next.s - 0.005 : true)) {
      spans.push(`<span class="w" data-wi="${wi}">${escapeHtml(S.words[wi].w)}</span>`);
      wi++;
    }
    node.innerHTML = `<span class="t">${fmt(line.s)}</span><span class="x">${spans.join(' ') || escapeHtml(line.text)}</span>`
      + `<button class="line-edit" title="Fix the caption text">${PENCIL}</button>`;
    frag.append(node);
  });
  el.lines.replaceChildren(frag);
  el.lineCount.textContent = S.lines.length ? `${S.lines.length} lines` : '';
  el.transcriptEmpty.hidden = S.lines.length > 0 || !S.videoKey;
  el.btnRetranscribe.hidden = !S.lines.length;
  el.btnCutMode.hidden = !S.lines.length;
  S.liveLine = -1;
  applySearch();
  paintRange();
  paintCuts();
  paintTeaser();
  markQueuedLines();
}

function lineNodes() { return el.lines.children; }

function paintRange() {
  const nodes = lineNodes();
  const has = S.inT != null && S.outT != null;
  let first = -1, last = -1;
  for (let i = 0; i < nodes.length; i++) {
    const line = S.lines[i];
    const on = has && Math.min(line.e, S.outT) - Math.max(line.s, S.inT) > 0.3;
    nodes[i].classList.toggle('sel', on);
    if (on) { if (first < 0) first = i; last = i; }
    nodes[i].classList.remove('first', 'last');
  }
  if (first >= 0) { nodes[first].classList.add('first'); nodes[last].classList.add('last'); }
}

function markQueuedLines() {
  const nodes = lineNodes();
  for (let i = 0; i < nodes.length; i++) {
    const line = S.lines[i];
    nodes[i].classList.toggle('in-queue', S.clips.some((c) => line.e > c.start && line.s < c.end));
  }
}

function pickLines(first, last) {
  setRange(S.lines[first].s - 0.15, S.lines[last].e + 0.3);
}

el.lines.addEventListener('click', (e) => {
  const node = e.target.closest('.line');
  if (!node || node.classList.contains('editing')) return;
  if (e.target.closest('.line-edit')) { startLineEdit(node); return; }
  if (S.teaserPick) {
    const word = e.target.closest('.w');
    if (word) clickTeaserWord(+word.dataset.wi);
    return;
  }
  if (S.cutMode || S.muteMode) {
    const word = e.target.closest('.w');
    if (word) clickToolWord(S.cutMode ? 'cuts' : 'mutes', +word.dataset.wi, e.shiftKey);
    return;
  }
  const i = +node.dataset.i;
  if (e.shiftKey && S.anchor != null) {
    pickLines(Math.min(S.anchor, i), Math.max(S.anchor, i));
  } else {
    S.anchor = i;
    pickLines(i, i);
    seek(S.lines[i].s);
  }
});

el.lines.addEventListener('dblclick', (e) => {
  const node = e.target.closest('.line');
  if (!node || S.cutMode || S.muteMode || S.teaserPick || node.classList.contains('editing')) return;
  seek(S.lines[+node.dataset.i].s);
  video.play().catch(() => {});
});

function applySearch() {
  const query = el.search.value.trim().toLowerCase();
  const tokens = query.split(/\s+/).filter(Boolean);
  const bare = (text) => text.toLowerCase().replace(/[^\p{L}\p{N}']/gu, '');
  const nodes = lineNodes();
  S.hits = [];
  S.hitIndex = -1;
  for (let i = 0; i < nodes.length; i++) {
    nodes[i].classList.remove('hit-current');
    const hit = query && S.lines[i].text.toLowerCase().includes(query);
    if (hit) S.hits.push(i);
    for (const span of nodes[i].querySelectorAll('.w')) {
      const word = bare(span.textContent);
      span.classList.toggle('mark', !!hit && tokens.some((t) => word && (word.includes(bare(t)) && bare(t))));
    }
  }
  el.searchCount.textContent = query ? `${S.hits.length}` : '';
}

/* ---------------------------------------------------------------- fixing caption text */

function startLineEdit(node) {
  const i = +node.dataset.i;
  const line = S.lines[i];
  const box = node.querySelector('.x');
  const original = box.innerHTML;
  node.classList.add('editing');
  box.contentEditable = 'plaintext-only';
  box.textContent = [...box.querySelectorAll('.w')].map((w) => w.textContent).join(' ') || box.textContent;
  box.focus();
  document.getSelection().selectAllChildren(box);

  const finish = async (save) => {
    box.removeEventListener('keydown', onKey);
    box.removeEventListener('blur', onBlur);
    box.contentEditable = 'false';
    node.classList.remove('editing');
    const text = box.textContent.replace(/\s+/g, ' ').trim();
    if (!save || text === box.dataset.before) { box.innerHTML = original; return; }
    try {
      await api.post('/api/edit-line', { s: line.s, e: line.e, text });
      toast(text ? 'Caption text fixed' : 'Words removed from the captions', 'ok');
      await refresh();
    } catch (err) {
      box.innerHTML = original;
      toast(err.message, 'error');
    }
  };
  const onKey = (ev) => {
    ev.stopPropagation();  // keep Enter / Space / I / O from reaching the editor shortcuts
    if (ev.key === 'Enter') { ev.preventDefault(); finish(true); }
    if (ev.key === 'Escape') { ev.preventDefault(); finish(false); }
  };
  const onBlur = () => finish(false);
  box.dataset.before = box.textContent;
  box.addEventListener('keydown', onKey);
  box.addEventListener('blur', onBlur);
}

/* ---------------------------------------------------------------- word tools: cut (remove) and mute (silence) */

const wordMid = (w) => (w.s + w.e) / 2;
/* is word i inside one of the ranges in S[list] ('cuts' or 'mutes')? */
const inList = (list, i) => i >= 0 && i < S.words.length
  && S[list].some(([a, b]) => wordMid(S.words[i]) > a && wordMid(S.words[i]) < b);
const isCut = (i) => inList('cuts', i);
const isMuted = (i) => inList('mutes', i);
const TOOL_ANCHOR = { cuts: null, mutes: null };
const TOOL_STATE = { cuts: true, mutes: true };

function normaliseCuts(ranges) {
  const sorted = ranges.filter(([a, b]) => b - a > 0.01).sort((x, y) => x[0] - y[0]);
  const out = [];
  for (const [a, b] of sorted) {
    const last = out[out.length - 1];
    if (last && a <= last[1] + 0.001) last[1] = Math.max(last[1], b);
    else out.push([a, b]);
  }
  return out.map(([a, b]) => [round(a, 3), round(b, 3)]);
}

/* add / take word i to / from the ranges in S[list] */
function setWordIn(list, i, on) {
  const w = S.words[i];
  if (on) {
    // join up with marked neighbours so the gap between them is covered too
    const a = inList(list, i - 1) ? S.words[i - 1].e : w.s - 0.02;
    const b = inList(list, i + 1) ? S.words[i + 1].s : w.e + 0.02;
    S[list] = normaliseCuts([...S[list], [a, b]]);
  } else {
    const a = inList(list, i - 1) ? S.words[i - 1].e + 0.02 : w.s - 0.05;
    const b = inList(list, i + 1) ? S.words[i + 1].s - 0.02 : w.e + 0.05;
    const pieces = [];
    for (const [s, e] of S[list]) {
      if (e <= a || s >= b) { pieces.push([s, e]); continue; }
      if (s < a) pieces.push([s, a]);
      if (e > b) pieces.push([b, e]);
    }
    S[list] = normaliseCuts(pieces);
  }
}

/* click = toggle one word; shift+click = give the whole run from the last click the same state */
function clickToolWord(list, i, shift) {
  const w = S.words[i];
  const verb = list === 'cuts' ? 'cut' : 'mute';
  if (S.inT == null || S.outT == null) { toast(`Pick the clip range first, then ${verb} words inside it.`, 'info'); return; }
  const inTeaser = list === 'mutes' && S.edit.intro && wordMid(w) >= S.edit.intro[0] && wordMid(w) <= S.edit.intro[1];
  if ((w.e <= S.inT || w.s >= S.outT) && !inTeaser) { toast('That word is outside the clip.', 'info'); return; }
  const anchor = TOOL_ANCHOR[list];
  if (shift && anchor != null) {
    const on = TOOL_STATE[list];
    for (let k = Math.min(anchor, i); k <= Math.max(anchor, i); k++) {
      if (inList(list, k) !== on) setWordIn(list, k, on);
    }
  } else {
    const on = !inList(list, i);
    setWordIn(list, i, on);
    TOOL_ANCHOR[list] = i;
    TOOL_STATE[list] = on;
  }
  editChanged();
}

function paintCuts() {
  const inClip = (list) => (S.inT == null ? 0 : S.words.filter((w, i) => w.e > S.inT && w.s < S.outT && inList(list, i)).length);
  for (const span of el.lines.querySelectorAll('.w')) {
    span.classList.toggle('cut', isCut(+span.dataset.wi));
    span.classList.toggle('muted', isMuted(+span.dataset.wi));
  }
  const cut = inClip('cuts'), mute = inClip('mutes');
  el.eCutCount.textContent = cut ? `${cut} word${cut === 1 ? '' : 's'} cut` : 'No words cut';
  el.eMuteCount.textContent = mute ? `${mute} word${mute === 1 ? '' : 's'} muted` : 'No words muted';
}

/* only one word tool at a time: cut, mute, or picking the teaser */
function setCutMode(on) {
  if (on) { if (S.teaserPick) setTeaserPick(null); if (S.muteMode) setMuteMode(false); }
  S.cutMode = on;
  document.body.classList.toggle('cut-mode', on);
  el.btnCutMode.classList.toggle('on', on);
  el.eCutMode.classList.toggle('on', on);
  if (on) toast('Cut tool on: click words to remove them. Press X to turn it off.', 'info');
}

function setMuteMode(on) {
  if (on) { if (S.teaserPick) setTeaserPick(null); if (S.cutMode) setCutMode(false); }
  S.muteMode = on;
  document.body.classList.toggle('mute-mode', on);
  el.btnMuteMode.classList.toggle('on', on);
  el.eMuteMode.classList.toggle('on', on);
  if (on) toast('Mute tool on: click words to silence them. Press M to turn it off.', 'info');
}
el.btnCutMode.onclick = () => setCutMode(!S.cutMode);
el.btnMuteMode.onclick = () => setMuteMode(!S.muteMode);

function nextHit(step = 1) {
  if (!S.hits.length) return;
  const nodes = lineNodes();
  if (S.hitIndex >= 0) nodes[S.hits[S.hitIndex]]?.classList.remove('hit-current');
  S.hitIndex = (S.hitIndex + step + S.hits.length) % S.hits.length;
  const i = S.hits[S.hitIndex];
  nodes[i].classList.add('hit-current');
  nodes[i].scrollIntoView({ block: 'center', behavior: 'smooth' });
  S.anchor = i;
  pickLines(i, i);
  seek(S.lines[i].s);
  el.searchCount.textContent = `${S.hitIndex + 1}/${S.hits.length}`;
}

el.search.addEventListener('input', applySearch);
el.search.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); nextHit(e.shiftKey ? -1 : 1); }
});

el.btnTranscribe.onclick = () => transcribe();
el.btnRetranscribe.onclick = () => {
  if (confirm('Transcribe this video again? The current transcript will be replaced.')) transcribe();
};

async function transcribe() {
  try {
    await api.post('/api/transcribe', { lang: el.lang.value });
    await refresh();
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ---------------------------------------------------------------- clip range + inspector */

function setRange(a, b, { fromInputs = false } = {}) {
  const dur = S.duration || Infinity;
  S.inT = a == null ? null : round(clamp(a, 0, dur), 2);
  S.outT = b == null ? null : round(clamp(b, 0, dur), 2);
  if (!fromInputs) {
    el.fIn.value = S.inT == null ? '' : fmt(S.inT);
    el.fOut.value = S.outT == null ? '' : fmt(S.outT);
    el.fIn.classList.remove('bad');
    el.fOut.classList.remove('bad');
  }
  updateLength();
  paintRange();
  paintCuts();
}

function updateLength() {
  const node = el.fLength;
  node.className = 'length mono';
  el.eFinal.className = 'length mono';
  if (S.inT == null || S.outT == null) {
    node.textContent = el.eFinal.textContent = '—';
    el.fLengthHint.textContent = 'Click a transcript line or press I / O';
    el.eFinalHint.textContent = 'Pick a clip range first';
    return;
  }
  const raw = S.outT - S.inT;
  if (raw <= 0) {
    node.textContent = el.eFinal.textContent = 'END ≤ START';
    node.classList.add('bad');
    el.fLengthHint.textContent = el.eFinalHint.textContent = 'The end must be after the start';
    return;
  }
  const { duration } = editState();
  const edited = Math.abs(duration - raw) > 0.05;
  const len = edited ? duration : raw;
  node.textContent = el.eFinal.textContent = `${len.toFixed(1)}s`;
  if (len < 10 || len > 90) { node.classList.add('warn'); el.eFinal.classList.add('warn'); }
  const advice = len < 10 ? 'Short – most campaigns want 15 s+' : len > 90 ? 'Long – 20–60 s performs best' : 'Best length: 20–60 s';
  el.fLengthHint.textContent = edited ? `after edits (raw ${raw.toFixed(1)}s)` : advice;
  el.eFinalHint.textContent = edited ? `from ${raw.toFixed(1)}s raw · ${advice}` : `No edits yet · ${advice}`;
}

for (const [input, which] of [[el.fIn, 'in'], [el.fOut, 'out']]) {
  input.addEventListener('change', () => {
    const t = parseTime(input.value);
    input.classList.toggle('bad', t == null);
    if (t == null) return;
    if (which === 'in') setRange(t, S.outT, { fromInputs: true });
    else setRange(S.inT, t, { fromInputs: true });
    input.value = fmt(t);
    seek(t);
  });
}

function setIn() {
  const t = video.currentTime;
  const out = S.outT != null && S.outT > t + 0.2 ? S.outT : Math.min(t + 30, S.duration);
  setRange(t, out);
}

function setOut() {
  const t = video.currentTime;
  const start = S.inT != null && S.inT < t - 0.2 ? S.inT : Math.max(0, t - 30);
  setRange(start, t);
}

$('#btn-set-in').onclick = setIn;
$('#btn-set-out').onclick = setOut;

/* zoom limits per layout – same as clipper.FIT_ZOOM / CROP_ZOOM */
const ZOOM_LIMITS = { fit: [0.5, 2.5], crop: [1, 2.5] };

function setLayout(layout) {
  S.layout = layout;
  for (const btn of el.fLayout.children) btn.classList.toggle('on', btn.dataset.value === layout);
  el.phone.classList.toggle('fit', layout === 'fit');
  el.fZoom.min = ZOOM_LIMITS[layout][0] * 100;
  setFrameZoom(S.frameZoom);
}
el.fLayout.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (btn) setLayout(btn.dataset.value);
});

function setCrop(value) {
  S.cropX = clamp(value, 0, 1);
  el.fCrop.value = Math.round(S.cropX * 1000);
  el.fCrop.style.setProperty('--p', `${S.cropX * 100}%`);
  el.fCropVal.textContent = `${Math.round(S.cropX * 100)}%`;
}
el.fCrop.addEventListener('input', () => setCrop(el.fCrop.value / 1000));

function setFrameZoom(value) {
  const [low, high] = ZOOM_LIMITS[S.layout];
  S.frameZoom = round(clamp(value, low, high), 3);
  el.fZoom.value = Math.round(S.frameZoom * 100);
  el.fZoom.style.setProperty('--p', `${(S.frameZoom * 100 - low * 100) / (high * 100 - low * 100) * 100}%`);
  el.fZoomVal.textContent = `${Math.round(S.frameZoom * 100)}%`;
}
el.fZoom.addEventListener('input', () => setFrameZoom(el.fZoom.value / 100));
$('#btn-frame-reset').onclick = () => { setFrameZoom(1); setCrop(0.5); S.frameY = 0.5; };

/* ---------------------------------------------------------------- hook looks */

function effectiveHook() {
  const base = S.hooks?.[S.hook.style] || S.hooks?.[S.defaultHook];
  if (!base) return null;
  return {
    ...base, size: Math.round(base.size * clamp(S.hook.size, 50, 200) / 100),
    margin_v: S.hook.pos ?? S.hookTop, duration: S.hook.duration,
  };
}

function hookSampleCss(hs) {
  const outline = hs.mode === 'outline'
    ? [[1, 1], [-1, -1], [1, -1], [-1, 1]].map(([x, y]) => `${x}px ${y}px 0 ${hs.outline_color}`).join(',')
      + (hs.glow ? `,0 0 6px ${hs.outline_color},0 0 10px ${hs.outline_color}` : '')
    : 'none';
  const bg = hs.mode === 'box' ? `background:${hs.box};` : '';
  return `${bg}color:${hs.text};font-family:'${hs.font}';text-shadow:${outline};`
    + `font-size:${clamp(10.5 * hs.size / 60, 9, 13)}px`;
}

function renderHookGrid() {
  el.hookGrid.innerHTML = Object.entries(S.hooks).map(([key, hs]) =>
    `<button class="hook-tile" data-hook="${key}" title="${escapeHtml(hs.label)}">`
    + `<span class="hook-sample"><span style="${hookSampleCss(hs)}">${hs.uppercase ? 'HOOK' : 'Hook'}</span></span>`
    + `<span class="hook-name">${escapeHtml(hs.label)}</span></button>`).join('');
}

function setHookStyle(changes) {
  Object.assign(S.hook, changes);
  if (!S.hooks) return;
  if (!S.hooks[S.hook.style]) S.hook.style = S.defaultHook;
  for (const tile of el.hookGrid.children) tile.classList.toggle('on', tile.dataset.hook === S.hook.style);
  const hs = effectiveHook();
  el.hSize.value = S.hook.size;
  el.hSize.style.setProperty('--p', `${(S.hook.size - 60) / 120 * 100}%`);
  el.hSizeVal.textContent = `${S.hook.size}%`;
  el.hPos.value = hs.margin_v;
  el.hPos.style.setProperty('--p', `${(hs.margin_v - 40) / 1460 * 100}%`);
  el.hPosVal.textContent = `${Math.round(hs.margin_v / 1920 * 100)}%`;
  for (const b of el.hDur.children) b.classList.toggle('on', +b.dataset.value === S.hook.duration);
}

el.hookGrid.addEventListener('click', (e) => {
  const tile = e.target.closest('.hook-tile');
  if (tile) setHookStyle({ style: tile.dataset.hook });
});
el.hSize.addEventListener('input', () => setHookStyle({ size: +el.hSize.value }));
el.hPos.addEventListener('input', () => setHookStyle({ pos: +el.hPos.value }));
el.hDur.addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (b) setHookStyle({ duration: +b.dataset.value });
});

function hookFields() {
  return { hook_style: S.hook.style, hook_size: S.hook.size, hook_pos: S.hook.pos, hook_duration: S.hook.duration };
}

$('#btn-hook-all').onclick = async () => {
  if (!S.clips.length) { toast('The queue is empty.', 'info'); return; }
  try {
    await saveClips(S.clips.map((c) => ({ ...stripStatus(c), ...hookFields() })));
    toast(`Hook look applied to ${S.clips.length} clip${S.clips.length === 1 ? '' : 's'}.`, 'ok');
  } catch (err) {
    toast(err.message, 'error');
  }
};

function nextName() {
  const taken = new Set(S.clips.map((c) => c.name));
  let n = 1;
  while (taken.has(`clip_${String(n).padStart(2, '0')}`)) n++;
  return `clip_${String(n).padStart(2, '0')}`;
}

function setEditing(name) {
  S.editing = name;
  el.editTag.textContent = name ? `EDITING · ${name}` : 'NEW';
  el.btnAdd.textContent = name ? 'Save changes' : 'Add to queue';
  S.cardsSig = '';
  renderCards();
}

function newClip(clearRange) {
  setEditing(null);
  el.fName.value = nextName();
  el.fHook.value = '';
  el.fPost.value = '';
  S.cuts = [];
  S.mutes = [];
  S.drops = [];   // razor parts and lines – made in the QML edition, kept here
  S.splits = [];
  S.edit.intro = null;
  TOOL_ANCHOR.cuts = TOOL_ANCHOR.mutes = null;
  if (clearRange) setRange(null, null);
  for (const fn of HOOKS.reset) fn();
  editChanged();
}
$('#btn-new').onclick = () => newClip(true);

/* extension points for ui/pro.js (keyframes, pop-ups, keywords, campaigns, undo, ...) */
const HOOKS = { fields: [], apply: [], reset: [], overlay: [], card: [], state: [] };

/* everything the editor holds for the clip, without checks (used for saving and for undo) */
function clipFields() {
  const fields = {
    name: safeName(el.fName.value), start: S.inT, end: S.outT, layout: S.layout, crop_x: round(S.cropX, 3),
    hook: el.fHook.value.trim(), post_caption: el.fPost.value.trim(), ...captionFields(), ...editFields(),
    ...hookFields(), frame_zoom: S.frameZoom, frame_y: round(S.frameY, 3),
  };
  for (const fn of HOOKS.fields) Object.assign(fields, fn());
  return fields;
}

function currentClip() {
  const name = safeName(el.fName.value);
  if (!name) throw new Error('Give the clip a name');
  if (S.inT == null || S.outT == null) throw new Error('Pick a start and an end first');
  if (S.outT <= S.inT) throw new Error('The end must be after the start');
  const { segs } = editState();
  if (!segs || !segs.length) throw new Error('Everything in this clip has been cut out');
  return clipFields();
}

function captionFields() {
  return {
    captions: el.fCaptions.checked, caption_style: S.cap.style, caption_color: S.cap.color,
    caption_size: S.cap.size, caption_pos: S.cap.pos,
    kw_highlight: S.kw.on, kw_color: S.kw.color, emojis: S.kw.emojis,
  };
}

const stripStatus = ({ status, ...clip }) => clip;

async function saveClips(list) {
  S.savingClips = true;
  try {
    const res = await api.post('/api/clips', { clips: list.map(stripStatus) });
    S.clips = res.clips;
    S.cardsSig = '';
    renderCards();
  } finally {
    S.savingClips = false;
  }
}

async function addClip(andRender = false) {
  let clip;
  try {
    clip = currentClip();
  } catch (err) {
    toast(err.message, 'error');
    return;
  }
  const list = S.clips.map(stripStatus);
  const key = S.editing ?? clip.name;
  const dupe = list.findIndex((c) => c.name === clip.name && c.name !== key);
  if (dupe !== -1) list.splice(dupe, 1);
  const idx = list.findIndex((c) => c.name === key);
  if (idx === -1) list.push(clip); else list[idx] = clip;
  try {
    await saveClips(list);
  } catch (err) {
    toast(err.message, 'error');
    return;
  }
  markQueuedLines();
  if (andRender) {
    setEditing(clip.name);
    el.fName.value = clip.name;
    renderClips([clip.name]);
  } else if (S.editing) {
    setEditing(clip.name);
    toast(`Saved ${clip.name}`, 'ok');
  } else {
    toast(`Added ${clip.name} to the queue`, 'ok');
    newClip(true);
  }
}

el.btnAdd.onclick = () => addClip(false);
el.btnRenderOne.onclick = () => addClip(true);

async function renderClips(names) {
  try {
    await api.post('/api/render', { names });
    await refresh();
  } catch (err) {
    toast(err.message, 'error');
  }
}

el.btnRenderAll.onclick = () => renderClips(S.clips.map((c) => c.name));

function openFolder() {
  api.post('/api/open-output').catch((err) => toast(err.message, 'error'));
}
$('#btn-folder').onclick = openFolder;

/* ---------------------------------------------------------------- caption styles */

const SWATCHES = ['#FFFF00', '#FFD400', '#39FF14', '#00E5FF', '#FF2BD6', '#8B5CFF', '#FF3B30', '#FF9500', '#FFFFFF'];

el.tabs.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  for (const b of el.tabs.children) b.classList.toggle('on', b === btn);
  for (const pane of document.querySelectorAll('.inspector-body')) pane.hidden = pane.dataset.pane !== btn.dataset.tab;
});

async function loadStyles() {
  try {
    const data = await api.get('/api/styles');
    S.styles = data.styles;
    S.defaultStyle = data.default;
    S.cardsSig = '';
    renderCards();
    renderStyleGrid();
    setCaptionStyle({ style: S.defaultStyle });
    S.hooks = data.hooks;
    S.defaultHook = data.default_hook;
    S.hookTop = data.hook_top;
    S.keywords = data.keywords || {};
    S.emojiSize = data.emoji_size || 150;
    S.muteSounds = data.mute_sounds || {  // an older server (app not restarted yet) only knows these two
      silence: { label: 'Silence', kind: 'none' }, bleep: { label: 'Bleep', kind: 'tone', freq: 1000 },
    };
    renderSoundGrid();
    renderHookGrid();
    setHookStyle({ style: S.defaultHook });
  } catch {
    setTimeout(loadStyles, 1500);
  }
}

/* a small CSS look-alike of each style for its tile */
function tileSample(st) {
  const words = st.max_words === 1 ? ['money'] : ['your', 'money', 'rule'];
  const active = st.max_words === 1 ? 0 : 1;
  const outline = st.outline
    ? [[1, 1], [-1, -1], [1, -1], [-1, 1], [0, 1.5], [0, -1.5], [1.5, 0], [-1.5, 0]]
      .map(([x, y]) => `${x}px ${y}px 0 ${st.outline_color}`).join(',')
    : 'none';
  const glow = st.glow ? `,0 0 6px ${st.outline_color},0 0 12px ${st.outline_color}` : '';
  const shadow = st.shadow ? `,2px 3px 0 rgba(0,0,0,.45)` : '';
  const size = clamp(14 * st.size / 84, 10, 19);
  const html = words.map((w, i) => {
    const text = escapeHtml(st.uppercase ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1));
    const lit = (st.mode === 'word' && i === active) || (st.mode === 'fill' && i <= active);
    if (st.mode === 'box' && i === active) {
      return `<span class="hl-box" style="background:${st.accent};text-shadow:none">${text}</span>`;
    }
    const grow = st.mode === 'word' && i === active && st.active_scale !== 1 ? `font-size:${st.active_scale}em;` : '';
    return `<span style="${grow}color:${lit ? st.accent : st.text}">${text}</span>`;
  }).join('');
  return `<div class="tile-sample" style="font-family:'${st.font}';font-weight:${st.bold ? 700 : 400};`
    + `font-size:${size}px;text-shadow:${outline}${glow}${shadow}">${html}</div>`;
}

function renderStyleGrid() {
  el.styleGrid.innerHTML = Object.entries(S.styles).map(([key, st]) =>
    `<button class="style-tile" data-style="${key}">${tileSample(st)}<span class="tile-name">${escapeHtml(st.label)}</span></button>`,
  ).join('');
}

el.styleGrid.addEventListener('click', (e) => {
  const tile = e.target.closest('.style-tile');
  if (tile) setCaptionStyle({ style: tile.dataset.style, color: null });
});

function renderSwatches() {
  const st = effectiveStyle();
  const custom = S.cap.color && !SWATCHES.includes(S.cap.color);
  el.swatches.innerHTML =
    `<button class="swatch auto${S.cap.color ? '' : ' on'}" data-color="" title="Style default"></button>`
    + SWATCHES.map((c) => `<button class="swatch${S.cap.color === c ? ' on' : ''}" data-color="${c}" style="background:${c}"></button>`).join('')
    + `<label class="swatch custom${custom ? ' on' : ''}" title="Pick any colour"${custom ? ` style="background:${S.cap.color}"` : ''}>`
    + `<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><input type="color" value="${st.accent.toLowerCase()}"></label>`;
  el.colorField.classList.toggle('disabled', st.mode === 'none');
}

el.swatches.addEventListener('click', (e) => {
  const sw = e.target.closest('button.swatch');
  if (sw) setCaptionStyle({ color: sw.dataset.color || null });
});
el.swatches.addEventListener('input', (e) => {
  if (e.target.type === 'color') { S.cap.color = e.target.value.toUpperCase(); }
});
el.swatches.addEventListener('change', (e) => {
  if (e.target.type === 'color') setCaptionStyle({ color: e.target.value.toUpperCase() });
});

function setCaptionStyle(changes) {
  Object.assign(S.cap, changes);
  if (!S.styles) return;
  if (!S.styles[S.cap.style]) S.cap.style = S.defaultStyle;
  for (const tile of el.styleGrid.children) tile.classList.toggle('on', tile.dataset.style === S.cap.style);
  const st = effectiveStyle();
  el.fSize.value = S.cap.size;
  el.fSize.style.setProperty('--p', `${(S.cap.size - 60) / 100 * 100}%`);
  el.fSizeVal.textContent = `${S.cap.size}%`;
  el.fPos.value = st.margin_v;
  el.fPos.style.setProperty('--p', `${(st.margin_v - 120) / (1500 - 120) * 100}%`);
  el.fPosVal.textContent = `${Math.round(st.margin_v / 1920 * 100)}% from bottom`;
  renderSwatches();
}

el.fSize.addEventListener('input', () => setCaptionStyle({ size: +el.fSize.value }));
el.fPos.addEventListener('input', () => setCaptionStyle({ pos: +el.fPos.value }));
$('#btn-cap-reset').onclick = () => setCaptionStyle({ color: null, size: 100, pos: null });

$('#btn-cap-all').onclick = async () => {
  if (!S.clips.length) { toast('The queue is empty.', 'info'); return; }
  try {
    await saveClips(S.clips.map((c) => ({ ...stripStatus(c), ...captionFields() })));
    toast(`Caption style applied to ${S.clips.length} clip${S.clips.length === 1 ? '' : 's'}. Render them again to update the videos.`, 'ok',
      { label: 'Render all', fn: () => renderClips(S.clips.map((c) => c.name)) });
  } catch (err) {
    toast(err.message, 'error');
  }
};

/* ---------------------------------------------------------------- edit tab */

const BAR_COLORS = ['#00E5FF', '#FF2BD6', '#FFFF00', '#39FF14', '#FFFFFF', '#FF3B30'];

/* the parts of the source kept in the clip – same rules as clipper.edit_segments */
function editSegments() {
  if (S.inT == null || S.outT == null || S.outT <= S.inT) return null;
  const start = S.inT, end = Math.min(S.outT, S.duration || S.outT), ed = S.edit;   // clipper.plan_clip ends at the video's end
  const removed = S.cuts.concat(S.drops).map(([a, b]) => [a, b]);   // drops: parts deleted with the QML razor
  const inside = S.words.filter((w) => w.e > start && w.s < end);
  if (ed.removePauses && inside.length) {
    const gap = ed.pauseMin, lead = 0.08, tail = 0.12;
    if (inside[0].s - start > gap) removed.push([start, inside[0].s - lead]);
    for (let i = 1; i < inside.length; i++) {
      if (inside[i].s - inside[i - 1].e > gap) removed.push([inside[i - 1].e + tail, inside[i].s - lead]);
    }
    if (end - inside[inside.length - 1].e > gap) removed.push([inside[inside.length - 1].e + tail, end]);
  }
  let kept = [[start, end]];
  for (const [a, b] of removed.sort((x, y) => x[0] - y[0] || x[1] - y[1])) {
    const pieces = [];
    for (const [s, e] of kept) {
      if (b <= s || a >= e) { pieces.push([s, e]); continue; }
      if (a > s) pieces.push([s, a]);
      if (b < e) pieces.push([b, e]);
    }
    kept = pieces;
  }
  kept = kept.filter(([s, e]) => e - s >= 0.12);
  if (!ed.zoom) return kept.map(([s, e]) => [s, e, 1]);
  const marks = S.lines.map((l) => l.s);
  const pieces = [];
  for (const [s, e] of kept) {
    const edges = [s, ...marks.filter((m) => s + 0.8 < m && m < e - 0.8), e];
    for (let i = 0; i + 1 < edges.length; i++) pieces.push([edges[i], edges[i + 1]]);
  }
  return pieces.map(([s, e], i) => [s, e, i % 2 ? ed.zoomAmount : 1]);
}

function outputTime(t, segs, speed) {
  let offset = 0;
  for (const [a, b] of segs) {
    if (t < a) break;
    if (t <= b) return (offset + t - a) / speed;
    offset += b - a;
  }
  return offset / speed;
}

/* segments, final length and the clip's own caption words, recomputed only when something changes */
function editState() {
  const key = JSON.stringify([S.inT, S.outT, S.cuts, S.drops, S.edit.removePauses, S.edit.pauseMin, S.edit.zoom,
    S.edit.zoomAmount, S.edit.speed, S.edit.intro, S.mutes, S.edit.muteCaptions, S.transcriptStamp]);
  if (S.editCache.key === key) return S.editCache;
  const segs = editSegments();
  const speed = S.edit.speed;
  const intro = S.edit.intro && S.duration ? teaserRange() : null;
  const cache = { key, segs, speed, intro, introLen: intro ? intro[1] - intro[0] : 0, duration: 0, words: [],
    timelines: new Map() };
  if (segs && segs.length) {
    // play order: teaser first, then the kept pieces (same as clipper.map_words)
    const pieces = (intro ? [[intro[0], intro[1], 1]] : []).concat(segs);
    cache.duration = pieces.reduce((sum, [a, b]) => sum + b - a, 0) / speed;
    let offset = 0;
    for (const [a, b] of pieces) {
      for (const w of S.words) {
        if (w.e <= a - 1 || w.s >= b + 1) continue;
        const mid = wordMid(w);
        if (mid < a || mid > b) continue;
        const s = (offset + Math.max(w.s, a) - a) / speed, e = (offset + Math.min(w.e, b) - a) / speed;
        const hidden = S.edit.muteCaptions && S.mutes.some(([m0, m1]) => mid >= m0 && mid <= m1);
        cache.words.push({ w: hidden ? censor(w.w) : w.w, s, e: Math.max(s, e) });
      }
      offset += b - a;
    }
  }
  S.editCache = cache;
  return cache;
}

/* the teaser range, clamped like clipper.teaser_piece */
function teaserRange() {
  let [a, b] = S.edit.intro;
  a = Math.max(0, a);
  b = Math.min(b, S.duration, a + 15);
  return b - a >= 0.3 ? [a, b] : null;
}

/* where the playhead is on the finished clip's timeline (null when outside the clip) */
function clipTime(t, ed) {
  if (S.inIntro && ed.intro && t >= ed.intro[0] - 0.05 && t <= ed.intro[1] + 0.05) {
    return clamp(t - ed.intro[0], 0, ed.introLen) / ed.speed;
  }
  if (!ed.segs || !ed.segs.length || t < S.inT - 0.01 || t > S.outT + 0.01) return null;
  return ed.introLen / ed.speed + outputTime(t, ed.segs, ed.speed);
}

function editChanged() {
  const ed = S.edit;
  el.ePauses.checked = ed.removePauses;
  el.ePauseMin.value = Math.round(ed.pauseMin * 100);
  el.ePauseMin.style.setProperty('--p', `${(ed.pauseMin * 100 - 20) / 130 * 100}%`);
  el.ePauseVal.textContent = `${ed.pauseMin.toFixed(2).replace(/0$/, '')}s`;
  el.eZoom.checked = ed.zoom;
  el.eZoomAmt.value = Math.round(ed.zoomAmount * 100);
  el.eZoomAmt.style.setProperty('--p', `${(ed.zoomAmount * 100 - 105) / 35 * 100}%`);
  el.eZoomVal.textContent = `${Math.round(ed.zoomAmount * 100)}%`;
  for (const b of el.eSpeed.children) b.classList.toggle('on', +b.dataset.value === ed.speed);
  el.eProgress.checked = ed.progress;
  el.eProgressColors.innerHTML = BAR_COLORS.map((c) =>
    `<button class="swatch${ed.progressColor === c ? ' on' : ''}" data-color="${c}" style="background:${c}"></button>`).join('');
  el.eMusicName.textContent = ed.music ? ed.music.split(/[\\/]/).pop() : 'No music';
  el.eMusicName.classList.toggle('none', !ed.music);
  el.eMusicName.title = ed.music;
  el.eMusicClear.hidden = !ed.music;
  el.eMusicVol.value = Math.round(ed.musicVolume * 100);
  el.eMusicVol.style.setProperty('--p', `${ed.musicVolume * 100 / 60 * 100}%`);
  el.eMusicVal.textContent = `${Math.round(ed.musicVolume * 100)}%`;
  if (document.activeElement !== el.eWatermark) el.eWatermark.value = ed.watermark;
  for (const b of el.eWmPos.children) b.classList.toggle('on', b.dataset.value === ed.watermarkPos);
  video.defaultPlaybackRate = video.playbackRate = ed.speed;
  const musicSrc = ed.music ? `/media/music?path=${encodeURIComponent(ed.music)}` : '';
  if ((el.music.dataset.src || '') !== musicSrc) {
    el.music.dataset.src = musicSrc;
    if (musicSrc) el.music.src = musicSrc; else { el.music.pause(); el.music.removeAttribute('src'); }
  }
  el.music.volume = clamp(ed.musicVolume * 0.7, 0, 1);
  // teaser
  const intro = ed.intro;
  el.eIntro.checked = !!intro;
  el.teaserField.classList.toggle('on', !!intro);
  el.eIntroFlash.checked = ed.introFlash;
  for (const b of el.eMuteSound.children) b.classList.toggle('on', b.dataset.value === ed.muteSound);
  el.eMuteCaptions.checked = ed.muteCaptions;
  el.eCustomRow.hidden = ed.muteSound !== 'custom';
  el.eSfxName.textContent = ed.muteSfx ? ed.muteSfx.split(/[\\/]/).pop() : 'No sound file';
  el.eSfxName.classList.toggle('none', !ed.muteSfx);
  el.eSfxName.title = ed.muteSfx;
  el.eSfxVolRow.hidden = ed.muteSound === 'silence';
  el.eSfxVol.value = Math.round(ed.muteSfxVolume * 100);
  el.eSfxVol.style.setProperty('--p', `${ed.muteSfxVolume * 100 / 150 * 100}%`);
  el.eSfxVolVal.textContent = `${Math.round(ed.muteSfxVolume * 100)}%`;
  if (document.activeElement !== el.eIntroA) el.eIntroA.value = intro ? fmt(intro[0]) : '';
  if (document.activeElement !== el.eIntroB) el.eIntroB.value = intro ? fmt(intro[1]) : '';
  if (intro) {
    const said = S.words.filter((w) => wordMid(w) >= intro[0] && wordMid(w) <= intro[1]).map((w) => w.w).join(' ');
    el.eIntroInfo.textContent = `${(intro[1] - intro[0]).toFixed(1)}s${said ? ` · “${said.length > 48 ? `${said.slice(0, 48)}…` : said}”` : ''}`;
    el.eIntroInfo.title = said;
  } else {
    el.eIntroInfo.textContent = 'No teaser picked';
  }
  paintCuts();
  paintTeaser();
  updateLength();
}

function editFields() {
  const ed = S.edit;
  return {
    cuts: S.cuts, remove_pauses: ed.removePauses, pause_min: ed.pauseMin, zoom: ed.zoom, zoom_amount: ed.zoomAmount,
    speed: ed.speed, progress: ed.progress, progress_color: ed.progressColor, music: ed.music,
    music_volume: ed.musicVolume, watermark: ed.watermark, watermark_pos: ed.watermarkPos,
    intro_start: ed.intro ? round(ed.intro[0], 3) : null, intro_end: ed.intro ? round(ed.intro[1], 3) : null,
    intro_flash: ed.introFlash, mutes: S.mutes, mute_mode: ed.muteSound, mute_captions: ed.muteCaptions,
    mute_sfx: ed.muteSfx, mute_sfx_volume: ed.muteSfxVolume, drops: S.drops, splits: S.splits,
  };
}

function editFromClip(clip) {
  S.edit = {
    removePauses: !!clip.remove_pauses, pauseMin: clip.pause_min || 0.5, zoom: !!clip.zoom,
    zoomAmount: clip.zoom_amount || 1.15, speed: clip.speed || 1, progress: !!clip.progress,
    progressColor: clip.progress_color || '#00E5FF', music: clip.music || '', musicVolume: clip.music_volume ?? 0.15,
    watermark: clip.watermark || '', watermarkPos: clip.watermark_pos || 'tr',
    intro: clip.intro_start != null && clip.intro_end != null ? [clip.intro_start, clip.intro_end] : null,
    introFlash: clip.intro_flash !== false, muteSound: clip.mute_mode || 'silence',
    muteCaptions: clip.mute_captions !== false, muteSfx: clip.mute_sfx || '', muteSfxVolume: clip.mute_sfx_volume ?? 0.8,
  };
  S.cuts = normaliseCuts((clip.cuts || []).map(([a, b]) => [a, b]));
  S.mutes = normaliseCuts((clip.mutes || []).map(([a, b]) => [a, b]));
  S.drops = normaliseCuts((clip.drops || []).map(([a, b]) => [a, b]));
  S.splits = (clip.splits || []).slice();
  editChanged();
}

const isEdited = (c) => (c.cuts && c.cuts.length) || (c.drops && c.drops.length) || c.remove_pauses || c.zoom || (c.speed && c.speed !== 1);

/* 'damn,' -> 'd***,' – same as clipper.censor */
function censor(text) {
  const core = text.replace(/[.,!?;:"']+$/, '');
  if (!core) return text;
  return (core.length > 1 ? core[0] + '*'.repeat(core.length - 1) : '*') + text.slice(core.length);
}

el.eMuteMode.onclick = () => setMuteMode(!S.muteMode);
el.eMuteClear.onclick = () => { S.mutes = []; editChanged(); };
const SPEAKER = '<svg viewBox="0 0 24 24"><path d="M4 9h4l5-4v14l-5-4H4zM16 9a4 4 0 0 1 0 6"/></svg>';

function renderSoundGrid() {
  el.eMuteSound.innerHTML = Object.entries(S.muteSounds).map(([key, s]) =>
    `<button class="sound-tile" data-value="${key}">${key === 'silence' ? '' : SPEAKER}${escapeHtml(s.label)}</button>`).join('');
  editChanged();
}

async function pickCustomSound() {
  try {
    const res = await api.post('/api/pick-sfx');
    if (!res.path) return false;
    S.edit.muteSfx = res.path;
    toast(`Muted-word sound: ${res.name}`, 'ok');
    return true;
  } catch (err) {
    toast(err.message, 'error');
    return false;
  }
}

el.eMuteSound.onclick = async (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  const key = b.dataset.value;
  if (key === 'custom' && !S.edit.muteSfx && !(await pickCustomSound())) return;
  S.edit.muteSound = key;
  editChanged();
  playMuteSound(1.0, b);
};
el.eSfxPick.onclick = async () => { if (await pickCustomSound()) { S.edit.muteSound = 'custom'; editChanged(); playMuteSound(1.0); } };
el.eSfxVol.oninput = () => { S.edit.muteSfxVolume = +el.eSfxVol.value / 100; editChanged(); };
el.eMuteCaptions.onchange = () => { S.edit.muteCaptions = el.eMuteCaptions.checked; editChanged(); };

/* ---------------------------------------------------------------- teaser (highlight played first) */

function paintTeaser() {
  const intro = S.edit.intro;
  for (const span of el.lines.querySelectorAll('.w')) {
    const w = S.words[+span.dataset.wi];
    span.classList.toggle('teaser', !!intro && !!w && wordMid(w) >= intro[0] && wordMid(w) <= intro[1]);
  }
}

function setTeaser(range) {
  if (range) {
    let [a, b] = range;
    if (b < a) [a, b] = [b, a];
    range = [round(Math.max(0, a), 2), round(Math.min(b, a + 15), 2)];
    if (range[1] - range[0] < 0.3) range = null;
  }
  S.edit.intro = range;
  editChanged();
}

function setTeaserPick(mode) {
  S.teaserPick = mode;
  document.body.classList.toggle('teaser-pick', !!mode);
  el.eIntroPick.classList.toggle('on', !!mode);
  if (mode === 'start') {
    if (S.cutMode) setCutMode(false);
    if (S.muteMode) setMuteMode(false);
    toast('Teaser: click the FIRST word of the highlight in the transcript.', 'info');
  } else if (mode === 'end') {
    toast('Now click the LAST word of the highlight.', 'info');
  }
}

/* teaser edges around words first..last: a little breathing room, but never into the neighbouring words */
function teaserBounds(first, last) {
  const prev = S.words[first - 1], next = S.words[last + 1];
  const a = Math.max(S.words[first].s - 0.05, prev ? prev.e : 0);
  const b = next ? Math.min(S.words[last].e + 0.12, next.s + 0.02) : S.words[last].e + 0.12;
  return [Math.max(0, a), b];
}

function clickTeaserWord(i) {
  if (S.teaserPick === 'start') {
    S.teaserStartWord = i;
    setTeaserPick('end');
    return;
  }
  const first = Math.min(S.teaserStartWord, i), last = Math.max(S.teaserStartWord, i);
  setTeaser(teaserBounds(first, last));
  setTeaserPick(null);
  toast(`Teaser set: ${(S.edit.intro[1] - S.edit.intro[0]).toFixed(1)}s`, 'ok');
}

/* the most energetic 3–5 s inside the clip (loud speech, ending on a full stop / ! / ?) */
function autoTeaser() {
  if (S.inT == null || S.outT == null) { toast('Pick the clip range first.', 'info'); return null; }
  const firstIdx = S.words.findIndex((w) => w.s >= S.inT);
  const words = S.words.filter((w) => w.s >= S.inT && w.e <= S.outT);
  if (firstIdx < 0 || words.length < 3) { toast('Not enough speech in this clip to pick a teaser.', 'info'); return null; }
  const energy = (a, b) => {
    if (!S.peaks) return 0;
    let sum = 0, n = 0;
    for (let k = Math.floor(a * S.peakRate); k < Math.ceil(b * S.peakRate) && k < S.peaks.length; k++) { sum += S.peaks[k]; n++; }
    return n ? sum / n / 255 : 0;
  };
  const clipLen = S.outT - S.inT;
  let best = null;
  for (let i = 0; i < words.length; i++) {
    // start on a sentence start (after . ! ? or the first word) – teasers that start mid-sentence feel random
    const starts = i === 0 || /[.!?,]$/.test(words[i - 1].w);
    for (let j = i; j < words.length; j++) {
      const len = words[j].e - words[i].s;
      if (len > 5.5) break;
      if (len < 2.5) continue;
      const ends = /[.!?]$/.test(words[j].w);
      const midway = (words[i].s - S.inT) / clipLen;  // later moments make better teasers
      const score = energy(words[i].s, words[j].e) + (ends ? 0.25 : 0) + (starts ? 0.15 : 0)
        + (/[!?]$/.test(words[j].w) ? 0.1 : 0) + midway * 0.2 - Math.abs(len - 4) * 0.03;
      if (!best || score > best.score) best = { score, i, j };
    }
  }
  if (!best) { toast('Couldn’t find a 3–5 s highlight in this clip.', 'info'); return null; }
  return teaserBounds(firstIdx + best.i, firstIdx + best.j);
}

function playTeaser() {
  const intro = editState().intro;
  if (!intro) { toast('Pick a teaser first.', 'info'); return; }
  S.inIntro = true;
  video.currentTime = intro[0];
  video.play().catch(() => {});
}

el.eIntro.onchange = () => {
  if (!el.eIntro.checked) { setTeaser(null); return; }
  const picked = autoTeaser();
  if (picked) { setTeaser(picked); toast('Teaser auto-picked – change it with Pick words or the times.', 'ok'); }
  else el.eIntro.checked = false;
};
el.eIntroAuto.onclick = () => { const picked = autoTeaser(); if (picked) setTeaser(picked); };
el.eIntroPick.onclick = () => setTeaserPick(S.teaserPick ? null : 'start');
el.eIntroPlay.onclick = playTeaser;
el.eIntroFlash.onchange = () => { S.edit.introFlash = el.eIntroFlash.checked; };
$('#e-intro-set-a').onclick = () => {
  const t = video.currentTime;
  const b = S.edit.intro && S.edit.intro[1] > t + 0.3 ? S.edit.intro[1] : t + 4;
  setTeaser([t, b]);
};
$('#e-intro-set-b').onclick = () => {
  const t = video.currentTime;
  const a = S.edit.intro && S.edit.intro[0] < t - 0.3 ? S.edit.intro[0] : Math.max(0, t - 4);
  setTeaser([a, t]);
};
for (const [input, which] of [[el.eIntroA, 0], [el.eIntroB, 1]]) {
  input.addEventListener('change', () => {
    const t = parseTime(input.value);
    input.classList.toggle('bad', t == null);
    if (t == null) return;
    const range = S.edit.intro ? [...S.edit.intro] : [t, t + 4];
    range[which] = t;
    if (which === 0 && !S.edit.intro) range[1] = t + 4;
    setTeaser(range);
  });
}

el.ePauses.onchange = () => { S.edit.removePauses = el.ePauses.checked; editChanged(); };
el.ePauseMin.oninput = () => { S.edit.pauseMin = +el.ePauseMin.value / 100; editChanged(); };
el.eZoom.onchange = () => { S.edit.zoom = el.eZoom.checked; editChanged(); };
el.eZoomAmt.oninput = () => { S.edit.zoomAmount = +el.eZoomAmt.value / 100; editChanged(); };
el.eSpeed.onclick = (e) => { const b = e.target.closest('button'); if (b) { S.edit.speed = +b.dataset.value; editChanged(); } };
el.eProgress.onchange = () => { S.edit.progress = el.eProgress.checked; editChanged(); };
el.eProgressColors.onclick = (e) => {
  const b = e.target.closest('button');
  if (b) { S.edit.progressColor = b.dataset.color; S.edit.progress = true; editChanged(); }
};
el.eMusicVol.oninput = () => { S.edit.musicVolume = +el.eMusicVol.value / 100; editChanged(); };
el.eMusicClear.onclick = () => { S.edit.music = ''; editChanged(); };
el.eMusicPick.onclick = async () => {
  try {
    const res = await api.post('/api/pick-music');
    if (res.path) { S.edit.music = res.path; editChanged(); toast(`Music: ${res.name}`, 'ok'); }
  } catch (err) {
    toast(err.message, 'error');
  }
};
el.eWatermark.oninput = () => { S.edit.watermark = el.eWatermark.value.trim(); };
el.eWmPos.onclick = (e) => { const b = e.target.closest('button'); if (b) { S.edit.watermarkPos = b.dataset.value; editChanged(); } };
el.eCutMode.onclick = () => setCutMode(!S.cutMode);
el.eCutClear.onclick = () => { S.cuts = []; editChanged(); };

$('#btn-edit-all').onclick = async () => {
  if (!S.clips.length) { toast('The queue is empty.', 'info'); return; }
  const { cuts, mutes, intro_start, intro_end, drops, splits, ...settings } = editFields();  // cuts, mutes and teasers stay per clip
  try {
    await saveClips(S.clips.map((c) => ({ ...stripStatus(c), ...settings })));
    toast(`Edit settings applied to ${S.clips.length} clip${S.clips.length === 1 ? '' : 's'} (cuts stay per clip).`, 'ok',
      { label: 'Render all', fn: () => renderClips(S.clips.map((c) => c.name)) });
  } catch (err) {
    toast(err.message, 'error');
  }
};

/* ---------------------------------------------------------------- queue cards */

const ICONS = {
  play: '<svg viewBox="0 0 24 24"><path d="M8 5l11 7-11 7z"/></svg>',
  render: '<svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>',
  folder: '<svg viewBox="0 0 24 24"><path d="M3 7h6l2 2h10v10H3z"/></svg>',
  trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>',
};
const STATE_LABEL = { new: 'Not rendered', queued: 'Queued', ready: 'Ready', error: 'Error' };

function renderCards() {
  const sig = JSON.stringify([S.clips, S.editing, S.busy]);
  if (sig === S.cardsSig) return;
  S.cardsSig = sig;
  el.queueCount.textContent = S.clips.length;
  el.btnRenderAll.disabled = S.busy || !S.clips.length;
  if (!S.clips.length) {
    el.cards.innerHTML = '<div class="cards-empty">NO CLIPS YET  ·  PICK A MOMENT, THEN “ADD TO QUEUE”</div>';
    return;
  }
  el.cards.replaceChildren(...S.clips.map((clip) => {
    const st = clip.status || { state: 'new' };
    const ready = st.state === 'ready';
    const label = st.state === 'rendering' ? `Rendering ${st.progress || 0}%` : (STATE_LABEL[st.state] || st.state);
    const card = document.createElement('div');
    card.className = `card${clip.name === S.editing ? ' editing' : ''}`;
    card.dataset.name = clip.name;
    card.innerHTML = `
      <div class="card-top"><span class="card-name"></span><span class="pill ${st.state}">${label}</span></div>
      <div class="card-times mono">${fmt(clip.start)} → ${fmt(clip.end)}  ·  ${(typeof st.length === 'number' ? st.length : clip.end - clip.start).toFixed(1)}s</div>
      <div class="card-tags"><span class="pill layout">${clip.layout}</span>
        <span class="pill style">${clip.captions === false ? 'no captions' : (S.styles?.[clip.caption_style]?.label || 'Classic')}</span>
        ${isEdited(clip) ? '<span class="pill edited">edited</span>' : ''}
        ${clip.intro_start != null ? '<span class="pill teaser">teaser</span>' : ''}
        ${clip.mutes && clip.mutes.length ? '<span class="pill muted">muted</span>' : ''}</div>
      <div class="card-hook"></div>
      <div class="card-actions">
        <button class="icon-btn" data-act="play" title="Watch the rendered clip" ${ready ? '' : 'disabled'}>${ICONS.play}</button>
        <button class="icon-btn" data-act="render" title="Render this clip" ${S.busy ? 'disabled' : ''}>${ICONS.render}</button>
        <button class="icon-btn" data-act="reveal" title="Show in folder" ${ready ? '' : 'disabled'}>${ICONS.folder}</button>
        <div class="spacer"></div>
        <button class="icon-btn danger" data-act="delete" title="Remove from queue">${ICONS.trash}</button>
      </div>
      ${st.state === 'rendering' ? `<div class="card-progress" style="width:${st.progress || 0}%"></div>` : ''}`;
    card.querySelector('.card-name').textContent = clip.name;
    const hook = card.querySelector('.card-hook');
    hook.textContent = clip.hook || 'No hook text';
    hook.classList.toggle('none', !clip.hook);
    if (st.error) card.title = st.error;
    for (const fn of HOOKS.card) fn(card, clip);
    return card;
  }));
}

el.cards.addEventListener('click', async (e) => {
  const card = e.target.closest('.card');
  if (!card) return;
  const clip = S.clips.find((c) => c.name === card.dataset.name);
  if (!clip) return;
  const act = e.target.closest('[data-act]')?.dataset.act;
  if (act === 'play') openPlayer(clip);
  else if (act === 'render') renderClips([clip.name]);
  else if (act === 'reveal') api.post('/api/reveal', { name: clip.name }).catch((err) => toast(err.message, 'error'));
  else if (act === 'delete') {
    if (S.editing === clip.name) newClip(false);
    try {
      await saveClips(S.clips.filter((c) => c.name !== clip.name));
      markQueuedLines();
    } catch (err) {
      toast(err.message, 'error');
    }
  } else loadClip(clip);
});

function loadClip(clip) {
  setEditing(clip.name);
  applyClipFields(clip);
  seek(clip.start);
  const first = S.lines.findIndex((l) => l.e > clip.start);
  if (first >= 0) lineNodes()[first].scrollIntoView({ block: 'center', behavior: 'smooth' });
}

/* put a clip's settings into the editor (loading a clip, undo / redo) */
function applyClipFields(clip) {
  el.fName.value = clip.name;
  setRange(clip.start, clip.end);
  setLayout(clip.layout || 'crop');
  setCrop(clip.crop_x ?? 0.5);
  el.fHook.value = clip.hook || '';
  el.fPost.value = clip.post_caption || '';
  el.fCaptions.checked = clip.captions !== false;
  setCaptionStyle({
    style: clip.caption_style || S.defaultStyle, color: clip.caption_color || null,
    size: clip.caption_size || 100, pos: clip.caption_pos ?? null,
  });
  editFromClip(clip);
  setHookStyle({
    style: clip.hook_style || S.defaultHook, size: clip.hook_size || 100,
    pos: clip.hook_pos ?? null, duration: clip.hook_duration || 0,
  });
  S.frameY = clip.frame_y ?? 0.5;
  setFrameZoom(clip.frame_zoom || 1);
  for (const fn of HOOKS.apply) fn(clip);
}

/* ---------------------------------------------------------------- rendered clip player */

function openPlayer(clip) {
  const st = clip.status || {};
  el.playerTitle.textContent = clip.name;
  el.playerCaption.textContent = clip.post_caption || '';
  el.playerVideo.src = `/media/clip/${encodeURIComponent(clip.name)}.mp4?v=${st.mtime || Date.now()}`;
  el.player.hidden = false;
  el.player.dataset.name = clip.name;
  video.pause();
  el.playerVideo.play().catch(() => {});
}

function closePlayer() {
  el.playerVideo.pause();
  el.playerVideo.removeAttribute('src');
  el.playerVideo.load();
  el.player.hidden = true;
}
$('#player-close').onclick = closePlayer;
el.player.addEventListener('click', (e) => { if (e.target === el.player) closePlayer(); });
$('#player-reveal').onclick = () =>
  api.post('/api/reveal', { name: el.player.dataset.name }).catch((err) => toast(err.message, 'error'));

/* ---------------------------------------------------------------- playback */

function seek(t) {
  if (!S.duration || !video.src) return;
  S.inIntro = false;  // a manual seek leaves the teaser
  video.currentTime = clamp(t, 0, Math.max(0, S.duration - 0.05));
}

/* start of the finished clip: the teaser if there is one, else the first kept piece */
function playFromClipStart(ed) {
  if (ed.intro) {
    S.inIntro = true;
    video.currentTime = ed.intro[0];
  } else {
    S.inIntro = false;
    video.currentTime = ed.segs && ed.segs.length ? ed.segs[0][0] : S.inT;
  }
}

function togglePlay() {
  if (!video.src) return;
  if (video.paused) {
    const t = video.currentTime;
    const ed = editState();
    const atStart = S.inT != null && Math.abs(t - S.inT) < 0.05;
    const outside = S.inT != null && S.outT != null && (t < S.inT - 0.05 || t >= S.outT - 0.05);
    if (S.loop && !S.inIntro && (outside || (atStart && ed.intro))) playFromClipStart(ed);
    video.play().catch(() => {});
  } else {
    video.pause();
  }
}

/* while the clip plays, background music follows the clip's own timeline */
function syncMusic() {
  const t = video.currentTime;
  const out = clipTime(t, editState());
  if (!S.edit.music || video.paused || out == null || !el.music.src) { el.music.pause(); return; }
  if (el.music.duration) el.music.currentTime = out % el.music.duration;
  el.music.play().catch(() => {});
}

el.btnPlay.onclick = togglePlay;
$('#btn-back').onclick = () => seek(video.currentTime - 5);
$('#btn-fwd').onclick = () => seek(video.currentTime + 5);
video.addEventListener('play', () => { el.btnPlay.classList.add('playing'); syncMusic(); });
video.addEventListener('pause', () => { el.btnPlay.classList.remove('playing'); el.music.pause(); });
video.addEventListener('seeked', () => { if (!video.paused) syncMusic(); });
el.btnLoop.onclick = () => { S.loop = !S.loop; el.btnLoop.classList.toggle('on', S.loop); };
el.btnSafe.onclick = () => { S.safe = !S.safe; el.btnSafe.classList.toggle('on', S.safe); };

/* the frame position at source time t: the last speaker switch at or before t, else the clip's own
   (same rule as clipper.position_track) */
function framePos(t = video.currentTime) {
  let idx = -1;
  S.keyframes.forEach((k, i) => { if (k.t <= t + 0.001) idx = i; });
  return idx >= 0 ? { x: S.keyframes[idx].x, y: S.keyframes[idx].y, idx } : { x: S.cropX, y: S.frameY, idx: -1 };
}

/* moving the picture changes whichever position is active at the playhead */
function setFramePos(x, y) {
  const pos = framePos();
  if (pos.idx >= 0) {
    S.keyframes[pos.idx].x = round(clamp(x, 0, 1), 3);
    S.keyframes[pos.idx].y = round(clamp(y, 0, 1), 3);
  } else {
    setCrop(x);
    S.frameY = clamp(y, 0, 1);
  }
}

/* where the video sits in the 9:16 frame – mirrors clipper.layout_filter */
function frameGeometry(vw, vh, pos = framePos()) {
  const z = S.frameZoom;
  if (S.layout === 'fit') {
    const w = CW * z, h = w * vh / vw;
    return { mode: 'fit', w, h, x: (CW - w) * pos.x, y: (CH - h) * pos.y };
  }
  const cw = Math.min(vh * 9 / 16, vw) / z, ch = vh / z;
  return { mode: 'crop', cw, ch, sx: (vw - cw) * pos.x, sy: (vh - ch) * pos.y };
}

/* drag the preview to move the video; the picture follows the mouse in both layouts */
el.phone.addEventListener('pointerdown', (e) => {
  const vw = video.videoWidth, vh = video.videoHeight;
  if (!vw || vw / vh <= 9 / 16 + 0.01) return;
  const rect = el.phone.getBoundingClientRect();
  const k = CW / rect.width;  // canvas pixels per screen pixel
  const start = framePos();
  const startX = e.clientX, startY = e.clientY, x0 = start.x, y0 = start.y;
  const g = frameGeometry(vw, vh, start);
  el.phone.setPointerCapture(e.pointerId);
  el.phone.classList.add('dragging');
  const move = (ev) => {
    const dx = (ev.clientX - startX) * k, dy = (ev.clientY - startY) * k;
    let x = x0, y = y0;
    if (g.mode === 'fit') {
      if (Math.abs(CW - g.w) > 1) x = x0 + dx / (CW - g.w);
      if (Math.abs(CH - g.h) > 1) y = y0 + dy / (CH - g.h);
    } else {
      if (vw - g.cw > 1) x = x0 - dx * (g.cw / CW) / (vw - g.cw);
      if (vh - g.ch > 1) y = y0 - dy * (g.ch / CH) / (vh - g.ch);
    }
    setFramePos(x, y);
  };
  const up = () => {
    el.phone.classList.remove('dragging');
    el.phone.removeEventListener('pointermove', move);
    el.phone.removeEventListener('pointerup', up);
  };
  el.phone.addEventListener('pointermove', move);
  el.phone.addEventListener('pointerup', up);
});

/* mouse wheel on the preview zooms the video in / out */
el.phone.addEventListener('wheel', (e) => {
  e.preventDefault();
  setFrameZoom(S.frameZoom * Math.exp(-clamp(e.deltaY, -300, 300) * 0.0015));  // one notch ≈ 15%
}, { passive: false });

/* ---------------------------------------------------------------- preview drawing */

function drawPreview() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, CW, CH);
  const vw = video.videoWidth, vh = video.videoHeight;
  const t = video.currentTime;
  const ed = editState();
  const out = clipTime(t, ed);  // position on the finished clip (teaser + edits), or null outside it
  const inClip = out != null;
  const piece = inClip && !S.inIntro ? ed.segs.find(([a, b]) => t >= a - 0.01 && t <= b + 0.01) : null;
  const zoom = piece ? piece[2] : 1;
  if (zoom !== 1) {  // same punch-in point as the render: centre, upper third
    const px = CW / 2, py = CH * 0.35;
    ctx.setTransform(zoom, 0, 0, zoom, px - zoom * px, py - zoom * py);
  }
  if (video.readyState >= 2 && vw) {
    if (vw / vh <= 9 / 16 + 0.01) {
      const s = Math.min(CW / vw, CH / vh);
      ctx.drawImage(video, (CW - vw * s) / 2, (CH - vh * s) / 2, vw * s, vh * s);
    } else {
      const g = frameGeometry(vw, vh);
      if (g.mode === 'fit') {
        const s = Math.max(CW / vw, CH / vh) * 1.08;
        ctx.filter = 'blur(12px)';
        ctx.drawImage(video, (CW - vw * s) / 2, (CH - vh * s) / 2, vw * s, vh * s);
        ctx.filter = 'none';
        ctx.drawImage(video, g.x, g.y, g.w, g.h);
      } else {
        ctx.drawImage(video, g.sx, g.sy, g.cw, g.ch, 0, 0, CW, CH);
      }
    }
  } else {
    drawNoSignal();
  }
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  for (const fn of HOOKS.overlay) fn(ctx, { t, out, inClip, ed });  // pop-ups sit under the captions
  // inside the clip, captions follow the edited timeline (teaser first, cut words gone, speed applied)
  if (S.styles && S.words.length && el.fCaptions.checked) drawCaptions(inClip ? out : t, inClip ? ed : null);
  const hook = el.fHook.value.trim();
  const hs = effectiveHook();
  if (hook && hs && !(inClip && hs.duration && out > hs.duration)) drawHook(hook, hs);
  if (S.edit.watermark) drawWatermark(S.edit.watermark, S.edit.watermarkPos);
  if (inClip && ed.intro && S.edit.introFlash) {  // the white flash where the teaser ends
    const cutAt = ed.introLen / ed.speed;
    if (out >= cutAt - 0.04 && out <= cutAt + 0.1) {
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      ctx.fillRect(0, 0, CW, CH);
    }
  }
  if (S.edit.progress && inClip && ed.duration) {
    ctx.fillStyle = S.edit.progressColor;
    ctx.fillRect(0, CH - 16 * K, CW * clamp(out / ed.duration, 0, 1), 16 * K);
  }
  if (S.inIntro && inClip) {
    ctx.font = '600 11px "Cascadia Mono"';
    ctx.fillStyle = 'rgba(255,181,71,0.95)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText('▶ TEASER', CW / 2, 40);
    ctx.textAlign = 'left';
  }
  if (S.safe) drawSafeZones();
}

// the render's ASS Mark style: 60 % black outline (&H66000000), 80 % white letters filled straight over the video
// (libass leaves the outline out under the letters), so it is drawn on its own layer with the letters cut out
let markCanvas = null;
function drawWatermark(text, pos) {
  text = text.replace(/\n/g, ' ').replace(/[{}\\]/g, '').trim();  // build_ass: clean_word(watermark)
  if (!text) return;
  if (!markCanvas) markCanvas = document.createElement('canvas');
  if (markCanvas.width !== CW || markCanvas.height !== CH) { markCanvas.width = CW; markCanvas.height = CH; }
  const m = markCanvas.getContext('2d');
  m.clearRect(0, 0, CW, CH);
  const size = 38 * K, mx = 50 * K, my = 70 * K;
  m.font = `600 ${size}px "Segoe UI Semibold", "Segoe UI"`;
  m.textAlign = pos[1] === 'l' ? 'left' : 'right';
  m.textBaseline = pos[0] === 't' ? 'top' : 'bottom';
  const x = pos[1] === 'l' ? mx : CW - mx, y = pos[0] === 't' ? my : CH - my;
  m.lineWidth = 4 * K;
  m.strokeStyle = 'rgba(0,0,0,0.6)';
  m.strokeText(text, x, y);
  m.globalCompositeOperation = 'destination-out';
  m.fillStyle = '#000';
  m.fillText(text, x, y);
  m.globalCompositeOperation = 'source-over';
  m.fillStyle = 'rgba(255,255,255,0.8)';
  m.fillText(text, x, y);
  ctx.drawImage(markCanvas, 0, 0);
}

function drawNoSignal() {
  ctx.strokeStyle = 'rgba(130,170,255,0.07)';
  ctx.lineWidth = 1;
  for (let x = 0; x <= CW; x += 30) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, CH); ctx.stroke(); }
  for (let y = 0; y <= CH; y += 30) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(CW, y); ctx.stroke(); }
  if (!S.videoKey) return;
  ctx.fillStyle = 'rgba(123,138,169,0.55)';
  ctx.font = '600 26px Bahnschrift';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('NO SIGNAL', CW / 2, CH / 2);
  ctx.textAlign = 'left';
}

/* the caption look for the clip being edited: preset + colour/size/height tweaks (mirrors resolve_style) */
function effectiveStyle() {
  const base = S.styles[S.cap.style] || S.styles[S.defaultStyle];
  const st = { ...base };
  if (S.cap.color) st.accent = S.cap.color;
  st.size = Math.round(base.size * clamp(S.cap.size, 50, 200) / 100);
  if (S.cap.pos != null) st.margin_v = S.cap.pos;
  return st;
}

/* same grouping as clipper.caption_chunks / caption_timeline */
function timelineFor(st, words = S.words, cache = S.timelines) {
  const key = `${st.max_words}|${st.max_chars}`;
  if (cache.has(key)) return cache.get(key);
  const chunks = [];
  let cur = [];
  for (const w of words) {
    if (cur.length) {
      const last = cur[cur.length - 1];
      const joined = cur.map((x) => x.w).join(' ').length + 1 + w.w.length;
      if (cur.length >= st.max_words || joined > st.max_chars || /[.?!,]$/.test(last.w) || w.s - last.e > 0.5) {
        chunks.push(cur);
        cur = [];
      }
    }
    cur.push(w);
  }
  if (cur.length) chunks.push(cur);
  const timeline = chunks.map((chunk, i) => {
    let end = chunk[chunk.length - 1].e;
    if (i + 1 < chunks.length && chunks[i + 1][0].s - end < 0.35) end = chunks[i + 1][0].s;
    return { words: chunk, end };
  });
  cache.set(key, timeline);
  return timeline;
}

function captionAt(t, timeline) {
  const idx = lastAtOrBefore(timeline, t, (c) => c.words[0].s);
  if (idx < 0 || t >= timeline[idx].end) return null;
  const words = timeline[idx].words;
  return { words, active: Math.max(0, lastAtOrBefore(words, t, (w) => w.s)) };
}

function drawCaptions(t, ed = null) {
  const st = effectiveStyle();
  const hit = captionAt(t, ed ? timelineFor(st, ed.words, ed.timelines) : timelineFor(st));
  if (!hit) return;
  const { active } = hit;
  const texts = hit.words.map((w) => (st.uppercase ? w.w.toUpperCase() : w.w));
  const weight = st.bold ? '700 ' : '';
  const grow = (i) => (st.mode === 'word' && i === active ? st.active_scale : 1);
  const size = st.size * K;
  const fontAt = (i) => `${weight}${size * grow(i)}px "${st.font}"`;

  // measure, then wrap into lines that fit (libass wraps the same way)
  ctx.font = `${weight}${size}px "${st.font}"`;
  const space = ctx.measureText(' ').width;
  const widths = texts.map((tx, i) => { ctx.font = fontAt(i); return ctx.measureText(tx).width; });
  const maxW = CW - 120 * K;
  const lines = [];
  let line = [], lineW = 0;
  texts.forEach((_, i) => {
    const add = (line.length ? space : 0) + widths[i];
    if (line.length && lineW + add > maxW) { lines.push({ idx: line, w: lineW }); line = []; lineW = 0; }
    lineW += (line.length ? space : 0) + widths[i];
    line.push(i);
  });
  if (line.length) lines.push({ idx: line, w: lineW });

  const dt = t - hit.words[0].s;
  const pop = active === 0 && st.pop !== 1 && st.active_scale === 1 && dt < 0.09 ? st.pop - (st.pop - 1) * (dt / 0.09) : 1;
  const lineH = size * 1.12;
  const placed = [];
  lines.forEach((ln, row) => {
    let x = -ln.w / 2;
    const y = -(lines.length - 1 - row) * lineH;
    for (const i of ln.idx) { placed.push({ i, x, y }); x += widths[i] + space; }
  });

  ctx.save();
  ctx.translate(CW / 2, CH - st.margin_v * K);
  ctx.scale(pop, pop);
  ctx.textBaseline = 'bottom';
  ctx.lineJoin = 'round';
  const outlineW = st.outline * 2 * K;
  const isBoxed = (i) => st.mode === 'box' && i === active;
  if (st.shadow) {
    const off = st.shadow * K;
    ctx.fillStyle = ctx.strokeStyle = 'rgba(0,0,0,0.5)';
    ctx.lineWidth = outlineW;
    for (const p of placed) {
      ctx.font = fontAt(p.i);
      if (st.outline) ctx.strokeText(texts[p.i], p.x + off, p.y + off);
      ctx.fillText(texts[p.i], p.x + off, p.y + off);
    }
  }
  for (const p of placed) {
    if (!isBoxed(p.i)) continue;
    ctx.font = fontAt(p.i);
    const m = ctx.measureText(texts[p.i]);
    const pad = st.box_pad * K;
    ctx.fillStyle = st.accent;
    ctx.beginPath();
    ctx.roundRect(p.x - pad, p.y - m.actualBoundingBoxAscent - pad, widths[p.i] + pad * 2,
      m.actualBoundingBoxAscent + m.actualBoundingBoxDescent + pad * 2, pad);
    ctx.fill();
  }
  if (st.outline) {
    ctx.strokeStyle = st.outline_color;
    ctx.lineWidth = outlineW;
    if (st.glow) { ctx.shadowColor = st.outline_color; ctx.shadowBlur = st.glow * K * 2.4; }
    for (const p of placed) {
      if (isBoxed(p.i)) continue;
      ctx.font = fontAt(p.i);
      ctx.strokeText(texts[p.i], p.x, p.y);
    }
    ctx.shadowBlur = 0;
  }
  for (const p of placed) {
    const lit = (st.mode === 'word' && p.i === active) || (st.mode === 'fill' && p.i <= active);
    const boxed = st.mode === 'box' && p.i === active;
    const keyword = S.kw.on && !lit && !boxed && keywordEmoji(texts[p.i])[0];
    ctx.fillStyle = lit ? st.accent : keyword ? S.kw.color : st.text;
    ctx.font = fontAt(p.i);
    ctx.fillText(texts[p.i], p.x, p.y);
  }
  ctx.restore();
  // keyword emoji above the captions – same place as clipper.render_clip puts it
  const emoji = S.kw.emojis ? texts.map((tx) => keywordEmoji(tx)[1]).find(Boolean) : '';
  if (emoji) {
    const box = S.emojiSize * K;
    const top = CH - st.margin_v * K - st.size * K * 1.25 - box - 10 * K;
    ctx.save();
    ctx.font = `${box * 0.86}px "Segoe UI Emoji"`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(emoji, CW / 2, top + box / 2);
    ctx.restore();
  }
}

/* same as clipper.bare_word / keyword_emoji: [is keyword, emoji or ''] */
function keywordEmoji(text) {
  const word = text.toLowerCase().replace(/[^\p{L}\p{N}_$%'-]/gu, '').replace(/^['-]+|['-]+$/g, '');
  if (!word) return [false, ''];
  if (/\d/.test(word) || word.startsWith('$') || word.endsWith('%')) return [true, word.startsWith('$') ? '💰' : ''];
  const emoji = S.keywords[word] || (word.endsWith('s') ? S.keywords[word.slice(0, -1)] : '');
  return emoji ? [true, emoji] : [false, ''];
}

function wrapText(text, maxW) {
  const words = text.split(/\s+/);
  const lines = [];
  let line = '';
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(test).width > maxW) { lines.push(line); line = word; } else line = test;
  }
  if (line) lines.push(line);
  return lines;
}

/* the hook title – mirrors clipper.hook_style_line (box = solid box per line, outline = stroked text) */
function drawHook(text, hs) {
  const size = hs.size * K, lineH = size * 1.18, top = hs.margin_v * K;
  const boxed = hs.mode === 'box';
  const pad = boxed ? hs.pad * K : 0;
  ctx.save();
  ctx.font = `${size}px "${hs.font}"`;
  ctx.textBaseline = 'top';
  ctx.textAlign = 'center';
  ctx.lineJoin = 'round';
  const lines = wrapText(hs.uppercase ? text.toUpperCase() : text, CW - 180 * K - pad * 2);
  const ys = lines.map((_, i) => top + i * lineH + size * 0.06);
  if (boxed) {
    ctx.fillStyle = hs.box;
    lines.forEach((line, i) => {
      const w = ctx.measureText(line).width;
      ctx.fillRect(CW / 2 - w / 2 - pad, top + i * lineH - pad, w + pad * 2, size + pad * 2);
    });
  } else {
    const outlineW = hs.outline * 2 * K;
    if (hs.shadow) {
      ctx.fillStyle = ctx.strokeStyle = 'rgba(0,0,0,0.5)';
      ctx.lineWidth = outlineW;
      lines.forEach((line, i) => {
        ctx.strokeText(line, CW / 2 + hs.shadow * K, ys[i] + hs.shadow * K);
        ctx.fillText(line, CW / 2 + hs.shadow * K, ys[i] + hs.shadow * K);
      });
    }
    if (hs.outline) {
      ctx.strokeStyle = hs.outline_color;
      ctx.lineWidth = outlineW;
      if (hs.glow) { ctx.shadowColor = hs.outline_color; ctx.shadowBlur = hs.glow * K * 2.4; }
      lines.forEach((line, i) => ctx.strokeText(line, CW / 2, ys[i]));
      ctx.shadowBlur = 0;
    }
  }
  ctx.fillStyle = hs.text;
  lines.forEach((line, i) => ctx.fillText(line, CW / 2, ys[i]));
  ctx.restore();
}

function drawSafeZones() {
  const zones = [[0, 0, 1080, 160], [0, 1600, 1080, 320], [930, 760, 150, 840]];
  ctx.save();
  ctx.fillStyle = 'rgba(255,43,214,0.16)';
  ctx.strokeStyle = 'rgba(255,43,214,0.75)';
  ctx.setLineDash([6, 5]);
  ctx.lineWidth = 1.5;
  for (const [x, y, w, h] of zones) {
    ctx.fillRect(x * K, y * K, w * K, h * K);
    ctx.strokeRect(x * K + 0.75, y * K + 0.75, w * K - 1.5, h * K - 1.5);
  }
  ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(255,170,240,0.95)';
  ctx.font = '600 11px "Cascadia Mono"';
  ctx.textBaseline = 'top';
  ctx.fillText('APP UI COVERS THIS', 10, 1610 * K);
  ctx.restore();
}

/* ---------------------------------------------------------------- waveform strip + overview */

function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width * dpr)), h = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  return { w, h, dpr };
}

function stripWindow() {
  if (S.dragWindow) return S.dragWindow;
  const dur = S.duration || 1;
  let a, b;
  if (S.inT != null && S.outT != null && S.outT > S.inT) {
    const pad = Math.max(2, (S.outT - S.inT) * 0.25);
    a = S.inT - pad; b = S.outT + pad;
  } else {
    const t = video.currentTime || 0;
    a = t - 15; b = t + 15;
  }
  const span = Math.min(b - a, dur);
  if (a < 0) { a = 0; b = span; }
  if (b > dur) { b = dur; a = Math.max(0, dur - span); }
  return [a, b];
}

function drawStrip() {
  const c = el.strip.getContext('2d');
  const { w, h, dpr } = fitCanvas(el.strip);
  c.clearRect(0, 0, w, h);
  if (!S.duration) return;
  const [a, b] = stripWindow();
  S.stripView = [a, b];
  const X = (t) => (t - a) / (b - a) * w;
  const hasRange = S.inT != null && S.outT != null && S.outT > S.inT;
  const segs = hasRange ? editState().segs || [] : [];
  const intro = hasRange ? editState().intro : null;
  c.fillStyle = '#8b5cff';  // muted words: violet bar along the bottom
  for (const [m0, m1] of S.mutes) {
    if (m1 > a && m0 < b) c.fillRect(X(m0), h - 4 * dpr, Math.max(2 * dpr, X(m1) - X(m0)), 4 * dpr);
  }
  if (intro && intro[1] > a && intro[0] < b) {  // the teaser: amber band with a top marker
    c.fillStyle = 'rgba(255,181,71,0.14)';
    c.fillRect(X(intro[0]), 0, X(intro[1]) - X(intro[0]), h);
    c.fillStyle = '#ffb547';
    c.fillRect(X(intro[0]), 0, X(intro[1]) - X(intro[0]), 3 * dpr);
  }
  if (hasRange) {
    c.fillStyle = 'rgba(0,229,255,0.07)';
    c.fillRect(X(S.inT), 0, X(S.outT) - X(S.inT), h);
    // parts that are cut out of the clip: red hatching
    let prev = S.inT;
    c.fillStyle = 'rgba(255,77,109,0.13)';
    for (const [sa, sb] of [...segs, [S.outT, S.outT]]) {
      if (sa - prev > 0.02) c.fillRect(X(prev), 0, X(sa) - X(prev), h);
      prev = Math.max(prev, sb);
    }
  }
  const mid = h / 2;
  if (S.peaks) {
    const bar = 2 * dpr, gap = 1 * dpr, n = Math.floor(w / (bar + gap));
    for (let i = 0; i < n; i++) {
      const t0 = a + (i / n) * (b - a), t1 = a + ((i + 1) / n) * (b - a);
      const p0 = Math.floor(t0 * S.peakRate), p1 = Math.max(p0 + 1, Math.floor(t1 * S.peakRate));
      let peak = 0;
      for (let k = p0; k < p1 && k < S.peaks.length; k++) if (S.peaks[k] > peak) peak = S.peaks[k];
      const amp = (peak / 255) * h * 0.4 + dpr;
      const tm = (t0 + t1) / 2;
      let color = 'rgba(123,138,169,0.42)';
      if (hasRange && tm >= S.inT && tm <= S.outT) {
        const piece = segs.find(([sa, sb]) => tm >= sa && tm <= sb);
        color = !piece ? 'rgba(255,77,109,0.55)' : piece[2] !== 1 ? '#a78bff' : '#00e5ff';
      }
      c.fillStyle = color;
      c.fillRect(i * (bar + gap), mid - amp, bar, amp * 2);
    }
  } else {
    c.fillStyle = 'rgba(123,138,169,0.25)';
    c.fillRect(0, mid - dpr / 2, w, dpr);
  }
  if (hasRange) {
    for (const [t, side] of [[S.inT, 1], [S.outT, -1]]) {
      const x = X(t);
      c.shadowColor = '#00e5ff';
      c.shadowBlur = 10 * dpr;
      c.fillStyle = '#00e5ff';
      c.fillRect(x - dpr, 0, 2 * dpr, h);
      c.shadowBlur = 0;
      c.beginPath();
      c.roundRect(side > 0 ? x : x - 10 * dpr, 0, 10 * dpr, 18 * dpr, 3 * dpr);
      c.fill();
    }
  }
  const px = X(video.currentTime || 0);
  c.shadowColor = '#ff2bd6';
  c.shadowBlur = 8 * dpr;
  c.fillStyle = '#ff2bd6';
  c.fillRect(px - dpr, 0, 2 * dpr, h);
  c.shadowBlur = 0;
  c.font = `${10 * dpr}px "Cascadia Mono"`;
  c.fillStyle = 'rgba(123,138,169,0.9)';
  c.textBaseline = 'bottom';
  c.textAlign = 'left';
  c.fillText(fmt(a), 6 * dpr, h - 4 * dpr);
  c.textAlign = 'right';
  c.fillText(fmt(b), w - 6 * dpr, h - 4 * dpr);
}

function snapTime(t, which) {
  const list = which === 'in' ? S.wordStarts : S.wordEnds;
  if (!list.length) return t;
  const i = lastAtOrBefore(list, t, (v) => v);
  let best = t, bestD = 0.25;
  for (const j of [i, i + 1]) {
    if (j < 0 || j >= list.length) continue;
    const target = which === 'in' ? list[j] - 0.05 : list[j] + 0.1;
    if (Math.abs(target - t) < bestD) { best = target; bestD = Math.abs(target - t); }
  }
  return best;
}

function stripHandleAt(clientX) {
  const rect = el.strip.getBoundingClientRect();
  const [a, b] = S.stripView;
  const near = (t) => t != null && Math.abs((t - a) / (b - a) * rect.width - (clientX - rect.left)) < 9;
  if (near(S.inT)) return 'in';
  if (near(S.outT)) return 'out';
  return 'seek';
}

el.strip.addEventListener('pointermove', (e) => {
  if (!S.dragWindow) el.strip.style.cursor = stripHandleAt(e.clientX) === 'seek' ? 'crosshair' : 'ew-resize';
});

el.strip.addEventListener('pointerdown', (e) => {
  if (!S.duration) return;
  const mode = stripHandleAt(e.clientX);
  const rect = el.strip.getBoundingClientRect();
  S.dragWindow = [...S.stripView];
  const [a, b] = S.dragWindow;
  el.strip.setPointerCapture(e.pointerId);
  const apply = (ev) => {
    let t = clamp(a + (ev.clientX - rect.left) / rect.width * (b - a), 0, S.duration);
    if (mode === 'seek') { seek(t); return; }
    if (!ev.altKey) t = snapTime(t, mode);
    if (mode === 'in') setRange(Math.min(t, S.outT - 0.3), S.outT);
    else setRange(S.inT, Math.max(t, S.inT + 0.3));
    seek(mode === 'in' ? S.inT : S.outT);
  };
  apply(e);
  const up = () => {
    el.strip.removeEventListener('pointermove', apply);
    el.strip.removeEventListener('pointerup', up);
    S.dragWindow = null;
  };
  el.strip.addEventListener('pointermove', apply);
  el.strip.addEventListener('pointerup', up);
});

function drawOverview() {
  const c = el.overview.getContext('2d');
  const { w, h, dpr } = fitCanvas(el.overview);
  c.clearRect(0, 0, w, h);
  if (!S.duration) return;
  const X = (t) => t / S.duration * w;
  c.fillStyle = 'rgba(130,170,255,0.07)';
  c.beginPath(); c.roundRect(0, 0, w, h, 4 * dpr); c.fill();
  if (S.peaks) {
    if (!S.ovBins || S.ovBins.length !== w) {
      S.ovBins = new Uint8Array(w);
      const per = S.peaks.length / w;
      for (let x = 0; x < w; x++) {
        let peak = 0;
        for (let k = Math.floor(x * per); k < Math.floor((x + 1) * per) || k === Math.floor(x * per); k++) {
          if (k < S.peaks.length && S.peaks[k] > peak) peak = S.peaks[k];
          if (k >= S.peaks.length) break;
        }
        S.ovBins[x] = peak;
      }
    }
    c.fillStyle = 'rgba(123,138,169,0.35)';
    for (let x = 0; x < w; x++) {
      const amp = S.ovBins[x] / 255 * (h - 4 * dpr);
      c.fillRect(x, (h - amp) / 2, 1, amp);
    }
  }
  c.fillStyle = 'rgba(139,92,255,0.7)';
  for (const clip of S.clips) c.fillRect(X(clip.start), 0, Math.max(2 * dpr, X(clip.end) - X(clip.start)), h);
  if (S.inT != null && S.outT != null) {
    c.fillStyle = 'rgba(0,229,255,0.55)';
    c.fillRect(X(S.inT), 0, Math.max(2 * dpr, X(S.outT) - X(S.inT)), h);
  }
  if (S.edit.intro) {
    c.fillStyle = '#ffb547';
    c.fillRect(X(S.edit.intro[0]), 0, Math.max(2 * dpr, X(S.edit.intro[1]) - X(S.edit.intro[0])), h);
  }
  const [a, b] = S.stripView;
  c.strokeStyle = 'rgba(232,241,255,0.4)';
  c.lineWidth = dpr;
  c.strokeRect(X(a) + dpr / 2, dpr / 2, Math.max(2, X(b) - X(a)) - dpr, h - dpr);
  c.fillStyle = '#ff2bd6';
  c.fillRect(X(video.currentTime || 0) - dpr, 0, 2 * dpr, h);
}

el.overview.addEventListener('pointerdown', (e) => {
  if (!S.duration) return;
  const rect = el.overview.getBoundingClientRect();
  const apply = (ev) => seek((ev.clientX - rect.left) / rect.width * S.duration);
  el.overview.setPointerCapture(e.pointerId);
  apply(e);
  const up = () => {
    el.overview.removeEventListener('pointermove', apply);
    el.overview.removeEventListener('pointerup', up);
  };
  el.overview.addEventListener('pointermove', apply);
  el.overview.addEventListener('pointerup', up);
});

/* ---------------------------------------------------------------- frame loop */

/* while playing inside the clip, jump over the parts that are cut out (and loop at the end) */
function skipCutParts(t) {
  if (video.paused || video.seeking || S.inT == null || S.outT == null || S.outT <= S.inT) return;
  const ed = editState();
  const { segs } = ed;
  if (!segs || !segs.length) return;
  if (S.inIntro) {  // teaser playing: when it ends, the clip starts from the beginning
    if (!ed.intro) { S.inIntro = false; return; }
    if (t >= ed.intro[1] - 0.02 || t < ed.intro[0] - 0.5) {
      S.inIntro = false;
      video.currentTime = segs[0][0];
    }
    return;
  }
  if (t < S.inT - 0.05) return;
  const lastEnd = segs[segs.length - 1][1];
  if (t >= lastEnd - 0.02) {
    if (S.loop) playFromClipStart(ed);
    else if (t >= S.outT) video.pause();
    return;
  }
  if (!segs.some(([a, b]) => t >= a - 0.03 && t < b)) {
    const next = segs.find(([a]) => a > t);
    if (next) video.currentTime = next[0];
  }
}

/* playback rules run on their own timer: the browser stops animation frames when the window is
   covered or hidden, but the video keeps playing and must still skip cuts / leave the teaser */
setInterval(() => {
  const t = video.currentTime || 0;
  skipCutParts(t);
  muteTick(t);
}, 30);

/* ---------------------------------------------------------------- muted-word sounds (preview) */

let audioCtx = null, toneOsc = null, toneGain = null;
const sfxBuffers = new Map();

function audio() {
  if (!audioCtx) {
    audioCtx = new AudioContext();
    toneOsc = audioCtx.createOscillator();
    toneGain = audioCtx.createGain();
    toneGain.gain.value = 0;
    toneOsc.connect(toneGain).connect(audioCtx.destination);
    toneOsc.start();
  }
  if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
  return audioCtx;
}

function soundUrl() {
  const key = S.edit.muteSound;
  if (key === 'custom') return S.edit.muteSfx ? `/media/music?path=${encodeURIComponent(S.edit.muteSfx)}` : null;
  return `/media/sfx/${key}.wav`;
}

async function sfxBuffer(url) {
  if (!sfxBuffers.has(url)) {
    sfxBuffers.set(url, fetch(url).then((r) => r.arrayBuffer()).then((data) => audio().decodeAudioData(data))
      .catch(() => { sfxBuffers.delete(url); return null; }));
  }
  return sfxBuffers.get(url);
}

/* play the chosen sound once (tile click, or a muted word starting during playback) */
async function playMuteSound(toneSeconds = 0.6, tile = null) {
  const sound = S.muteSounds?.[S.edit.muteSound];
  if (!sound || sound.kind === 'none') return;
  const ctx = audio();
  const level = S.edit.muteSfxVolume;
  if (tile) { tile.classList.add('playing'); setTimeout(() => tile.classList.remove('playing'), 600); }
  if (sound.kind === 'tone') {
    toneOsc.frequency.value = sound.freq;
    toneGain.gain.setTargetAtTime(0.12 * level, ctx.currentTime, 0.005);
    toneGain.gain.setTargetAtTime(0, ctx.currentTime + toneSeconds, 0.005);
    return;
  }
  const url = soundUrl();
  const buffer = url && await sfxBuffer(url);
  if (!buffer) return;
  const src = ctx.createBufferSource();
  const gain = ctx.createGain();
  gain.gain.value = 0.6 * level;
  src.buffer = buffer;
  src.connect(gain).connect(ctx.destination);
  src.start();
}

/* during playback: silence the muted words and play their sound – the tone for as long as the
   word lasts, a one-shot effect once where each muted part starts (same as the render) */
function muteTick(t) {
  const look = t + 0.04;  // react a moment early so the start of the word doesn't slip through
  const inClip = S.inT != null && (S.inIntro || (t >= S.inT - 0.05 && t <= S.outT + 0.05));
  const idx = !video.paused && inClip ? S.mutes.findIndex(([a, b]) => look >= a && t <= b) : -1;
  const hit = idx >= 0;
  if (video.muted !== hit) video.muted = hit;
  const sound = S.muteSounds?.[S.edit.muteSound];
  if (sound?.kind === 'tone' && (hit || toneGain)) {
    audio();
    toneOsc.frequency.value = sound.freq;
    toneGain.gain.setTargetAtTime(hit ? 0.12 * S.edit.muteSfxVolume : 0, audioCtx.currentTime, 0.005);
  } else if (toneGain) {
    toneGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.005);
  }
  const key = `${idx}|${S.inIntro}`;
  if (hit && sound?.kind === 'hit' && S.muteHit !== key) playMuteSound();
  S.muteHit = hit ? key : -1;
}

function tick() {
  const t = video.currentTime || 0;
  const now = fmt(t);
  if (el.tcNow.textContent !== now) {
    el.tcNow.textContent = now;
    el.hudTime.textContent = `T+ ${now}`;
  }
  const mode = `${S.layout === 'fit' ? 'FIT' : 'CROP'} · ${Math.round(S.frameZoom * 100)}%`;
  if (el.hudMode.textContent !== mode) el.hudMode.textContent = mode;

  if (S.lines.length) {
    const idx = lastAtOrBefore(S.lines, t + 0.05, (l) => l.s);
    if (idx !== S.liveLine) {
      const nodes = lineNodes();
      nodes[S.liveLine]?.classList.remove('live');
      nodes[idx]?.classList.add('live');
      S.liveLine = idx;
      if (idx >= 0 && el.follow.checked && !video.paused) {
        const box = el.lines.getBoundingClientRect(), r = nodes[idx].getBoundingClientRect();
        if (r.top < box.top + 40 || r.bottom > box.bottom - 40) nodes[idx].scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    }
  }
}

function frame() {
  drawPreview();
  drawStrip();
  drawOverview();
  tick();
  requestAnimationFrame(frame);
}

/* ---------------------------------------------------------------- keyboard + window */

document.addEventListener('keydown', (e) => {
  if (!el.player.hidden) { if (e.key === 'Escape') closePlayer(); return; }
  const tag = e.target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) {
    if (e.key === 'Escape' && !e.target.isContentEditable) e.target.blur();
    return;
  }
  if (!S.videoKey) return;
  const t = video.currentTime;
  switch (e.key) {
    case 'x': case 'X': setCutMode(!S.cutMode); break;
    case 'm': case 'M': setMuteMode(!S.muteMode); break;
    case ' ': e.preventDefault(); togglePlay(); break;
    case 'i': case 'I': setIn(); break;
    case 'o': case 'O': setOut(); break;
    case 'j': case 'J': seek(t - 5); break;
    case 'l': case 'L': seek(t + 5); break;
    case 'k': case 'K': video.pause(); break;
    case 'ArrowLeft': e.preventDefault(); seek(t - (e.shiftKey ? 0.1 : 1)); break;
    case 'ArrowRight': e.preventDefault(); seek(t + (e.shiftKey ? 0.1 : 1)); break;
    case 'Enter': e.preventDefault(); addClip(e.shiftKey); break;
    case '/': e.preventDefault(); el.search.focus(); break;
    default:
  }
});

$('#btn-open').onclick = () => openVideo();
$('#btn-open-hero').onclick = () => openVideo();

window.addEventListener('dragover', (e) => e.preventDefault());
window.addEventListener('drop', (e) => {
  e.preventDefault();
  toast('Use the Open button to pick the video file.', 'info');
});
window.addEventListener('pagehide', () => navigator.sendBeacon('/api/bye', ''));

setCrop(0.5);
setLayout('crop');
editChanged();
renderCards();
loadStyles();
poll();
requestAnimationFrame(frame);
