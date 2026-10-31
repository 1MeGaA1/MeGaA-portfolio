/* =====================================================
   OZONE STUDIOS — ADMIN
   Real-time Firestore CRUD for beats, bookings, offers
   ===================================================== */

(function () {
  "use strict";

  const ADMIN_EMAIL = "admin@example.com";

  // ---------- IN-MEMORY STATE (kept fresh by Firestore listeners) ----------
  let beats    = [];
  let bookings = [];
  let offers   = [];
  let users    = [];

  function uid(prefix) {
    return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }
  function escapeHtml(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }
  function fmtDate(value) {
    if (!value) return "—";
    if (value && typeof value.toDate === "function") value = value.toDate();
    const d = new Date(value);
    if (isNaN(d)) return String(value);
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }
  function fmtFullDate(value) {
    if (!value) return "—";
    if (value && typeof value.toDate === "function") value = value.toDate();
    const d = new Date(value);
    if (isNaN(d)) return String(value);
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  }
  // 12-hour AM/PM formatter — "May 12, 5:30 PM"
  function fmtSubmittedAt(value) {
    if (!value) return "—";
    if (value && typeof value.toDate === "function") value = value.toDate();
    const d = new Date(value);
    if (isNaN(d)) return String(value);
    const date = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", hour12: true });
    return date + ", " + time;
  }
  function toMillis(value) {
    if (!value) return 0;
    if (value && typeof value.toMillis === "function") return value.toMillis();
    return new Date(value).getTime() || 0;
  }

  // ---------- SLOT LABELS (mirror of public site) ----------
  const SLOT_LABELS = {
    "15:00-17:00": "3PM — 5PM",
    "17:00-19:00": "5PM — 7PM",
    "19:00-21:00": "7PM — 9PM",
    "21:00-23:00": "9PM — 11PM"
  };
  function fmtTime12(hhmm) {
    const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm || "");
    if (!m) return hhmm || "";
    const h = parseInt(m[1], 10);
    const mins = m[2];
    const period = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return h12 + (mins !== "00" ? ":" + mins : "") + period;
  }
  function slotLabel(slot) {
    if (!slot) return "";
    if (SLOT_LABELS[slot]) return SLOT_LABELS[slot];
    const parts = slot.split("-");
    if (parts.length !== 2) return slot;
    return fmtTime12(parts[0]) + " — " + fmtTime12(parts[1]);
  }

  // ---------- WHATSAPP HELPERS ----------
  function normalisePhone(raw) {
    if (!raw) return null;
    let d = String(raw).replace(/\D/g, "");
    if (!d) return null;
    // Egyptian local form 010..., 011..., 012..., 015... → prepend 20 after dropping leading 0
    if (d.startsWith("0") && (d.length === 11 || d.length === 10)) d = "20" + d.slice(1);
    // Already E.164-ish without +
    if (d.length < 8 || d.length > 15) return null;
    return d;
  }
  function waLink(phone, message) {
    const num = normalisePhone(phone);
    if (!num) return null;
    return "https://wa.me/" + num + "?text=" + encodeURIComponent(message);
  }
  function bookingWaMessage(b) {
    const first = (b.name || "").split(" ")[0] || "there";
    const studio = b.studio ? `Studio ${b.studio}` : "";
    const dateStr = b.date ? fmtFullDate(b.date) : "";
    const slot = slotLabel(b.time);
    const status = (b.status || "PENDING");
    const verb = status === "CONFIRMED" ? "confirmed" :
                 status === "DONE"      ? "wrapped" :
                 status === "CANCELLED" ? "cancelled" :
                                          "received";
    const bits = [studio, dateStr, slot].filter(Boolean).join(" · ");
    if (b.type === "service") {
      return `Hi ${first}, your ${b.service || "service"} request at Ozone Studios is *${verb}*. We'll be in touch shortly with next steps.`;
    }
    return `Hi ${first}, your session at Ozone Studios is *${verb}*${bits ? " for " + bits : ""}. See you then.`;
  }

  // ---------- BEAT ICONS (mirror of public script) ----------
  const ICONS = {
    moon:    '<path d="M20 14a8 8 0 1 1-9-9 6 6 0 0 0 9 9z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
    keys:    '<rect x="4" y="7" width="16" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/><line x1="8" y1="7" x2="8" y2="18" stroke="currentColor" stroke-width="1.2"/><line x1="12" y1="7" x2="12" y2="18" stroke="currentColor" stroke-width="1.2"/><line x1="16" y1="7" x2="16" y2="18" stroke="currentColor" stroke-width="1.2"/>',
    flame:   '<path d="M12 3c1 3 4 4 4 8a4 4 0 0 1-8 0c0-2 1-3 1-5 1 1 2 1 2 0 0-1 .5-2 1-3z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
    spark:   '<path d="M12 3v6M12 15v6M3 12h6M15 12h6M5.6 5.6l3 3M15.4 15.4l3 3M18.4 5.6l-3 3M8.6 15.4l-3 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
    wave:    '<path d="M3 14c2 0 2-4 4-4s2 4 4 4 2-4 4-4 2 4 4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
    diamond: '<path d="M12 3l4 5-4 13-4-13z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M4 8h16" stroke="currentColor" stroke-width="1.4"/>'
  };
  function iconSvg(name) {
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.wave}</svg>`;
  }

  // Trash / WA / Edit SVG snippets
  const TRASH_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-7 0v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  const EDIT_SVG  = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21l4-1 12-12-3-3L4 17l-1 4z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const WA_SVG    = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M19.07 4.93A9.94 9.94 0 0 0 12 2a9.96 9.96 0 0 0-8.43 15.35L2 22l4.78-1.52A9.96 9.96 0 0 0 22 12a9.94 9.94 0 0 0-2.93-7.07ZM12 20a7.96 7.96 0 0 1-4.07-1.11l-.29-.17-2.84.9.91-2.77-.19-.3A7.96 7.96 0 1 1 20 12a7.97 7.97 0 0 1-8 8Zm4.4-5.97c-.24-.12-1.4-.69-1.62-.77-.22-.08-.38-.12-.54.12-.16.24-.62.77-.76.93-.14.16-.28.18-.52.06-.24-.12-1-.37-1.92-1.18-.71-.63-1.19-1.41-1.33-1.65-.14-.24-.02-.37.1-.49.11-.1.24-.28.36-.42.12-.14.16-.24.24-.4.08-.16.04-.3-.02-.42-.06-.12-.54-1.3-.74-1.78-.2-.47-.4-.4-.54-.41-.14-.01-.3-.01-.46-.01-.16 0-.42.06-.64.3-.22.24-.84.82-.84 2 0 1.18.86 2.32.98 2.48.12.16 1.7 2.6 4.12 3.55.58.25 1.03.4 1.38.51.58.18 1.1.16 1.52.1.46-.07 1.4-.57 1.6-1.12.2-.55.2-1.02.14-1.12-.06-.1-.22-.16-.46-.28Z"/></svg>';

  // ---------- ROUTER ----------
  const ROUTES = ["dashboard", "bookings", "offers", "beats", "clients"];
  const TITLES = {
    dashboard: "Dashboard",
    bookings:  "Bookings",
    offers:    "Offers & Deals",
    beats:     "Songs & Beats",
    clients:   "Clients"
  };
  const navLinks  = document.querySelectorAll("#adminNav a");
  const panels    = document.querySelectorAll(".admin-panel");
  const titleEl   = document.getElementById("adminPageTitle");
  let currentRoute = "dashboard";

  function route() {
    const hash = (location.hash || "#dashboard").slice(1);
    const r = ROUTES.includes(hash) ? hash : "dashboard";
    currentRoute = r;
    panels.forEach((p) => { p.hidden = p.dataset.panel !== r; });
    navLinks.forEach((a) => a.classList.toggle("is-active", a.dataset.route === r));
    titleEl.textContent = TITLES[r];
    if (r === "dashboard") renderDashboard();
    if (r === "bookings")  renderBookings();
    if (r === "offers")    renderOffers();
    if (r === "beats")     renderBeats();
    if (r === "clients")   renderClients();
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);

  // ---------- ICON PICKER (fill chip thumbnails) ----------
  document.querySelectorAll("#iconPicker .icon-chip").forEach((chip) => {
    chip.innerHTML = iconSvg(chip.dataset.icon);
  });

  // ---------- AUTH GATE ----------
  function whenFirebaseReady(cb) {
    if (window.ozFB && window.ozFB.ready) { cb(); return; }
    window.addEventListener("oz-firebase-ready", cb, { once: true });
  }

  const gateEl      = document.getElementById("adminGate");
  const shellEl     = document.getElementById("adminShell");
  const loginForm   = document.getElementById("adminLoginForm");
  const loginStatus = document.getElementById("adminLoginStatus");
  const sideUser    = document.getElementById("adminSideUser");
  const signOutBtn  = document.getElementById("adminSignOut");

  let listenersAttached = false;
  let unsubBookings = null;
  let unsubBeats = null;
  let unsubOffers = null;
  let unsubUsers = null;

  function showGate() {
    console.log("[ozone-admin] showGate()");
    gateEl.hidden = false;
    shellEl.hidden = true;
  }
  function showShell(user) {
    console.log("[ozone-admin] showShell() for", user && user.email);
    gateEl.hidden = true;
    shellEl.hidden = false;
    sideUser.hidden = false;
    sideUser.textContent = user.email;
  }
  function attachListeners() {
    if (listenersAttached) return;
    listenersAttached = true;
    unsubBookings = window.ozFB.watchBookings((rows) => {
      bookings = rows;
      if (currentRoute === "dashboard") renderDashboard();
      if (currentRoute === "bookings")  renderBookings();
      if (currentRoute === "clients")   renderClients();
      updatePendingBadge();
    });
    unsubBeats = window.ozFB.watchBeats((rows) => {
      beats = rows;
      if (currentRoute === "dashboard") renderDashboard();
      if (currentRoute === "beats")     renderBeats();
    });
    unsubOffers = window.ozFB.watchOffers((rows) => {
      offers = rows;
      if (currentRoute === "dashboard") renderDashboard();
      if (currentRoute === "offers")    renderOffers();
    });
    if (window.ozFB.watchUsers) {
      unsubUsers = window.ozFB.watchUsers((rows) => {
        users = rows;
        if (currentRoute === "clients") renderClients();
      });
    }
  }
  function detachListeners() {
    if (unsubBookings) unsubBookings();
    if (unsubBeats) unsubBeats();
    if (unsubOffers) unsubOffers();
    if (unsubUsers) unsubUsers();
    listenersAttached = false;
    bookings = []; beats = []; offers = []; users = [];
  }

  whenFirebaseReady(() => {
    window.ozFB.onAuth((user) => {
      console.log("[ozone-admin] onAuth fired:", user ? user.email : "(no user)");
      const ok = user && user.email && user.email.toLowerCase() === ADMIN_EMAIL.toLowerCase();
      if (ok) {
        showShell(user);
        attachListeners();
        route();
      } else {
        // Hide admin UI without signing the user out — they may legitimately be
        // signed in as a customer on the public site in another tab. The login
        // form's own submit handler shows the "not authorized" error when an
        // actual sign-in attempt uses the wrong email.
        detachListeners();
        showGate();
      }
    });
  });

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(loginForm).entries());
    if (!data.email || !data.password) {
      loginStatus.textContent = "ENTER EMAIL AND PASSWORD";
      loginStatus.className = "form-status error";
      return;
    }
    if (data.email.trim().toLowerCase() !== ADMIN_EMAIL.toLowerCase()) {
      loginStatus.textContent = "THIS ACCOUNT IS NOT AUTHORIZED";
      loginStatus.className = "form-status error";
      return;
    }
    loginStatus.textContent = "SIGNING IN...";
    loginStatus.className = "form-status";
    try {
      await window.ozFB.signIn(data.email.trim(), data.password);
      loginStatus.textContent = "";
      loginForm.reset();
    } catch (err) {
      console.error("[ozone-admin] sign-in error:", err);
      const code = err && err.code ? err.code : "";
      let msg;
      switch (code) {
        case "auth/invalid-credential":
        case "auth/wrong-password":
        case "auth/user-not-found":
          msg = "WRONG EMAIL OR PASSWORD";
          break;
        case "auth/too-many-requests":
          msg = "TOO MANY ATTEMPTS — TRY AGAIN IN A MOMENT";
          break;
        case "auth/network-request-failed":
          msg = "NETWORK ERROR — CHECK YOUR CONNECTION";
          break;
        case "auth/operation-not-allowed":
          msg = "EMAIL SIGN-IN IS DISABLED IN FIREBASE — ENABLE IT IN CONSOLE";
          break;
        case "auth/user-disabled":
          msg = "THIS USER IS DISABLED";
          break;
        case "auth/invalid-email":
          msg = "EMAIL FORMAT INVALID";
          break;
        default:
          msg = "SIGN-IN FAILED — " + (code || (err && err.message) || "UNKNOWN ERROR");
      }
      loginStatus.textContent = msg;
      loginStatus.className = "form-status error";
    }
  });

  signOutBtn.addEventListener("click", async () => {
    try { await window.ozFB.signOut(); }
    catch (err) { alert("Sign-out failed: " + err.message); }
  });

  // ---------- BADGE ----------
  function updatePendingBadge() {
    const badge = document.getElementById("navBookingsBadge");
    if (!badge) return;
    const pending = bookings.filter((b) => (b.status || "PENDING") === "PENDING").length;
    if (pending > 0) {
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
  }

  // ---------- DASHBOARD ----------
  function renderDashboard() {
    const pending = bookings.filter((b) => (b.status || "PENDING") === "PENDING");
    const nowEl = document.getElementById("nowPending");
    const nounEl = document.getElementById("nowPendingNoun");
    const nextEl = document.getElementById("nowNext");
    nowEl.textContent = pending.length;
    nounEl.textContent = pending.length === 1 ? "booking" : "bookings";

    // Earliest pending: sort by date+time ascending, fall back to createdAt
    if (pending.length === 0) {
      nextEl.textContent = "All caught up.";
    } else {
      const sorted = [...pending].sort((a, b) => {
        const da = new Date(`${a.date || "9999-12-31"}T${(a.time || "00:00-00:00").split("-")[0]}:00`).getTime();
        const db = new Date(`${b.date || "9999-12-31"}T${(b.time || "00:00-00:00").split("-")[0]}:00`).getTime();
        return da - db;
      });
      const next = sorted[0];
      const bits = [next.studio ? "Studio " + next.studio : null, fmtFullDate(next.date), slotLabel(next.time), next.name].filter(Boolean);
      nextEl.textContent = "Next up: " + bits.join(" · ");
    }

    document.getElementById("statBookings").textContent =
      bookings.filter((b) => (b.status || "PENDING") !== "CANCELLED").length;
    document.getElementById("statOffers").textContent   = offers.filter((o) => o.active !== false).length;
    document.getElementById("statBeats").textContent    = beats.length;
    document.getElementById("statClients").textContent  = uniqueClients().length;

    const body = document.getElementById("dashBookingsBody");
    const empty = document.getElementById("dashBookingsEmpty");
    const recent = bookings.slice(0, 5);
    body.innerHTML = recent.map(rowBookingDash).join("");
    empty.hidden = recent.length !== 0;
  }
  function rowBookingDash(b) {
    const status = b.status || "PENDING";
    return `
      <article class="admin-row booking-row-compact">
        <div class="br-client">
          <span class="br-name">${escapeHtml(b.name)}</span>
          <span class="br-tags">
            ${b.type === "service" ? '<span class="br-tag is-service">SERVICE</span>' : '<span class="br-tag">SESSION</span>'}
            ${b.studio ? `<span class="br-tag">Studio ${escapeHtml(b.studio)}</span>` : ""}
          </span>
        </div>
        <div class="br-service">${escapeHtml(b.service || "—")}</div>
        <div class="br-when">
          <span class="br-when-date">${fmtFullDate(b.date)}</span>
          ${b.time ? `<span>${escapeHtml(slotLabel(b.time))}</span>` : ""}
        </div>
        <div>
          <span class="status-pill is-active${status === "CANCELLED" ? " is-cancelled" : ""}">${status.replace("_", " ")}</span>
        </div>
      </article>
    `;
  }

  // Quick add beat form
  const quickBeatForm = document.getElementById("quickBeatForm");
  if (quickBeatForm) {
    quickBeatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const status = document.getElementById("quickBeatStatus");
      const data = Object.fromEntries(new FormData(e.target).entries());
      if (!data.name || !data.bpm || !data.price) {
        status.textContent = "PLEASE FILL ALL FIELDS";
        status.className = "form-status error";
        return;
      }
      try {
        await window.ozFB.addBeat({
          name: data.name.trim(),
          genre: data.genre,
          bpm: Number(data.bpm),
          price: Number(data.price),
          license: data.license,
          icon: "wave"
        });
        status.textContent = "ADDED — VISIBLE ON THE BEAT STORE";
        status.className = "form-status ok";
        e.target.reset();
      } catch (err) {
        status.textContent = "COULDN'T SAVE — " + (err.message || "TRY AGAIN");
        status.className = "form-status error";
      }
      setTimeout(() => { status.textContent = ""; status.className = "form-status"; }, 3500);
    });
  }

  // ---------- BOOKINGS ----------
  let bookingFilter = "ALL";
  let bookingDateFilter = "ALL";

  document.querySelectorAll("#bookingFilters .filter-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#bookingFilters .filter-pill").forEach((b) =>
        b.classList.toggle("is-active", b === btn)
      );
      bookingFilter = btn.dataset.status;
      renderBookings();
    });
  });
  document.querySelectorAll("#bookingDateFilters .filter-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#bookingDateFilters .filter-pill").forEach((b) =>
        b.classList.toggle("is-active", b === btn)
      );
      bookingDateFilter = btn.dataset.range;
      renderBookings();
    });
  });

  // Returns true if a "YYYY-MM-DD" session date falls within the named range.
  function dateInRange(dateStr, range) {
    if (range === "ALL" || !dateStr) return range === "ALL";
    const parts = dateStr.split("-").map(Number);
    if (parts.length !== 3) return false;
    const d = new Date(parts[0], parts[1] - 1, parts[2]); // local midnight
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const oneDay = 86400000;
    if (range === "TODAY")     return d.getTime() === today.getTime();
    if (range === "YESTERDAY") return d.getTime() === today.getTime() - oneDay;
    if (range === "UPCOMING")  return d.getTime() >= today.getTime();
    if (range === "WEEK") {
      // Calendar week starting Sunday — common in Egypt
      const dow = today.getDay();
      const weekStart = today.getTime() - dow * oneDay;
      const weekEnd = weekStart + 6 * oneDay;
      return d.getTime() >= weekStart && d.getTime() <= weekEnd;
    }
    if (range === "MONTH") {
      return d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth();
    }
    return true;
  }

  function renderBookings() {
    const body  = document.getElementById("bookingsBody");
    const empty = document.getElementById("bookingsEmpty");
    const filtered = bookings.filter((b) => {
      const statusOk = bookingFilter === "ALL" ? true : (b.status || "PENDING") === bookingFilter;
      const dateOk   = dateInRange(b.date, bookingDateFilter);
      return statusOk && dateOk;
    });
    body.innerHTML = filtered.map(rowBooking).join("");
    empty.hidden = filtered.length !== 0;
  }

  const STATUSES = ["PENDING", "CONFIRMED", "IN_PROGRESS", "DONE", "CANCELLED"];

  function rowBooking(b) {
    const status = b.status || "PENDING";
    const slot = slotLabel(b.time);
    const phone = b.phone || "";
    const email = b.email || "";
    const tags = [];
    tags.push(b.type === "service"
      ? '<span class="br-tag is-service">SERVICE</span>'
      : '<span class="br-tag">SESSION</span>');
    if (b.studio) tags.push(`<span class="br-tag">Studio ${escapeHtml(b.studio)}</span>`);
    if (b.tier && b.type === "service") tags.push(`<span class="br-tag">${escapeHtml(b.tier)}</span>`);

    const notes = b.notes ? `<div class="br-notes">${escapeHtml(b.notes)}</div>` : "";
    const linkRow = b.link
      ? `<div class="br-link"><a href="${escapeHtml(b.link)}" target="_blank" rel="noopener noreferrer">🔗 Open files link</a></div>`
      : "";
    const submittedRow = b.createdAt
      ? `<div class="br-submitted">Submitted ${escapeHtml(fmtSubmittedAt(b.createdAt))}</div>`
      : "";

    const railPills = STATUSES.map((s) => {
      const active = s === status;
      const cls = ["status-pill"];
      if (active) cls.push("is-active");
      if (active && s === "CANCELLED") cls.push("is-cancelled");
      return `<button type="button" class="${cls.join(" ")}" data-action="status" data-id="${b.id}" data-value="${s}">${s.replace("_", " ")}</button>`;
    }).join("");

    const phoneNorm = normalisePhone(phone);
    const waUrl = phoneNorm ? waLink(phoneNorm, bookingWaMessage(b)) : null;

    return `
      <article class="admin-row booking-row" data-id="${b.id}">
        <div class="br-client">
          <span class="br-name">${escapeHtml(b.name)}</span>
          <span class="br-tags">${tags.join("")}</span>
          ${submittedRow}
          ${notes}
          ${linkRow}
        </div>
        <div class="br-contact">
          ${email ? `<a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>` : ""}
          ${phone ? `<a href="tel:${escapeHtml(phone)}">${escapeHtml(phone)}</a>` : ""}
        </div>
        <div class="br-service">${escapeHtml(b.service || "—")}</div>
        <div class="br-when">
          <span class="br-when-date">${fmtFullDate(b.date)}</span>
          ${slot ? `<span>${escapeHtml(slot)}</span>` : ""}
        </div>
        <div class="status-rail">${railPills}</div>
        <div class="row-actions">
          ${waUrl
            ? `<a class="wa-btn" href="${waUrl}" target="_blank" rel="noopener noreferrer" aria-label="Reply on WhatsApp">${WA_SVG}</a>`
            : `<button class="wa-btn" type="button" disabled aria-label="No phone number on file">${WA_SVG}</button>`}
          <button class="icon-btn danger" data-action="delete-booking" data-id="${b.id}" aria-label="Delete">${TRASH_SVG}</button>
        </div>
      </article>
    `;
  }

  function canReserveSlot(b) {
    return !!(b && b.type === "session" && b.studio && b.date && b.time);
  }

  document.getElementById("bookingsBody").addEventListener("click", async (e) => {
    const statusBtn = e.target.closest('[data-action="status"]');
    if (statusBtn) {
      const id = statusBtn.dataset.id;
      const value = statusBtn.dataset.value;
      const booking = bookings.find((b) => b.id === id);
      const prevStatus = booking ? (booking.status || "PENDING") : null;
      try {
        await window.ozFB.updateBookingStatus(id, value);
        if (canReserveSlot(booking)) {
          if (value === "CONFIRMED" && prevStatus !== "CONFIRMED") {
            console.log("[ozone-admin] reserving slot for", booking.studio, booking.date, booking.time);
            try {
              await window.ozFB.setSlotReservation({
                studio: booking.studio,
                date: booking.date,
                time: booking.time,
                bookingId: id,
                customerName: booking.name || ""
              });
              console.log("[ozone-admin] slot reserved successfully");
            } catch (slotErr) {
              console.error("[ozone-admin] setSlotReservation FAILED:", slotErr);
              alert("Status changed but slot reservation failed:\n" + (slotErr.message || slotErr) + "\n\nMost common cause: Firestore rules don't allow slotReservations writes yet. Republish the rules.");
            }
          } else if (prevStatus === "CONFIRMED" && value !== "CONFIRMED") {
            console.log("[ozone-admin] releasing slot for", booking.studio, booking.date, booking.time);
            try {
              await window.ozFB.clearSlotReservation(booking.studio, booking.date, booking.time);
              console.log("[ozone-admin] slot released successfully");
            } catch (slotErr) {
              console.error("[ozone-admin] clearSlotReservation FAILED:", slotErr);
            }
          }
        }
      } catch (err) {
        alert("Failed to update status: " + err.message);
      }
      return;
    }
    const del = e.target.closest('[data-action="delete-booking"]');
    if (del) {
      const id = del.dataset.id;
      const booking = bookings.find((b) => b.id === id);
      if (!confirm("Delete this booking?")) return;
      try {
        await window.ozFB.deleteBooking(id);
        // If we deleted a confirmed session, release its slot too
        if (canReserveSlot(booking) && (booking.status || "PENDING") === "CONFIRMED") {
          await window.ozFB.clearSlotReservation(booking.studio, booking.date, booking.time);
        }
      } catch (err) {
        alert("Failed to delete: " + err.message);
      }
    }
  });

  // ---------- OFFERS ----------
  function renderOffers() {
    const grid = document.getElementById("offersGrid");
    const empty = document.getElementById("offersEmpty");
    grid.innerHTML = offers.map(cardOffer).join("");
    empty.hidden = offers.length !== 0;
  }
  function cardOffer(o) {
    const active = o.active !== false;
    const expires = o.validUntil ? `Until ${fmtDate(o.validUntil)}` : "No expiry";
    return `
      <article class="offer-card${active ? "" : " is-inactive"}" data-id="${o.id}">
        <p class="offer-discount">${escapeHtml(o.discount || "—")}</p>
        <h4 class="offer-title">${escapeHtml(o.title || "")}</h4>
        <p class="offer-desc">${escapeHtml(o.description || "")}</p>
        <div class="offer-foot">
          <span>${expires}</span>
          <div class="offer-foot-actions">
            <button class="toggle-pill ${active ? "on" : "off"}" data-action="toggle-offer" data-id="${o.id}" type="button">${active ? "ACTIVE" : "OFF"}</button>
            <button class="icon-btn" data-action="edit-offer" data-id="${o.id}" aria-label="Edit">${EDIT_SVG}</button>
            <button class="icon-btn danger" data-action="delete-offer" data-id="${o.id}" aria-label="Delete">${TRASH_SVG}</button>
          </div>
        </div>
      </article>
    `;
  }
  document.getElementById("offersGrid").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-action]");
    if (!t) return;
    const id = t.dataset.id;
    const action = t.dataset.action;
    const o = offers.find((x) => x.id === id);
    if (!o) return;
    try {
      if (action === "toggle-offer") {
        await window.ozFB.updateOffer(id, { active: o.active === false });
      } else if (action === "delete-offer") {
        if (!confirm("Delete this offer?")) return;
        await window.ozFB.deleteOffer(id);
      } else if (action === "edit-offer") {
        const f = document.getElementById("offerForm");
        f.entityId.value = o.id;
        f.title.value = o.title || "";
        f.description.value = o.description || "";
        f.discount.value = o.discount || "";
        f.validUntil.value = o.validUntil || "";
        document.getElementById("offerFormTitle").textContent = "Edit Offer";
        document.getElementById("offerFormSubmit").textContent = "SAVE CHANGES";
        document.getElementById("offerFormReset").hidden = false;
        f.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (err) {
      alert("Action failed: " + err.message);
    }
  });

  document.getElementById("offerForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const status = document.getElementById("offerStatus");
    const data = Object.fromEntries(new FormData(f).entries());
    if (!data.title) {
      status.textContent = "TITLE IS REQUIRED";
      status.className = "form-status error";
      return;
    }
    try {
      if (data.entityId) {
        await window.ozFB.updateOffer(data.entityId, {
          title: data.title, description: data.description, discount: data.discount, validUntil: data.validUntil
        });
        status.textContent = "OFFER UPDATED";
      } else {
        await window.ozFB.addOffer({
          title: data.title, description: data.description, discount: data.discount, validUntil: data.validUntil, active: true
        });
        status.textContent = "OFFER ADDED";
      }
      status.className = "form-status ok";
      resetOfferForm();
    } catch (err) {
      status.textContent = "FAILED — " + (err.message || "TRY AGAIN");
      status.className = "form-status error";
    }
    setTimeout(() => { status.textContent = ""; status.className = "form-status"; }, 3500);
  });
  document.getElementById("offerFormReset").addEventListener("click", resetOfferForm);
  function resetOfferForm() {
    const f = document.getElementById("offerForm");
    f.reset();
    f.entityId.value = "";
    document.getElementById("offerFormTitle").textContent = "Create Offer";
    document.getElementById("offerFormSubmit").textContent = "+ ADD OFFER";
    document.getElementById("offerFormReset").hidden = true;
  }

  // ---------- BEATS ----------
  function renderBeats() {
    const body  = document.getElementById("beatsBody");
    const empty = document.getElementById("beatsEmpty");
    const count = document.getElementById("beatCount");
    body.innerHTML = beats.map(rowBeat).join("");
    empty.hidden = beats.length !== 0;
    count.textContent = `${beats.length} beat${beats.length === 1 ? "" : "s"}`;
  }
  function rowBeat(b) {
    return `
      <article class="admin-row beat-row-admin" data-id="${b.id}">
        <div class="beat-thumb-mini">${iconSvg(b.icon)}</div>
        <div class="br-name">${escapeHtml(b.name)}</div>
        <div class="beat-genre-cell">${escapeHtml(b.genre)}</div>
        <div class="beat-bpm-cell">${b.bpm} BPM</div>
        <div class="beat-price-cell">
          <span class="beat-price-amount">${b.price} EGP</span>
          <span class="beat-price-license">${escapeHtml(b.license || "")}</span>
        </div>
        <div class="row-actions">
          <button class="icon-btn" data-action="edit-beat" data-id="${b.id}" aria-label="Edit">${EDIT_SVG}</button>
          <button class="icon-btn danger" data-action="delete-beat" data-id="${b.id}" aria-label="Delete">${TRASH_SVG}</button>
        </div>
      </article>
    `;
  }

  document.getElementById("beatsBody").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-action]");
    if (!t) return;
    const id = t.dataset.id;
    if (t.dataset.action === "delete-beat") {
      if (!confirm("Remove this beat from the store?")) return;
      try { await window.ozFB.deleteBeat(id); }
      catch (err) { alert("Failed to delete: " + err.message); }
    } else if (t.dataset.action === "edit-beat") {
      const b = beats.find((x) => x.id === id);
      if (!b) return;
      const f = document.getElementById("beatForm");
      f.entityId.value = b.id;
      f.name.value = b.name;
      f.genre.value = b.genre;
      f.bpm.value = b.bpm;
      f.price.value = b.price;
      f.license.value = b.license;
      const radio = f.querySelector(`input[name="icon"][value="${b.icon}"]`);
      if (radio) radio.checked = true;
      document.getElementById("beatFormTitle").textContent = "Edit Beat";
      document.getElementById("beatFormSubmit").textContent = "SAVE CHANGES";
      document.getElementById("beatFormReset").hidden = false;
      f.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  document.getElementById("beatForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const status = document.getElementById("beatStatus");
    const data = Object.fromEntries(new FormData(f).entries());
    if (!data.name || !data.bpm || !data.price) {
      status.textContent = "PLEASE FILL ALL REQUIRED FIELDS";
      status.className = "form-status error";
      return;
    }
    const payload = {
      name: data.name.trim(),
      genre: data.genre,
      bpm: Number(data.bpm),
      price: Number(data.price),
      license: data.license,
      icon: data.icon || "wave"
    };
    try {
      if (data.entityId) {
        await window.ozFB.updateBeat(data.entityId, payload);
        status.textContent = "BEAT UPDATED";
      } else {
        await window.ozFB.addBeat(payload);
        status.textContent = "ADDED — VISIBLE ON THE BEAT STORE";
      }
      status.className = "form-status ok";
      resetBeatForm();
    } catch (err) {
      status.textContent = "FAILED — " + (err.message || "TRY AGAIN");
      status.className = "form-status error";
    }
    setTimeout(() => { status.textContent = ""; status.className = "form-status"; }, 3500);
  });
  document.getElementById("beatFormReset").addEventListener("click", resetBeatForm);
  function resetBeatForm() {
    const f = document.getElementById("beatForm");
    f.reset();
    f.entityId.value = "";
    const first = f.querySelector('input[name="icon"]');
    if (first) first.checked = true;
    document.getElementById("beatFormTitle").textContent = "Add Beat";
    document.getElementById("beatFormSubmit").textContent = "+ ADD TO LIBRARY";
    document.getElementById("beatFormReset").hidden = true;
  }

  // ---------- CLIENTS ----------
  // Merge two sources:
  //  - users collection (people who created an account, even if they never booked)
  //  - bookings collection (guest bookings → people without accounts)
  // Keyed by lowercased email; falls back to phone or name for guests.
  function mergedClients() {
    const map = new Map();

    // Seed from accounts in /users
    users.forEach((u) => {
      const key = (u.email || "").toLowerCase();
      if (!key) return;
      const fullName = u.displayName ||
        ((u.firstName || "") + " " + (u.lastName || "")).trim() ||
        u.email;
      map.set(key, {
        name: fullName,
        email: u.email,
        phone: u.phone || "",
        provider: u.provider || "password",
        hasAccount: true,
        joinedAt: u.createdAt || null,
        count: 0,
        latest: null
      });
    });

    // Layer booking data on top. Cancelled bookings don't count toward the
    // client's booking total or "latest service" — they're explicitly negated.
    bookings.forEach((b) => {
      const status = b.status || "PENDING";
      if (status === "CANCELLED") return;
      const key = (b.email || b.phone || b.name || "").toLowerCase();
      if (!key) return;
      if (!map.has(key)) {
        map.set(key, {
          name: b.name,
          email: b.email,
          phone: b.phone,
          provider: "guest",
          hasAccount: false,
          joinedAt: null,
          count: 1,
          latest: b
        });
      } else {
        const c = map.get(key);
        c.count += 1;
        // Backfill phone/name from booking if missing on profile
        if (!c.phone && b.phone) c.phone = b.phone;
        if (!c.name && b.name) c.name = b.name;
        if (!c.latest || toMillis(b.createdAt) > toMillis(c.latest.createdAt)) c.latest = b;
      }
    });

    return [...map.values()].sort((a, b) => {
      // Account holders first, then by booking count desc, then by name
      if (a.hasAccount !== b.hasAccount) return a.hasAccount ? -1 : 1;
      if (a.count !== b.count) return b.count - a.count;
      return (a.name || "").localeCompare(b.name || "");
    });
  }
  // Backward-compat for the dashboard tile count.
  function uniqueClients() { return mergedClients(); }

  function providerTag(provider) {
    if (provider === "google")   return '<span class="br-tag client-tag-account client-tag-google">GOOGLE</span>';
    if (provider === "password") return '<span class="br-tag client-tag-account">ACCOUNT</span>';
    return '<span class="br-tag client-tag-guest">GUEST</span>';
  }

  function renderClients() {
    const body  = document.getElementById("clientsBody");
    const empty = document.getElementById("clientsEmpty");
    const list  = mergedClients();
    body.innerHTML = list.map((c) => {
      const waUrl = waLink(c.phone, `Hi ${(c.name || "").split(" ")[0] || "there"}, this is Ozone Studios.`);
      const joined = c.joinedAt ? `<div class="client-joined">Joined ${escapeHtml(fmtSubmittedAt(c.joinedAt))}</div>` : "";
      const latestService = c.latest ? (c.latest.service || "—") : "—";
      return `
        <article class="admin-row client-row">
          <div class="client-name-cell">
            <span class="br-name">${escapeHtml(c.name || "")}</span>
            <span class="br-tags">${providerTag(c.provider)}</span>
            ${joined}
          </div>
          <div class="br-contact">${c.email ? `<a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a>` : ""}</div>
          <div class="br-contact">${c.phone ? `<a href="tel:${escapeHtml(c.phone)}">${escapeHtml(c.phone)}</a>` : ""}</div>
          <div><span class="client-count">${c.count}</span></div>
          <div class="br-service">${escapeHtml(latestService)}</div>
          <div class="row-actions">
            ${waUrl
              ? `<a class="wa-btn" href="${waUrl}" target="_blank" rel="noopener noreferrer" aria-label="Message on WhatsApp">${WA_SVG}</a>`
              : `<button class="wa-btn" type="button" disabled aria-label="No phone on file">${WA_SVG}</button>`}
          </div>
        </article>
      `;
    }).join("");
    empty.hidden = list.length !== 0;
  }

  // ---------- INIT ----------
  if (!location.hash) location.hash = "#dashboard";
  route();
})();
