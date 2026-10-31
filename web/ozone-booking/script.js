// Smooth nav active-link sync on scroll
(function () {
  const links = document.querySelectorAll(".nav-links a");
  const sections = [...document.querySelectorAll("section[id]")];

  function setActive() {
    const y = window.scrollY + 140;
    let current = "";
    sections.forEach((s) => {
      if (s.offsetTop <= y) current = "#" + s.id;
    });
    links.forEach((a) => {
      a.classList.toggle(
        "active",
        a.getAttribute("href") === current || (current === "" && a.getAttribute("href") === "#")
      );
    });
  }
  window.addEventListener("scroll", setActive, { passive: true });
  setActive();

  // Smooth-scroll nav anchor clicks (uses a JS animation so it visibly glides
  // even on browsers/settings where CSS scroll-behavior is too snappy).
  const navH = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--nav-h"), 10) || 92;

  function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function smoothScrollTo(targetY, duration) {
    const startY = window.scrollY;
    const dist = targetY - startY;
    if (Math.abs(dist) < 2) return;
    // Temporarily disable CSS scroll-behavior so each frame lands cleanly
    const htmlEl = document.documentElement;
    const prevBehavior = htmlEl.style.scrollBehavior;
    htmlEl.style.scrollBehavior = "auto";
    const start = performance.now();
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      window.scrollTo(0, startY + dist * easeInOutCubic(t));
      if (t < 1) {
        requestAnimationFrame(step);
      } else {
        htmlEl.style.scrollBehavior = prevBehavior;
      }
    }
    requestAnimationFrame(step);
  }

  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const href = a.getAttribute("href");
      if (!href || href === "#") {
        e.preventDefault();
        smoothScrollTo(0, 900);
        history.replaceState(null, "", " ");
        return;
      }
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const targetY = target.getBoundingClientRect().top + window.scrollY - navH;
      const dist = Math.abs(targetY - window.scrollY);
      const duration = Math.min(1400, Math.max(600, dist * 0.6));
      smoothScrollTo(targetY, duration);
      history.pushState(null, "", href);
    });
  });
})();

// Footer year
(function () {
  const y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
})();

// Casino-style streams counter — rolls 0 → target on first scroll into view
(function () {
  const counter = document.getElementById("streamsCounter");
  if (!counter) return;
  const display = counter.querySelector(".counter-display");
  const plus = display.querySelector(".counter-plus");
  if (!display || !plus) return;

  const target = parseInt(display.dataset.target || "1000000", 10);
  const targetStr = String(target);                     // "1000000"
  const groupedStr = target.toLocaleString("en-US");    // "1,000,000"

  // Build the visual: a .digit cell per number, .comma in between
  const digitNodes = [];
  for (let i = 0; i < groupedStr.length; i++) {
    const ch = groupedStr.charAt(i);
    if (ch === ",") {
      const c = document.createElement("span");
      c.className = "comma";
      c.textContent = ",";
      display.insertBefore(c, plus);
    } else {
      const cell = document.createElement("span");
      cell.className = "digit";
      const strip = document.createElement("span");
      strip.className = "strip";
      cell.appendChild(strip);
      display.insertBefore(cell, plus);
      digitNodes.push({ cell, strip, target: parseInt(ch, 10) });
    }
  }

  // For each digit, build a strip with N full 0–9 cycles ending at the target digit.
  // Earlier (left-most) digits land first; later digits keep spinning longer.
  function buildStrip(strip, targetDigit, cycles) {
    let html = "";
    for (let c = 0; c < cycles; c++) {
      for (let d = 0; d < 10; d++) html += "<span>" + d + "</span>";
    }
    for (let d = 0; d <= targetDigit; d++) html += "<span>" + d + "</span>";
    strip.innerHTML = html;
    return cycles * 10 + targetDigit; // total offset (in em) to land on the last span
  }

  let started = false;
  function startRoll() {
    if (started) return;
    started = true;

    digitNodes.forEach((node, i) => {
      // Right-most digits spin longer for the casino "land sequentially" feel.
      const cycles = 3 + i * 0.6;
      const totalSteps = buildStrip(node.strip, node.target, Math.round(cycles));
      // Each digit gets a slightly longer duration so they settle one after the other.
      const dur = 1600 + i * 220; // ms
      node.strip.style.transition =
        "transform " + dur + "ms cubic-bezier(.18,.86,.24,1)";
      // Force reflow so the transition applies cleanly
      // eslint-disable-next-line no-unused-expressions
      node.strip.offsetHeight;
      node.strip.style.transform = "translateY(-" + totalSteps + "em)";
    });

    // After the last digit lands, mark active for label glow
    const finalDelay = 1600 + (digitNodes.length - 1) * 220;
    setTimeout(() => counter.classList.add("is-active"), finalDelay);
  }

  function isInView() {
    const r = counter.getBoundingClientRect();
    const vh = window.innerHeight || document.documentElement.clientHeight;
    // Start once at least ~30% of the counter has crossed into the viewport
    const threshold = 0.3 * r.height;
    return r.top < vh - threshold && r.bottom > threshold;
  }

  function checkAndStart() {
    if (isInView()) {
      startRoll();
      window.removeEventListener("scroll", checkAndStart);
      window.removeEventListener("resize", checkAndStart);
    }
  }

  // Try IntersectionObserver first (preferred when supported)
  let ioFired = false;
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            ioFired = true;
            startRoll();
            io.disconnect();
          }
        });
      },
      { threshold: 0.3 }
    );
    io.observe(counter);
  }

  // Always set up a scroll fallback — handles environments where IO is unreliable.
  window.addEventListener("scroll", checkAndStart, { passive: true });
  window.addEventListener("resize", checkAndStart);
  // Run once on load in case the counter is already on screen.
  if (document.readyState === "complete") {
    checkAndStart();
  } else {
    window.addEventListener("load", checkAndStart, { once: true });
  }
  // And one more delayed check to cover cases where layout settles late.
  setTimeout(checkAndStart, 250);
})();

