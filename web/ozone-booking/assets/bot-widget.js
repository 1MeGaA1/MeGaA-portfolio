/* =========================================================================
   Floating WhatsApp widget
   Self-contained: injects its own CSS + HTML, attaches its own listeners.
   Include with: <script src="assets/bot-widget.js"></script>
   ========================================================================= */
(function () {
  if (document.getElementById("oz-bot-root")) return; // double-include guard

  var WHATSAPP_URL = "https://www.whatsapp.com/catalog/200000000000/?app_absent=0";

  /* ---------- styles ---------- */
  var css = "" +
    ".oz-bot{position:fixed;right:22px;bottom:22px;z-index:100;font-family:'Space Grotesk',system-ui,sans-serif;}" +
    ".oz-bot *{box-sizing:border-box;}" +

    /* FAB */
    ".oz-bot-fab{position:relative;width:64px;height:64px;border:0;border-radius:50%;cursor:pointer;background:linear-gradient(140deg,#1ebd5b,#0a8f3f);box-shadow:0 10px 28px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.10),0 0 26px rgba(37,211,102,.30);display:grid;place-items:center;padding:0;color:#fff;transition:transform .2s ease,box-shadow .25s ease;}" +
    ".oz-bot-fab:hover{transform:translateY(-2px);box-shadow:0 14px 34px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.18),0 0 36px rgba(37,211,102,.50);}" +
    ".oz-bot-fab:active{transform:translateY(0);}" +
    ".oz-bot-fab .oz-bot-icon{width:38px;height:38px;display:block;color:#fff;}" +

    /* Pulse ring */
    ".oz-bot-pulse{position:absolute;inset:-4px;border-radius:50%;border:2px solid rgba(37,211,102,.6);animation:ozBotPulse 2.2s ease-out infinite;pointer-events:none;}" +
    "@keyframes ozBotPulse{0%{transform:scale(.95);opacity:.85;}80%{transform:scale(1.25);opacity:0;}100%{transform:scale(1.25);opacity:0;}}" +

    /* Card */
    ".oz-bot-card{position:absolute;bottom:78px;right:0;width:288px;background:#0d0d0d;color:#fff;border:1px solid rgba(255,255,255,.10);border-radius:18px;overflow:hidden;box-shadow:0 28px 60px rgba(0,0,0,.6),0 0 28px rgba(37,211,102,.12);transform:translateY(8px) scale(.96);transform-origin:bottom right;opacity:0;pointer-events:none;transition:transform .25s ease,opacity .2s ease;}" +
    ".oz-bot[data-state='open'] .oz-bot-card{transform:translateY(0) scale(1);opacity:1;pointer-events:auto;}" +

    /* Close */
    ".oz-bot-close{position:absolute;top:8px;right:10px;width:24px;height:24px;border-radius:50%;border:0;background:rgba(255,255,255,.10);color:#fff;font-size:16px;line-height:1;cursor:pointer;display:grid;place-items:center;padding:0;transition:background .15s ease;z-index:2;}" +
    ".oz-bot-close:hover{background:rgba(255,255,255,.20);}" +

    /* Body */
    ".oz-bot-body{padding:22px 18px 18px;}" +
    ".oz-bot-greet{margin:0 0 6px;font-size:15px;font-weight:600;color:#fff;}" +
    ".oz-bot-msg{margin:0 0 14px;font-size:13.5px;line-height:1.55;color:#cfd2d7;}" +
    ".oz-bot-contact{margin:0 0 14px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);font-size:12px;line-height:1.55;color:#e5e7eb;letter-spacing:.02em;}" +
    ".oz-bot-cta{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:12px 16px;border-radius:999px;background:#25d366;color:#06210e;font-family:'Orbitron','Space Grotesk',sans-serif;font-size:13px;font-weight:700;letter-spacing:.10em;text-decoration:none;border:0;cursor:pointer;box-shadow:0 8px 20px rgba(37,211,102,.32);transition:transform .15s ease,box-shadow .2s ease,background .2s ease;}" +
    ".oz-bot-cta:hover{transform:translateY(-1px);background:#22c75e;box-shadow:0 10px 26px rgba(37,211,102,.45);}" +
    ".oz-bot-cta svg{width:18px;height:18px;}" +

    /* Mobile tweak */
    "@media (max-width:560px){.oz-bot{right:16px;bottom:16px;}.oz-bot-card{width:calc(100vw - 32px);max-width:300px;}}";

  var styleEl = document.createElement("style");
  styleEl.id = "oz-bot-styles";
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  /* ---------- WhatsApp icon (canonical filled logo) ---------- */
  var whatsappSvg =
    "<svg class='oz-bot-icon' viewBox='0 0 32 32' xmlns='http://www.w3.org/2000/svg' fill='currentColor' aria-hidden='true'>" +
      "<path d='M16.003.001C7.165.001.005 7.16 0 15.998c-.002 2.825.737 5.582 2.142 8.012L0 32l8.179-2.144a16 16 0 0 0 7.819 1.992h.007C24.84 31.848 32 24.687 32 15.85 31.998 11.572 30.32 7.55 27.305 4.535A15.9 15.9 0 0 0 16.003.001zm.005 29.18a13.3 13.3 0 0 1-6.78-1.857l-.486-.289-5.045 1.323 1.347-4.92-.317-.504a13.27 13.27 0 0 1-2.034-7.084c.004-7.34 5.978-13.314 13.32-13.314a13.23 13.23 0 0 1 9.421 3.905c2.516 2.519 3.9 5.864 3.899 9.42-.003 7.342-5.977 13.32-13.325 13.32zm7.31-9.974c-.4-.2-2.366-1.167-2.733-1.301-.366-.134-.633-.2-.9.2-.266.4-1.033 1.301-1.266 1.567-.234.267-.467.3-.866.1-.4-.2-1.69-.624-3.218-1.987-1.19-1.06-1.992-2.371-2.226-2.771-.234-.4-.025-.616.176-.815.18-.18.4-.467.6-.7.2-.234.266-.4.4-.667.134-.267.067-.5-.033-.7-.1-.2-.9-2.166-1.233-2.966-.325-.78-.654-.674-.9-.687-.234-.012-.5-.014-.766-.014-.267 0-.7.1-1.067.5-.366.4-1.4 1.367-1.4 3.333 0 1.967 1.434 3.866 1.633 4.133.2.267 2.821 4.307 6.834 6.04.954.413 1.7.66 2.282.846.959.305 1.832.262 2.521.159.77-.115 2.366-.967 2.7-1.9.333-.934.333-1.733.233-1.9-.1-.167-.367-.267-.767-.467z'/>" +
    "</svg>";

  /* CTA icon — same WhatsApp glyph but without the FAB-only class. */
  var ctaWhatsappSvg = whatsappSvg.replace("class='oz-bot-icon'", "");

  /* ---------- markup ---------- */
  var wrap = document.createElement("div");
  wrap.className = "oz-bot";
  wrap.id = "oz-bot-root";
  wrap.dataset.state = "closed";
  wrap.innerHTML =
    "<button type='button' class='oz-bot-fab' aria-label='Chat on WhatsApp'>" +
      "<span class='oz-bot-pulse' aria-hidden='true'></span>" +
      whatsappSvg +
    "</button>" +

    "<div class='oz-bot-card' role='dialog' aria-label='Chat on WhatsApp'>" +
      "<button type='button' class='oz-bot-close' aria-label='Close'>×</button>" +
      "<div class='oz-bot-body'>" +
        "<p class='oz-bot-greet'>Hello! 👋 😊</p>" +
        "<p class='oz-bot-msg'>Let me know if you have any questions.</p>" +
        "<p class='oz-bot-contact'>📍 Cairo, Egypt &nbsp;|&nbsp; 📞 +20 1XX XXX XXXX</p>" +
        "<a class='oz-bot-cta' href='" + WHATSAPP_URL + "' target='_blank' rel='noopener noreferrer'>" +
          ctaWhatsappSvg + "<span>CHAT ON WHATSAPP</span>" +
        "</a>" +
      "</div>" +
    "</div>";

  function attach() {
    document.body.appendChild(wrap);

    var fab = wrap.querySelector(".oz-bot-fab");
    var closeBtn = wrap.querySelector(".oz-bot-close");

    function open()   { wrap.dataset.state = "open"; }
    function close()  { wrap.dataset.state = "closed"; }
    function toggle() { (wrap.dataset.state === "open") ? close() : open(); }

    fab.addEventListener("click", toggle);
    closeBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      close();
    });
    // Click outside to close
    document.addEventListener("click", function (e) {
      if (wrap.dataset.state !== "open") return;
      if (!wrap.contains(e.target)) close();
    });
    // ESC to close
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && wrap.dataset.state === "open") close();
    });

    // Auto-open once per session, after a delay
    try {
      if (!sessionStorage.getItem("oz_bot_seen")) {
        setTimeout(function () {
          open();
          sessionStorage.setItem("oz_bot_seen", "1");
        }, 1800);
      }
    } catch (e) { /* sessionStorage blocked: ignore */ }
  }

  if (document.body) {
    attach();
  } else {
    document.addEventListener("DOMContentLoaded", attach);
  }
})();