// Auth modal — open from nav, switch between Create Account / Sign In
(function () {
  const openBtn = document.getElementById("openAuthModal");
  const modal   = document.getElementById("authModal");
  if (!openBtn || !modal) return;

  const tabs        = modal.querySelectorAll(".auth-modal-tab");
  const eyebrow     = document.getElementById("authModalEye");
  const titleEl     = document.getElementById("authModalTitle");
  const subEl       = document.getElementById("authModalSub");
  const submitBtn   = document.getElementById("authSubmit");
  const form        = document.getElementById("authForm");
  const statusEl    = document.getElementById("authStatus");
  const firstField  = form.querySelector('input[name="firstName"]');
  const emailField  = form.querySelector('input[name="email"]');
  const passField   = form.querySelector('input[name="password"]');
  const confirmField = form.querySelector('input[name="confirmPassword"]');

  let mode = "signup"; // "signup" | "signin"

  function setMode(next) {
    mode = next;
    modal.dataset.mode = next;
    tabs.forEach((t) => t.classList.toggle("is-active", t.dataset.authMode === next));
    if (next === "signup") {
      eyebrow.textContent = "JOIN OZONE";
      titleEl.textContent = "Create your account";
      subEl.textContent = "Track your bookings and skip the form next time.";
      submitBtn.textContent = "CREATE ACCOUNT";
      passField.setAttribute("autocomplete", "new-password");
      passField.setAttribute("minlength", "8");
      passField.placeholder = "At least 8 characters";
    } else {
      eyebrow.textContent = "WELCOME BACK";
      titleEl.textContent = "Sign in";
      subEl.textContent = "Pick up where you left off.";
      submitBtn.textContent = "SIGN IN";
      passField.setAttribute("autocomplete", "current-password");
      passField.removeAttribute("minlength");
      passField.placeholder = "Your password";
    }
    statusEl.textContent = "";
    statusEl.className = "form-status";
  }

  function openModal(initial) {
    setMode(initial || "signup");
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    setTimeout(() => {
      const focusTarget = (mode === "signup") ? firstField : emailField;
      if (focusTarget && !focusTarget.disabled) focusTarget.focus();
    }, 60);
  }
  function closeModal() {
    modal.hidden = true;
    document.body.style.overflow = "";
    form.reset();
    statusEl.textContent = "";
    statusEl.className = "form-status";
  }

  openBtn.addEventListener("click", () => openModal(openBtn.dataset.authMode || "signup"));

  // Google sign-in button — single popup for both Create Account and Sign In tabs.
  const googleBtn = document.getElementById("authGoogleBtn");
  if (googleBtn) {
    googleBtn.addEventListener("click", async () => {
      if (!window.ozFB || !window.ozFB.signInWithGoogle) {
        statusEl.textContent = "STILL LOADING — TRY AGAIN IN A MOMENT";
        statusEl.className = "form-status error";
        return;
      }
      statusEl.textContent = "OPENING GOOGLE...";
      statusEl.className = "form-status";
      googleBtn.disabled = true;
      try {
        await window.ozFB.signInWithGoogle();
        statusEl.textContent = "SIGNED IN WITH GOOGLE";
        statusEl.className = "form-status ok";
        setTimeout(closeModal, 700);
      } catch (err) {
        console.error("[ozone-auth] google error:", err);
        const code = err && err.code ? err.code : "";
        let msg;
        switch (code) {
          case "auth/popup-closed-by-user":
          case "auth/cancelled-popup-request":
            msg = ""; // user closed it themselves — silent
            break;
          case "auth/popup-blocked":
            msg = "POPUP BLOCKED — ALLOW POPUPS FOR THIS SITE";
            break;
          case "auth/account-exists-with-different-credential":
            msg = "AN ACCOUNT WITH THIS EMAIL ALREADY EXISTS USING A PASSWORD";
            break;
          case "auth/operation-not-allowed":
            msg = "GOOGLE SIGN-IN IS DISABLED IN FIREBASE — ENABLE IT FIRST";
            break;
          default:
            msg = code ? code.toUpperCase() : (err.message || "SIGN-IN FAILED").toUpperCase();
        }
        statusEl.textContent = msg;
        statusEl.className = msg ? "form-status error" : "form-status";
      } finally {
        googleBtn.disabled = false;
      }
    });
  }
  tabs.forEach((t) => t.addEventListener("click", () => setMode(t.dataset.authMode)));
  modal.addEventListener("click", (e) => {
    if (e.target.matches("[data-auth-close]")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.hidden) closeModal();
  });

  function authErrorMessage(err) {
    const code = err && err.code ? err.code : "";
    switch (code) {
      case "auth/email-already-in-use":   return "AN ACCOUNT WITH THIS EMAIL ALREADY EXISTS — TRY SIGNING IN";
      case "auth/invalid-email":          return "EMAIL FORMAT INVALID";
      case "auth/weak-password":          return "PASSWORD TOO WEAK — USE AT LEAST 8 CHARACTERS";
      case "auth/invalid-credential":
      case "auth/wrong-password":
      case "auth/user-not-found":         return "WRONG EMAIL OR PASSWORD";
      case "auth/too-many-requests":      return "TOO MANY ATTEMPTS — TRY AGAIN IN A MOMENT";
      case "auth/network-request-failed": return "NETWORK ERROR — CHECK YOUR CONNECTION";
      case "auth/operation-not-allowed":  return "EMAIL SIGN-IN IS DISABLED IN FIREBASE";
      default: return (code ? code : (err && err.message) || "UNKNOWN ERROR").toUpperCase();
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!window.ozFB || !window.ozFB.ready) {
      statusEl.textContent = "STILL LOADING — TRY AGAIN IN A MOMENT";
      statusEl.className = "form-status error";
      return;
    }
    const data = Object.fromEntries(new FormData(form).entries());
    const email = (data.email || "").trim();
    const password = data.password || "";
    if (!email || !password) {
      statusEl.textContent = "FILL IN EMAIL AND PASSWORD";
      statusEl.className = "form-status error";
      return;
    }
    if (mode === "signup") {
      const firstName = (data.firstName || "").trim();
      const lastName  = (data.lastName  || "").trim();
      const phone     = (data.phone     || "").trim();
      const confirm   = data.confirmPassword || "";
      if (!firstName || !lastName) {
        statusEl.textContent = "ENTER YOUR FIRST AND LAST NAME";
        statusEl.className = "form-status error";
        return;
      }
      if (!phone) {
        statusEl.textContent = "ENTER YOUR PHONE NUMBER";
        statusEl.className = "form-status error";
        return;
      }
      if (password.length < 8) {
        statusEl.textContent = "PASSWORD MUST BE AT LEAST 8 CHARACTERS";
        statusEl.className = "form-status error";
        return;
      }
      if (password !== confirm) {
        statusEl.textContent = "PASSWORDS DON'T MATCH";
        statusEl.className = "form-status error";
        confirmField.focus();
        return;
      }
      statusEl.textContent = "CREATING ACCOUNT...";
      statusEl.className = "form-status";
      try {
        await window.ozFB.signUp(email, password, {
          firstName,
          lastName,
          phone,
          displayName: (firstName + " " + lastName).trim()
        });
        // onAuth fired during createUser with no displayName yet — refresh the
        // nav button now that updateProfile() has completed.
        openBtn.textContent = (firstName || email.split("@")[0]).toUpperCase();
        openBtn.dataset.authMode = "signedin";
        statusEl.textContent = "ACCOUNT CREATED — WELCOME";
        statusEl.className = "form-status ok";
        setTimeout(closeModal, 900);
      } catch (err) {
        console.error("[ozone-auth] error:", err);
        statusEl.textContent = authErrorMessage(err);
        statusEl.className = "form-status error";
      }
    } else {
      statusEl.textContent = "SIGNING IN...";
      statusEl.className = "form-status";
      try {
        await window.ozFB.signIn(email, password);
        statusEl.textContent = "SIGNED IN";
        statusEl.className = "form-status ok";
        setTimeout(closeModal, 900);
      } catch (err) {
        console.error("[ozone-auth] error:", err);
        statusEl.textContent = authErrorMessage(err);
        statusEl.className = "form-status error";
      }
    }
  });

  // Reflect auth state in the nav button label + account dropdown.
  // The admin email is reserved for /admin — on the public site we treat it as
  // "not signed in as a customer" so the nav stays consistent for visitors.
  const ADMIN_EMAIL_PUBLIC = "admin@example.com";
  const accountMenu      = document.getElementById("accountMenu");
  const accountMenuName  = document.getElementById("accountMenuName");
  const accountMenuEmail = document.getElementById("accountMenuEmail");
  const accountSignOut   = document.getElementById("accountSignOut");

  function closeAccountMenu() {
    accountMenu.hidden = true;
    openBtn.setAttribute("aria-expanded", "false");
  }
  function openAccountMenu() {
    accountMenu.hidden = false;
    openBtn.setAttribute("aria-expanded", "true");
  }
  function toggleAccountMenu() {
    if (accountMenu.hidden) openAccountMenu(); else closeAccountMenu();
  }

  function whenFirebaseReady(cb) {
    if (window.ozFB && window.ozFB.ready) { cb(); return; }
    window.addEventListener("oz-firebase-ready", cb, { once: true });
  }
  whenFirebaseReady(() => {
    window.ozFB.onAuth((user) => {
      const isCustomer = !!(user && user.email && user.email.toLowerCase() !== ADMIN_EMAIL_PUBLIC.toLowerCase());
      if (isCustomer) {
        const first = (user.displayName || user.email || "").split(/[ @]/)[0] || "ACCOUNT";
        openBtn.textContent = first.toUpperCase();
        openBtn.dataset.authMode = "signedin";
        accountMenuName.textContent = user.displayName || first;
        accountMenuEmail.textContent = user.email || "";
      } else {
        openBtn.textContent = "CREATE ACCOUNT";
        openBtn.dataset.authMode = "signup";
        closeAccountMenu();
      }
    });
  });

  // Override the openBtn click: if signed-in, toggle the dropdown instead of
  // opening the auth modal.
  openBtn.addEventListener("click", (e) => {
    if (openBtn.dataset.authMode === "signedin") {
      e.stopImmediatePropagation();
      toggleAccountMenu();
    }
  }, true);

  // Sign out button inside the dropdown
  accountSignOut.addEventListener("click", async () => {
    closeAccountMenu();
    try { await window.ozFB.signOut(); }
    catch (err) { alert("Sign-out failed: " + err.message); }
  });

  // Close dropdown on outside click or Escape
  document.addEventListener("click", (e) => {
    if (accountMenu.hidden) return;
    if (!document.getElementById("navAccount").contains(e.target)) closeAccountMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !accountMenu.hidden) closeAccountMenu();
  });
})();

// Block navigation on track cards that don't yet have a real link
(function () {
  document.querySelectorAll("a.work-card").forEach((a) => {
    a.addEventListener("click", (e) => {
      const href = a.getAttribute("href");
      if (!href || href === "#" || a.hasAttribute("data-needs-link")) {
        e.preventDefault();
      }
    });
  });
})();

// Shared storage helpers
function ozLoad(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch (e) { return fallback; }
}
function ozSave(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
}

// WhatsApp deep-link helpers (studio number)
const OZ_WA_NUMBER = "200000000000";
function ozOpenWhatsApp(message) {
  const url = "https://wa.me/" + OZ_WA_NUMBER + "?text=" + encodeURIComponent(message);
  window.open(url, "_blank", "noopener");
}

// Slot label helpers — shared between calendar and submit handlers
const OZ_SLOT_LABELS = {
  "15:00-17:00": "3PM — 5PM",
  "17:00-19:00": "5PM — 7PM",
  "19:00-21:00": "7PM — 9PM",
  "21:00-23:00": "9PM — 11PM"
};
function ozFmtTime12(hhmm) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm || "");
  if (!m) return hhmm || "";
  const h = parseInt(m[1], 10);
  const mins = m[2];
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return h12 + (mins !== "00" ? ":" + mins : "") + period;
}
function ozSlotLabel(slot) {
  if (!slot) return "";
  if (OZ_SLOT_LABELS[slot]) return OZ_SLOT_LABELS[slot];
  const parts = slot.split("-");
  if (parts.length !== 2) return slot;
  return ozFmtTime12(parts[0]) + " — " + ozFmtTime12(parts[1]);
}

// Booking calendar — studio tabs, per-studio month calendar, fixed slot list
(function () {
  const form = document.getElementById("bookForm");
  if (!form) return;

  const tabs            = form.querySelectorAll(".studio-tab");
  const calGrid         = form.querySelector("#calGrid");
  const calMonthName    = form.querySelector("#calMonthName");
  const calPrev         = form.querySelector("#calPrev");
  const calNext         = form.querySelector("#calNext");
  const slotButtons     = form.querySelectorAll(".slot:not(.slot-custom)");
  const slotCustom      = form.querySelector("#slotCustom");
  const slotCustomStart = form.querySelector("#slotCustomStart");
  const slotCustomEnd   = form.querySelector("#slotCustomEnd");
  const slotsHead       = form.querySelector("#slotsHead");
  const studioName      = form.querySelector("#studioName");
  const studioDesc      = form.querySelector("#studioDesc");
  const hiddenStudio    = form.querySelector("#hiddenStudio");
  const hiddenDate      = form.querySelector("#hiddenDate");
  const hiddenTime      = form.querySelector("#hiddenTime");
  const summary         = form.querySelector("#bookingSummary");
  const summaryText     = form.querySelector("#selectedSummary");

  const FIXED_SLOTS = ["15:00-17:00", "17:00-19:00", "19:00-21:00", "21:00-23:00"];
  const SLOT_LABELS = OZ_SLOT_LABELS;

  const STUDIOS = {
    A: {
      name: "Studio A",
      descHTML:
        '<p class="eq-sub">Equipment’s</p>' +
        '<ul class="eq-list">' +
          '<li>🎤 Microphone — Rode NT1-A</li>' +
          '<li>🎛 Sound Interface — Universal Audio Volt 276</li>' +
          '<li>🔊 Monitors — PreSonus Eris E5</li>' +
        '</ul>'
    },
    B: {
      name: "Studio B",
      descHTML:
        '<p class="eq-sub">Equipment’s</p>' +
        '<ul class="eq-list">' +
          '<li>🎤 Microphone — Neumann TLM-103</li>' +
          '<li>🎛 Sound Interface — Universal Audio Apollo Twin</li>' +
          '<li>🔊 Monitors — Yamaha HS8</li>' +
        '</ul>'
    }
  };

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const state = {
    activeStudio: "A",
    viewMonth: new Date(today.getFullYear(), today.getMonth(), 1),
    studios: {
      A: { date: null, slot: null },
      B: { date: null, slot: null }
    }
  };

  const pad = (n) => String(n).padStart(2, "0");
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const sameDay = (a, b) => !!(a && b) && a.getTime() === b.getTime();
  const fmtMonth = (d) => d.toLocaleString("en-US", { month: "long", year: "numeric" });
  const fmtDate  = (d) => d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

  function renderStudio() {
    studioName.textContent = STUDIOS[state.activeStudio].name;
    studioDesc.innerHTML = STUDIOS[state.activeStudio].descHTML;
    tabs.forEach((t) => t.classList.toggle("is-active", t.dataset.studio === state.activeStudio));
  }

  function renderCalendar() {
    calMonthName.textContent = fmtMonth(state.viewMonth);
    const year = state.viewMonth.getFullYear();
    const month = state.viewMonth.getMonth();
    const firstDow = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const selDate = state.studios[state.activeStudio].date;

    let html = "";
    for (let i = 0; i < firstDow; i++) html += `<span class="cal-day cal-day-blank"></span>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const cellDate = new Date(year, month, d);
      const isPast = cellDate < today;
      const isToday = sameDay(cellDate, today);
      const isSelected = sameDay(cellDate, selDate);
      const cls = ["cal-day"];
      if (isPast) cls.push("is-past");
      if (isToday) cls.push("is-today");
      if (isSelected) cls.push("is-selected");
      html += `<button type="button" class="${cls.join(" ")}"${isPast ? " disabled" : ""} data-date="${ymd(cellDate)}">${d}</button>`;
    }
    calGrid.innerHTML = html;

    calGrid.querySelectorAll(".cal-day:not(.cal-day-blank)").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.disabled) return;
        const [yy, mm, dd] = btn.dataset.date.split("-").map(Number);
        const s = state.studios[state.activeStudio];
        s.date = new Date(yy, mm - 1, dd);
        s.slot = null;
        renderCalendar();
        renderSlots();
        syncHidden();
      });
    });
  }

  // ---- Reserved-slot awareness (synced from Firestore via admin confirmations) ----
  // Set of "<studio>_<date>_<time>" keys currently reserved.
  const reservedKeys = new Set();
  function reservationKey(studio, date, time) { return studio + "_" + date + "_" + time; }
  function isSlotReserved(studio, date, time) {
    if (!studio || !date || !time) return false;
    return reservedKeys.has(reservationKey(studio, date, time));
  }
  function whenFirebaseReadyForReservations(cb) {
    if (window.ozFB && window.ozFB.ready) { cb(); return; }
    window.addEventListener("oz-firebase-ready", cb, { once: true });
  }
  whenFirebaseReadyForReservations(() => {
    if (!window.ozFB.watchSlotReservations) return;
    window.ozFB.watchSlotReservations((rows) => {
      reservedKeys.clear();
      rows.forEach((r) => reservedKeys.add(reservationKey(r.studio, r.date, r.time)));
      renderSlots();
    });
  });

  function renderSlots() {
    const s = state.studios[state.activeStudio];
    slotsHead.textContent = s.date ? fmtDate(s.date) : "Pick a date";
    const dateStr = s.date ? ymd(s.date) : "";

    slotButtons.forEach((b) => {
      const slotVal = b.dataset.slot;
      const reserved = isSlotReserved(state.activeStudio, dateStr, slotVal);
      b.classList.toggle("is-active", slotVal === s.slot && !reserved);
      b.classList.toggle("is-booked", reserved);
      b.disabled = !s.date || reserved;
      // Restore the original label when the slot frees up
      const base = b.dataset.baseLabel || b.textContent.replace(/\s*·\s*BOOKED\s*$/, "");
      if (!b.dataset.baseLabel) b.dataset.baseLabel = base;
      b.textContent = reserved ? base + " · BOOKED" : base;
    });

    // Custom hours: check if the chosen start-end range overlaps a reservation
    const customStart = slotCustomStart.value;
    const customEnd   = slotCustomEnd.value;
    const customSlot  = (customStart && customEnd) ? customStart + "-" + customEnd : "";
    const customReserved = customSlot && isSlotReserved(state.activeStudio, dateStr, customSlot);
    const isCustom = !!s.slot && !FIXED_SLOTS.includes(s.slot);
    slotCustom.classList.toggle("is-active", isCustom && !customReserved);
    slotCustom.classList.toggle("is-booked", customReserved);
    slotCustomStart.disabled = !s.date;
    slotCustomEnd.disabled = !s.date;
    if (isCustom) {
      const [start, end] = s.slot.split("-");
      if (slotCustomStart.value !== start) slotCustomStart.value = start;
      if (slotCustomEnd.value !== end) slotCustomEnd.value = end;
    }
  }

  function syncHidden() {
    const s = state.studios[state.activeStudio];
    hiddenStudio.value = state.activeStudio;
    hiddenDate.value = s.date ? ymd(s.date) : "";
    hiddenTime.value = s.slot || "";
    if (s.date && s.slot) {
      summary.hidden = false;
      summaryText.textContent = `Studio ${state.activeStudio} · ${fmtDate(s.date)} · ${ozSlotLabel(s.slot)}`;
    } else {
      summary.hidden = true;
    }
  }

  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      state.activeStudio = t.dataset.studio;
      const s = state.studios[state.activeStudio];
      const isCustom = !!s.slot && !FIXED_SLOTS.includes(s.slot);
      if (!isCustom) {
        slotCustomStart.value = "";
        slotCustomEnd.value = "";
      }
      renderStudio();
      renderCalendar();
      renderSlots();
      syncHidden();
    });
  });

  calPrev.addEventListener("click", () => {
    const v = state.viewMonth;
    const next = new Date(v.getFullYear(), v.getMonth() - 1, 1);
    if (next < new Date(today.getFullYear(), today.getMonth(), 1)) return;
    state.viewMonth = next;
    renderCalendar();
  });
  calNext.addEventListener("click", () => {
    const v = state.viewMonth;
    state.viewMonth = new Date(v.getFullYear(), v.getMonth() + 1, 1);
    renderCalendar();
  });

  slotButtons.forEach((b) => {
    b.addEventListener("click", () => {
      const s = state.studios[state.activeStudio];
      if (!s.date) return;
      const dateStr = ymd(s.date);
      if (isSlotReserved(state.activeStudio, dateStr, b.dataset.slot)) return;
      s.slot = b.dataset.slot;
      renderSlots();
      syncHidden();
    });
  });

  function onCustomTimeChange() {
    const s = state.studios[state.activeStudio];
    if (!s.date) return;
    const start = slotCustomStart.value;
    const end = slotCustomEnd.value;
    if (start && end && start < end) {
      const candidate = start + "-" + end;
      // Refuse to select a custom range that's already reserved
      if (isSlotReserved(state.activeStudio, ymd(s.date), candidate)) {
        if (s.slot && !FIXED_SLOTS.includes(s.slot)) s.slot = null;
      } else {
        s.slot = candidate;
      }
    } else if (s.slot && !FIXED_SLOTS.includes(s.slot)) {
      s.slot = null;
    }
    renderSlots();
    syncHidden();
  }
  [slotCustomStart, slotCustomEnd].forEach((inp) => {
    inp.addEventListener("change", onCustomTimeChange);
    inp.addEventListener("input", onCustomTimeChange);
  });

  renderStudio();
  renderCalendar();
  renderSlots();
  syncHidden();
})();

// Auth-aware booking forms — hide fields whose data we already have on the
// signed-in customer's profile, and write any newly-entered fields back to it.
let ozBookingProfile = null;
function ozGetBookingProfile() { return ozBookingProfile; }
(function () {
  const ADMIN_EMAIL_LOCAL = "admin@example.com";
  const forms = [
    document.getElementById("bookForm"),
    document.getElementById("serviceForm")
  ].filter(Boolean);
  if (!forms.length) return;

  // Remember which inputs were originally required so we can restore that
  // attribute when the customer signs back out.
  const originallyRequired = new WeakSet();
  forms.forEach((form) => {
    form.querySelectorAll('[data-known-field] input').forEach((inp) => {
      if (inp.required) originallyRequired.add(inp);
    });
  });

  function applyProfileToForms(profile) {
    ozBookingProfile = profile;
    const has = {
      name:  !!(profile && (profile.displayName || profile.firstName || profile.lastName)),
      email: !!(profile && profile.email),
      phone: !!(profile && profile.phone)
    };
    forms.forEach((form) => {
      // Hide / show fields whose data we have
      form.querySelectorAll('[data-known-field]').forEach((label) => {
        const key = label.dataset.knownField;
        const known = !!has[key];
        label.hidden = known;
        const input = label.querySelector('input, select');
        if (input) input.required = !known && originallyRequired.has(input);
      });
      // Collapse rows where all .field children are hidden; otherwise let the
      // remaining visible field take the full row width.
      form.querySelectorAll('.form-row').forEach((row) => {
        const fields = [...row.querySelectorAll('.field')];
        const visible = fields.filter((c) => !c.hidden);
        row.hidden = visible.length === 0;
        row.style.gridTemplateColumns = visible.length === 1 ? '1fr' : '';
      });
      // "Booking as <name>" chip
      const chip = form.querySelector('[data-known-chip]');
      if (chip) {
        if (profile) {
          chip.hidden = false;
          chip.querySelector('strong').textContent =
            profile.displayName || `${profile.firstName || ""} ${profile.lastName || ""}`.trim() || profile.email || "";
        } else {
          chip.hidden = true;
        }
      }
    });
  }

  function whenFirebaseReady(cb) {
    if (window.ozFB && window.ozFB.ready) { cb(); return; }
    window.addEventListener("oz-firebase-ready", cb, { once: true });
  }

  whenFirebaseReady(() => {
    window.ozFB.onAuth(async (user) => {
      if (!user) { applyProfileToForms(null); return; }
      // Admin account doesn't act as a "customer" on the public site
      if (user.email && user.email.toLowerCase() === ADMIN_EMAIL_LOCAL) {
        applyProfileToForms(null);
        return;
      }
      try {
        const profile = await window.ozFB.getMyProfile();
        applyProfileToForms(profile);
      } catch (_) {
        applyProfileToForms(null);
      }
    });
  });
})();

// Booking mode tabs (Session / Service)
(function () {
  const tabs = document.querySelectorAll(".book-mode-tab");
  const sessionForm = document.getElementById("bookForm");
  const serviceForm = document.getElementById("serviceForm");
  if (!tabs.length || !sessionForm || !serviceForm) return;

  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      const mode = t.dataset.mode;
      tabs.forEach((b) => b.classList.toggle("is-active", b === t));
      sessionForm.hidden = (mode !== "session");
      serviceForm.hidden = (mode !== "service");
    });
  });
})();

// Booking form (session) — saves to localStorage AND opens WhatsApp with the details
(function () {
  const form = document.getElementById("bookForm");
  const status = document.getElementById("formStatus");
  if (!form) return;

  function buildSessionMessage(data) {
    const slot = ozSlotLabel(data.time);
    const lines = [
      "🎙️ *Ozone Studios — Session Booking*",
      "🎚️ Studio: Studio " + data.studio,
      "📅 Date: " + data.date,
      "⏰ Time: " + slot,
      "🎧 Service: " + data.service,
      "",
      "Name: " + data.name,
      "Email: " + data.email,
      "Phone: " + data.phone
    ];
    if (data.notes && data.notes.trim()) lines.push("", "Notes: " + data.notes.trim());
    return lines.join("\n");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());

    // Merge in the signed-in customer's profile for any fields that were hidden
    const prof = (typeof ozGetBookingProfile === "function") ? ozGetBookingProfile() : null;
    if (prof) {
      const fullName = prof.displayName || `${prof.firstName || ""} ${prof.lastName || ""}`.trim();
      if (!data.name)  data.name  = fullName;
      if (!data.email) data.email = prof.email || "";
      if (!data.phone) data.phone = prof.phone || "";
    }

    if (!data.name || !data.email || !data.phone || !data.service || !data.studio || !data.date || !data.time) {
      status.textContent = "PLEASE PICK A STUDIO, DATE, TIME, AND FILL ALL FIELDS";
      status.className = "form-status error";
      return;
    }

    // Open WhatsApp first (must be inside the click gesture to avoid popup block)
    ozOpenWhatsApp(buildSessionMessage(data));

    // If the customer is signed in but didn't have a phone on file, save it now
    if (prof && !prof.phone && data.phone && window.ozFB && window.ozFB.updateMyProfile) {
      try { await window.ozFB.updateMyProfile({ phone: data.phone.trim() }); } catch (_) {}
    }

    const record = {
      type: "session",
      name: data.name.trim(),
      email: data.email.trim(),
      phone: data.phone.trim(),
      service: data.service,
      studio: data.studio,
      date: data.date,
      time: data.time,
      notes: (data.notes || "").trim(),
      status: "PENDING"
    };

    try {
      if (window.ozFB && window.ozFB.addBooking) {
        await window.ozFB.addBooking(record);
      } else {
        // Fallback to localStorage if Firebase hasn't loaded
        const bookings = ozLoad("ozone_bookings", []);
        bookings.push({ id: "bk" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), ...record, createdAt: new Date().toISOString() });
        ozSave("ozone_bookings", bookings);
      }
    } catch (err) {
      console.error("Booking save failed", err);
    }

    status.textContent = "OPENING WHATSAPP — SEND THE MESSAGE TO CONFIRM";
    status.className = "form-status ok";
    form.reset();
  });
})();

// Service request form — submits with a file link
(function () {
  const form = document.getElementById("serviceForm");
  if (!form) return;
  const status = document.getElementById("serviceStatus");

  function buildServiceMessage(data) {
    const lines = [
      "🎚️ *Ozone Studios — Service Request*",
      "🎧 Service: " + data.serviceType,
      "⭐ Tier: " + (data.tier || "Standard"),
      "",
      "Name: " + data.name,
      "Email: " + data.email,
      "Phone: " + data.phone,
      "",
      "🔗 Files: " + data.link
    ];
    if (data.notes && data.notes.trim()) lines.push("", "Notes: " + data.notes.trim());
    return lines.join("\n");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());

    // Merge profile for hidden fields
    const prof = (typeof ozGetBookingProfile === "function") ? ozGetBookingProfile() : null;
    if (prof) {
      const fullName = prof.displayName || `${prof.firstName || ""} ${prof.lastName || ""}`.trim();
      if (!data.name)  data.name  = fullName;
      if (!data.email) data.email = prof.email || "";
      if (!data.phone) data.phone = prof.phone || "";
    }

    if (!data.serviceType || !data.name || !data.email || !data.phone || !data.link) {
      status.textContent = "PLEASE PICK A SERVICE, ADD A LINK, AND FILL ALL FIELDS";
      status.className = "form-status error";
      return;
    }

    // Open WhatsApp first (inside the click gesture so popup blockers don't fire)
    ozOpenWhatsApp(buildServiceMessage(data));

    // Persist phone back to profile if we collected it for a Google-signin user
    if (prof && !prof.phone && data.phone && window.ozFB && window.ozFB.updateMyProfile) {
      try { await window.ozFB.updateMyProfile({ phone: data.phone.trim() }); } catch (_) {}
    }

    const record = {
      type: "service",
      name: data.name.trim(),
      email: data.email.trim(),
      phone: data.phone.trim(),
      service: data.serviceType,
      tier: data.tier || "Standard",
      link: data.link.trim(),
      notes: (data.notes || "").trim(),
      status: "PENDING"
    };

    try {
      if (window.ozFB && window.ozFB.addBooking) {
        await window.ozFB.addBooking(record);
      } else {
        const bookings = ozLoad("ozone_bookings", []);
        bookings.push({ id: "sv" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), ...record, createdAt: new Date().toISOString() });
        ozSave("ozone_bookings", bookings);
      }
    } catch (err) {
      console.error("Service request save failed", err);
    }

    status.textContent = "OPENING WHATSAPP — SEND THE MESSAGE TO CONFIRM";
    status.className = "form-status ok";
    form.reset();
  });
})();

