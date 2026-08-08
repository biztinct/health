/* =============================================================================
   CareJioX Learn — engine
   -----------------------------------------------------------------------------
   Dependency-free on purpose, so the pieces port into the host framework:
     Spot        spotlight engine (box-shadow hole + placed coach card)
     Trace       SVG cubic path + dot advanced along getPointAtLength
     flashRing   scroll-into-view + temporary ring (Coach "point at")
     SCREENS     the simulated CMS shell; every referenced control carries a
                 stable data-a="…" anchor (the anchor registry of DESIGN_SPEC §4)
     Views       HubView / JourneyView / LessonView / SimView / CompView
     State       one persisted object in localStorage
   Delegated events only: data-go / data-nav / data-act on one document listener.
   ========================================================================== */

const DEFAULT_STATE = {
  lang: "en", role: "crm", motion: "auto", mode: null,
  done: {}, lessonPos: {}, missions: {}, conf: {},
  last: null, visited: false, quizTries: {},
};
let S;
try { S = Object.assign({}, DEFAULT_STATE, JSON.parse(localStorage.getItem("cjxLearn") || "{}")); }
catch (e) { S = Object.assign({}, DEFAULT_STATE); }
function save() { localStorage.setItem("cjxLearn", JSON.stringify(S)); }

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const APP = $("#app"), OVER = $("#overlay-root"), TOASTS = $("#toast-root");

function T(k) { const v = I18N[S.lang][k]; return v === undefined ? I18N.en[k] : v; }
/* Every translatable string passes through here, so `{{key}}` token resolution
   is free everywhere — lessons, quizzes, missions, coach answers, chrome.
   Tokens fill NAMED SLOTS only; they can never introduce prose. */
const TOKEN_RE = /\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}/g;
function tx(o) {
  if (o == null) return "";
  const s = typeof o === "string" ? o : (o[S.lang] || o.en || "");
  return s.indexOf("{{") === -1 ? s : s.replace(TOKEN_RE, (_, k) => tenantValue(k, S.lang));
}
function ic(n, c) { return `<svg class="ic ${c || ""}" aria-hidden="true"><use href="#i-${n}"/></svg>`; }
function esc(s) { return String(s).replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m])); }
function reduced() {
  return S.motion === "reduced" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function M(n) { return money(n, S.lang); }
function P(n) { return pct(n, S.lang); }
function N(n) { return num(n, S.lang); }

function toast(msg, kind, icon) {
  const el = document.createElement("div");
  el.className = "toast " + (kind || "");
  el.innerHTML = ic(icon || "info") + "<span>" + msg + "</span>";
  TOASTS.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 240); }, 3400);
}
function setLast(label) { S.last = { hash: location.hash, label }; save(); }

/* --------------------------------------------------------------- modal */
let modalEl = null;
function openModal(html, opts) {
  closeModal();
  modalEl = document.createElement("div");
  modalEl.className = "modal-bg";
  modalEl.innerHTML = `<div class="modal" role="dialog" aria-modal="true" tabindex="-1">${html}</div>`;
  document.body.appendChild(modalEl);
  const box = $(".modal", modalEl);
  box.focus();
  if (!opts || opts.dismissable !== false) {
    modalEl.addEventListener("click", (e) => { if (e.target === modalEl) closeModal(); });
  }
  return box;
}
function closeModal() { if (modalEl) { modalEl.remove(); modalEl = null; } }

/* =============================================================================
   Spotlight engine — never covers the element it explains: it dims AROUND it.
   ========================================================================== */
const Spot = {
  hole: null, card: null,
  show(anchorSel, cardHTML) {
    Trace.clear();               // a trace belongs to ONE step; never let it outlive it
    const el = anchorSel ? $(`[data-a="${anchorSel}"]`) : null;
    if (!this.hole) {
      this.hole = document.createElement("div"); this.hole.className = "spot-hole";
      this.card = document.createElement("div"); this.card.className = "coach";
      this.card.setAttribute("role", "region");
      this.card.setAttribute("aria-live", "polite");
      OVER.appendChild(this.hole); OVER.appendChild(this.card);
    }
    this.card.innerHTML = cardHTML;
    if (el) {
      el.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
      const place = () => {
        // The placement is deferred one frame to let scrollIntoView settle, so
        // it can outlive the step that scheduled it — exiting a lesson calls
        // hide() and this fires afterwards against a torn-down overlay.
        if (!this.hole || !this.card) return;
        const r = el.getBoundingClientRect(), pad = 8;
        this.hole.style.display = "block";
        this.hole.style.top = (r.top - pad) + "px";
        this.hole.style.left = (r.left - pad) + "px";
        this.hole.style.width = (r.width + pad * 2) + "px";
        this.hole.style.height = (r.height + pad * 2) + "px";
        this.position(r);
      };
      reduced() ? place() : setTimeout(place, 190);
    } else {
      this.hole.style.display = "none";
      this.position(null);
    }
  },
  /* placement: right -> left -> below -> above, clamped to the viewport */
  position(r) {
    const c = this.card;
    if (!c) return;                 // same race as place() — see above
    const W = window.innerWidth, H = window.innerHeight;
    // Reserve the strip the floating control bar occupies so the coach card's
    // own Back/Next never end up underneath it.
    const bottomGuard = $(".playbar") ? 88 : 12;
    const usable = H - bottomGuard;
    c.style.top = "0px"; c.style.left = "0px";
    const cw = Math.min(372, W - 32), ch = c.offsetHeight || 260;
    let top, left;
    if (!r) { top = Math.max(16, (usable - ch) / 2); left = (W - cw) / 2; }
    else if (r.right + cw + 28 < W) { left = r.right + 20; top = r.top + r.height / 2 - ch / 2; }
    else if (r.left - cw - 28 > 0) { left = r.left - cw - 20; top = r.top + r.height / 2 - ch / 2; }
    else if (r.bottom + ch + 28 < usable) { top = r.bottom + 20; left = Math.min(Math.max(16, r.left), W - cw - 16); }
    else { top = Math.max(16, r.top - ch - 20); left = Math.min(Math.max(16, r.left), W - cw - 16); }
    c.style.top = Math.max(12, Math.min(top, usable - ch)) + "px";
    c.style.left = Math.max(12, Math.min(left, W - cw - 12)) + "px";
    c.style.width = cw + "px";
  },
  hide() { if (this.hole) { this.hole.remove(); this.card.remove(); this.hole = null; this.card = null; } Trace.clear(); },
};

/* =============================================================================
   Trace engine — an animated dot travels from a setup value to the line it
   produces. Skipped (drawn as a static path) under reduced motion.
   ========================================================================== */
const Trace = {
  svg: null,
  clear() { if (this.svg) { this.svg.remove(); this.svg = null; } },
  run(fromA, toA) {
    this.clear();
    const a = $(`[data-a="${fromA}"]`), b = $(`[data-a="${toA}"]`);
    if (!a || !b) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const x1 = ra.left + ra.width / 2, y1 = ra.top + ra.height / 2;
    const x2 = rb.left + rb.width / 2, y2 = rb.top + rb.height / 2;
    const mx = (x1 + x2) / 2;
    const d = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "tracelayer");
    svg.innerHTML = `<path d="${d}"/><circle r="6" cx="${x1}" cy="${y1}"/>`;
    OVER.appendChild(svg); this.svg = svg;
    a.classList.add("ring"); setTimeout(() => a.classList.remove("ring"), 3000);
    if (reduced()) { b.classList.add("ring"); setTimeout(() => b.classList.remove("ring"), 3000); return; }
    const path = svg.querySelector("path"), dot = svg.querySelector("circle");
    const len = path.getTotalLength();
    let t0 = null;
    const step = (ts) => {
      if (!this.svg) return;
      if (t0 === null) t0 = ts;
      const k = Math.min(1, (ts - t0) / 1250);
      const pt = path.getPointAtLength(len * k);
      dot.setAttribute("cx", pt.x); dot.setAttribute("cy", pt.y);
      if (k < 1) requestAnimationFrame(step);
      else { b.classList.add("ring"); setTimeout(() => b.classList.remove("ring"), 3000); }
    };
    requestAnimationFrame(step);
  },
};

function flashRing(anchor) {
  const el = $(`[data-a="${anchor}"]`);
  if (!el) return false;
  el.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
  el.classList.add("ring");
  setTimeout(() => el.classList.remove("ring"), 3200);
  return true;
}

/* =============================================================================
   Role visibility — mirrors the DB role gate on cms.sidebar.item.
   MEASURED: a session without Owner/CRM sees only the four ungated CRM leaves.
   ========================================================================== */
function canSee(item) { return !item.roles || item.roles.indexOf(S.role) !== -1; }
function roleLabel() { return T("roles")[S.role]; }

/* =============================================================================
   THE SIMULATED SHELL
   ========================================================================== */
/* Which screen the shell is currently showing — the Coach grounds on this. */
let CURRENT_SCREEN = null;

function shellHTML(screen, opts) {
  opts = opts || {};
  CURRENT_SCREEN = screen;
  const guided = !!opts.guided; // lessons/missions show the full menu
  const secs = MENU.map((sec) => {
    const items = sec.items.map((it) => {
      const vis = !sec.inScope ? true : canSee(it);
      const off = !sec.inScope || (!vis && !guided);
      const on = it.id === screen;
      return `<button class="item ${on ? "on" : ""} ${off ? "off" : ""}" data-nav="${it.id}"
        ${off ? 'tabindex="-1" aria-disabled="true"' : ""}>${ic(it.icon)}<span>${esc(tx(it.label))}</span></button>`;
    }).join("");
    return `<div class="sec">${esc(tx(sec.label))}</div>${items}`;
  }).join("");
  const scr = SCREENS[screen] ? SCREENS[screen]() : "";
  const gated = MENU[0].items.find((i) => i.id === screen);
  const blocked = gated && !canSee(gated) && !guided;
  return `
  <div class="shell">
    <aside class="sb" aria-label="CareJioX navigation">
      <div class="brand"><span class="mark">${ic("heart")}</span><span>CareJioX</span></div>
      <div class="catch"><b>${esc(T("catchment"))}</b>${esc(T("hanoi"))}</div>
      ${secs}
      <div class="foot">${esc(tx(B("Practice tenant · demo data", "Đơn vị thực hành · dữ liệu mô phỏng")))}</div>
    </aside>
    <div class="main">
      ${opts.practice ? `<div class="pbanner">${ic("shield-check")}<span>${esc(T("practiceBanner"))}</span></div>` : ""}
      <div class="mhead">
        <button class="sbtoggle" data-act="sb-open" aria-label="Menu">${ic("menu")}</button>
        <h2>${esc(screenTitle(screen))}</h2>
        <span class="sub">${esc(tx(B("Việt Úc Care — Hà Nội", "Việt Úc Care — Hà Nội")))}</span>
        <span class="who chip b">${ic("users")}${esc(roleLabel())}</span>
      </div>
      <div class="screen">${blocked ? blockedHTML() : scr}</div>
    </div>
  </div>`;
}
function screenTitle(id) {
  for (const sec of MENU) for (const it of sec.items) if (it.id === id) return tx(it.label);
  return "";
}
function blockedHTML() {
  return `<div class="panel" style="max-width:560px">
    <h3>${ic("lock")}${esc(T("notVisible"))}</h3>
    <p style="color:var(--muted)">${esc(T("notVisibleBody"))}</p>
    <p style="color:var(--muted);font-size:12.5px;margin:0">${esc(tx(B(
      "Switch the role at the top of the page to Owner or CRM / Reception to see this screen.",
      "Hãy đổi vai trò ở đầu trang sang Chủ sở hữu hoặc CRM / Lễ tân để xem màn hình này.")))}</p>
  </div>`;
}

/* --------------------------------------------------------------- screens */
const SCREENS = {
  dashboard() {
    const m = CASE.month, k = CASE.kpis;
    const cards = [
      ["phone", T("today"), N(k.contactsToday), B("Contacts Today", "Liên hệ hôm nay"), "", "db-contacts"],
      ["clock", T("all"), N(k.pendingFollowups), B("Pending Follow-ups", "Đang chờ theo dõi"), "warn", "db-pending"],
      ["target", T("all"), N(k.activeLeads), B("Active Leads", "KHTN đang hoạt động"), "", "db-leads"],
      ["calendar", T("week"), N(k.bookingsWeek), B("Bookings This Week", "Lịch hẹn tuần này"), "pos", "db-bookings"],
      ["trending-up", T("month"), P(m.conversion), B("Conversion Rate", "Tỷ lệ chuyển đổi"), "pos", "db-conv"],
      ["ban", T("month"), P(m.spamRate), B("Spam Rate", "Tỷ lệ thư rác"), "", "db-spam"],
    ].map(([i, per, v, lab, tone, a]) => `
      <div class="kpi ${tone}" data-a="${a}">
        <div class="kt">${ic(i)}<span>${esc(tx(lab))}</span></div>
        <div class="kv">${v}</div>
        <div style="font-size:11px;color:var(--faint)">${esc(per)}</div>
      </div>`).join("");
    const segs = [
      [m.booking, "var(--st-completed)", B("Booking", "Đặt lịch")],
      [m.lead, "var(--st-confirmed)", B("Lead", "KHTN")],
      [m.lost, "var(--st-cancelled)", B("Lost Booking", "Mất cơ hội")],
      [m.spam, "var(--st-draft)", B("Spam", "Thư rác")],
    ];
    const stack = segs.map(([n, c]) => `<i style="width:${(n / m.total * 100).toFixed(1)}%;background:${c}"></i>`).join("");
    const leg = segs.map(([n, c, l]) => `<span><em style="background:${c}"></em>${esc(tx(l))} · <b>${N(n)}</b></span>`).join("");
    const max = Math.max.apply(null, CASE.channels.map((c) => c.n));
    const bars = CASE.channels.map((c) => `
      <div class="hbar"><span>${esc(tx(c.label))}</span>
        <span class="track"><i style="width:${(c.n / max * 100).toFixed(0)}%"></i></span><b>${N(c.n)}</b></div>`).join("");
    return `
      <div class="tabs" data-a="db-period">
        ${[["today", 1], ["week", 0], ["month", 0], ["all", 0], ["custom", 0]]
          .map(([k2, on]) => `<button aria-selected="${on ? "true" : "false"}">${esc(T(k2))}</button>`).join("")}
      </div>
      <div class="grid g6" style="margin-bottom:var(--sp4)">${cards}</div>
      <div class="grid g2">
        <div class="panel" data-a="db-pipeline"><h3>${ic("pie")}${esc(tx(B("Contact Pipeline · this month", "Quy trình liên hệ · tháng này")))}</h3>
          <div class="stack">${stack}</div><div class="legend">${leg}</div>
          <p style="font-size:12px;color:var(--muted);margin:var(--sp3) 0 0">${esc(tx(B(
            `${N(m.total)} enquiries = ${N(m.spam)} spam + ${N(m.real)} real; ${N(m.real)} = ${N(m.booking)} booked + ${N(m.lead)} leads + ${N(m.lost)} lost.`,
            `${N(m.total)} yêu cầu = ${N(m.spam)} thư rác + ${N(m.real)} thật; ${N(m.real)} = ${N(m.booking)} đã đặt lịch + ${N(m.lead)} KHTN + ${N(m.lost)} mất cơ hội.`)))}</p>
        </div>
        <div class="panel" data-a="db-channels"><h3>${ic("bar-chart")}${esc(tx(B("Source Channels · this month", "Các kênh nguồn · tháng này")))}</h3>
          <div class="hbars">${bars}</div></div>
      </div>
      <div class="panel" data-a="db-recent"><h3>${ic("clock")}${esc(tx(B("Recent Contacts", "Liên hệ gần đây")))}</h3>
        <div class="rows">
          ${recentRows()}
        </div>
      </div>`;
  },

  carecommand() {
    const u = CASE.urgency;
    const rows = wallRows();
    const calc = u.map((t) => `<div class="cr ${t.v === 15 && /watch|cảnh báo/i.test(tx(t.k)) ? "hit" : ""}"
        ${/watch|cảnh báo/i.test(tx(t.k)) ? 'data-a="cc-term-watch"' : ""}>
        <span>${esc(tx(t.k))}</span><b>+${t.v}</b></div>`).join("")
      + `<div class="cr tot"><span>${esc(tx(B("Urgency score", "Điểm ưu tiên")))}</span><b>${CASE.urgencyTotal}</b></div>`;
    return `
      <div class="tabs" data-a="cc-tabs">
        <button aria-selected="true">${esc(T("attention"))} · ${CASE.wall.needsReply}</button>
        <button aria-selected="false">${esc(T("leadsTab"))}</button>
        <button aria-selected="false">${esc(T("allTab"))} · ${CASE.wall.open}</button>
        <span class="chip b" style="margin-left:auto;align-self:center" data-a="cc-catchment">${ic("map-pin")}${esc(T("catchment"))}: ${esc(T("hanoi"))}</span>
      </div>
      <div class="grid g2" style="align-items:start">
        <div class="panel" data-a="cc-wall">
          <h3>${ic("zap")}${esc(tx(B("Attention wall", "Bảng cần chú ý")))}
            <span class="chip" style="margin-left:auto">${esc(tx(B(
              `${CASE.wall.open} open · ${CASE.wall.unclaimed} unclaimed`,
              `${CASE.wall.open} đang mở · ${CASE.wall.unclaimed} chưa ai nhận`)))}</span></h3>
          <div class="rows">${rows}</div>
        </div>
        <div class="panel">
          <h3>${ic("message-circle")}#${CASE.convId} · ${esc(tx(CASE.sender))}</h3>
          <div class="claimbar" data-a="cc-claim">${ic("user-plus")}
            <span>${esc(T("unclaimed"))}</span>
            <button class="btn sm pri" data-act="sim-claim" data-a="cc-release">${esc(T("claim"))}</button></div>
          <div class="tl">${timelineHTML()}</div>
          <div class="composer" data-a="cc-composer">
            <textarea placeholder="${esc(tx(B("Type a reply…", "Nhập câu trả lời…")))}"></textarea>
          </div>
          <div class="strip" data-a="cc-actions">
            <button class="btn sm pri" data-act="sim-send">${ic("send")}${esc(T("sendReply"))}</button>
            <button class="btn sm" data-act="sim-note">${ic("file-text")}${esc(T("addNote"))}</button>
            <button class="btn sm" data-act="sim-book">${ic("calendar")}${esc(T("bookBtn"))}</button>
            <button class="btn sm" data-act="sim-escalate" data-a="cc-escalate">${ic("alert-triangle")}${esc(T("escalate"))}</button>
            <button class="btn sm" data-act="sim-lead">${ic("target")}${esc(T("logLead"))}</button>
            <button class="btn sm" data-act="sim-consent" data-a="cc-consent">${ic("shield-check")}${esc(T("consentBtn"))}</button>
            <button class="btn sm danger" data-act="sim-junk" data-a="cc-junk">${ic("ban")}${esc(T("markJunk"))}</button>
          </div>
        </div>
      </div>
      <div class="grid g2" style="align-items:start">
        <div class="panel" data-a="cc-score-4172"><h3>${ic("calculator")}${esc(tx(B("Urgency breakdown · #4172", "Chi tiết điểm ưu tiên · #4172")))}</h3>
          <div class="calc">${calc}</div></div>
        <div class="panel" data-a="cc-pipeline"><h3>${ic("git-branch")}${esc(tx(B("Conversation lifecycle", "Vòng đời cuộc hội thoại")))}</h3>
          ${pipeHTML("conv", 0)}</div>
      </div>`;
  },

  channelcenter() {
    const cards = PRACTICE.channels.map((c) => {
      const connected = c.state !== "not_connected";
      return `
      <div class="chcard" data-a="${c.a}">
        <header><span class="glyph">${ic(c.glyph)}</span><b>${esc(tx(c.name))}</b>
          <span style="margin-left:auto">${statusChip("connection", c.state)}</span></header>
        <div class="meta2"${c.areaAnchor ? ' data-a="ch-area-zalo-hn"' : ""}>${esc(tx(c.meta))}</div>
        <div class="acts">
          ${!connected ? `<button class="btn sm pri">${esc(T("connectBtn"))}</button>` :
            `<button class="btn sm" data-act="sim-reauth" ${c.id === "zalo-hn" ? 'data-a="ch-reauth"' : ""}>${esc(T("reauth"))}</button>
             <button class="btn sm ghost" ${c.id === "zalo-hn" ? 'data-a="ch-disable"' : ""}>${esc(T("disconnect"))}</button>`}
        </div>
      </div>`;
    }).join("");
    return `
      <div class="panel" data-a="ch-pipeline"><h3>${ic("git-branch")}${esc(tx(B("Connection lifecycle", "Vòng đời kết nối")))}</h3>
        ${pipeHTML("conn", 5)}
        <p style="font-size:12px;color:var(--muted);margin:var(--sp3) 0 0">${esc(tx(B(
          "One server path writes this state and audits every move. Ready is derived from the readiness checks, never typed in.",
          "Chỉ một luồng phía máy chủ ghi trạng thái này và ghi nhật ký mọi thay đổi. Trạng thái Đã kết nối được suy ra từ các bước kiểm tra sẵn sàng, không bao giờ nhập tay.")))}</p>
      </div>
      <div class="panel" data-a="ch-catalogue"><h3>${ic("plug")}${esc(tx(B("Connectable channels", "Các kênh có thể kết nối")))}
        <span class="chip" style="margin-left:auto">${esc(tx(B("Walk-in is not connectable — no provider", "Đến trực tiếp không kết nối được — không có nhà cung cấp")))}</span></h3>
        <div class="chcards">${cards}</div></div>
      <div class="grid g2" style="align-items:start">
        <div class="panel" data-a="ch-checks"><h3>${ic("clipboard-check")}${esc(tx(B("Readiness checks · Hà Nội OA", "Kiểm tra sẵn sàng · OA Hà Nội")))}</h3>
          <div class="checks">
            ${PRACTICE.readiness.map((k) => `<div class="chk ${k.pass ? "pass" : "fail"}">
              ${ic(k.pass ? "check-circle" : "x")}<span>${esc(tx(k.l))}</span></div>`).join("")}
          </div>
          <p style="font-size:12px;color:var(--muted);margin:var(--sp3) 0 0">${esc(tx(B(
            "These prove the connection is capable. Only real traffic proves it works.",
            "Những bước này chứng minh kết nối có khả năng hoạt động. Chỉ lưu lượng thật mới chứng minh nó hoạt động.")))}</p>
        </div>
        <div class="panel" data-a="ch-prove"><h3>${ic("target")}${esc(tx(B("Prove it works", "Chứng minh nó hoạt động")))}</h3>
          <p style="font-size:12.5px;color:var(--muted)">${esc(tx(B(
            "Send one message from a personal account to the OA and watch it appear on the wall.",
            "Gửi một tin nhắn từ tài khoản cá nhân tới OA và xem nó xuất hiện trên bảng.")))}</p>
          <button class="btn pri sm" data-act="sim-prove">${ic("send")}${esc(tx(B("Send test message", "Gửi tin nhắn thử")))}</button>
          <div style="margin-top:var(--sp4)" data-a="ch-wall-hn">
            <div class="hbar"><span>${esc(T("hanoi"))}</span><span class="track"><i style="width:100%"></i></span><b>${CASE.wall.open}</b></div>
            <div class="hbar"><span>${esc(T("hcmc"))}</span><span class="track"><i style="width:58%"></i></span><b>7</b></div>
          </div>
        </div>
      </div>
      <div class="panel" data-a="ch-golive"><h3>${ic("shield-check")}${esc(tx(B("Go-live console", "Bảng điều khiển phát hành")))}</h3>
        <p style="font-size:12.5px;color:var(--muted);margin:0">${esc(tx(B(
          "Availability is reported honestly: a channel is offered only when this deployment has an adapter AND the tenant has credentials. Three channels above are shown as Not connected for exactly that reason — the console does not draw a Connect button that could only fail.",
          "Khả dụng được báo cáo trung thực: một kênh chỉ được đưa ra khi bản triển khai này có bộ chuyển đổi VÀ đơn vị có thông tin xác thực. Ba kênh ở trên hiển thị Chưa kết nối đúng vì lý do đó — bảng điều khiển không vẽ ra nút Kết nối chắc chắn sẽ thất bại.")))}</p>
      </div>`;
  },

  unrouted() {
    const items = PRACTICE.captures.map((c) => `
      <div class="row">
        <span class="avatar">${ic("inbox")}</span>
        <span><span class="nm">${esc(tx(c.what))}</span><br><span class="sub2">${esc(tx(c.got))}</span></span>
        <span class="rr">
          <button class="btn sm ${c.anchored ? "pri" : ""}" ${c.anchored ? "" : "disabled"} ${c.anchorA ? 'data-a="ur-convert"' : ""}>${esc(T("convert"))}</button>
          <button class="btn sm ghost" ${c.anchorA ? 'data-a="ur-dismiss"' : ""}>${esc(T("dismiss"))}</button>
        </span>
      </div>`).join("");
    return `<div class="panel" data-a="ur-list">
      <h3>${ic("inbox")}${esc(tx(B("New today", "Mới hôm nay")))}<span class="chip a" style="margin-left:auto">${CASE.unrouted}</span></h3>
      <div class="rows">${items}</div>
      <p style="font-size:12px;color:var(--muted);margin:var(--sp4) 0 0">${esc(tx(B(
        "These records cannot be edited — they are evidence of exactly what the channel sent. Convert needs at least one anchor (a contact, a phone number or an email); the first row has none, so Convert is refused rather than creating an unreachable record.",
        "Các bản ghi này không sửa được — chúng là bằng chứng về đúng những gì kênh đã gửi. Chuyển đổi cần ít nhất một điểm neo (một liên hệ, một số điện thoại hoặc email); dòng đầu tiên không có, nên Chuyển đổi bị từ chối thay vì tạo ra một bản ghi không liên lạc được.")))}</p>
    </div>`;
  },

  contacts() {
    const tabs = [B("All", "Tất cả"), B("Active", "Đang hoạt động"), B("Leads", "KHTN"),
                  B("Bookings", "Đặt lịch"), B("Lost", "Thất bại"), B("Spam", "Thư rác")]
      .map((l, i) => `<button aria-selected="${i === 0 ? "true" : "false"}">${esc(tx(l))}</button>`).join("");
    const rows = PRACTICE.contacts.map((c) => `
      <div class="row">
        <span class="avatar">${esc(initial(c.name))}</span>
        <span><span class="nm">${esc(tx(c.name))}</span><br><span class="sub2">${esc(tx(c.meta))}</span></span>
        <span class="rr">
          ${statusChip("contact", c.status)}
          <button class="btn sm">${esc(T("bookBtn"))}</button>
          <button class="btn sm ghost">${esc(T("escalate"))}</button>
          <button class="btn sm ghost">${esc(T("markJunk"))}</button>
        </span>
      </div>`).join("");
    return `<div class="tabs">${tabs}</div>
      <div class="panel"><div class="rows">${rows}</div></div>
      <div class="panel"><h3>${ic("git-branch")}${esc(tx(B("Contact lifecycle", "Vòng đời liên hệ")))}</h3>${pipeHTML("contact", 2)}</div>`;
  },

  touchpoints() {
    const rows = CASE.attribution.map((a) => `
      <tr><td>${esc(typeof a.c === "string" ? a.c : tx(a.c))}</td>
        <td>${esc(typeof a.src === "string" ? a.src : tx(a.src))}</td>
        <td>pkgdvietuc.com/dich-vu/…</td><td class="n">${N(a.n)}</td></tr>`).join("");
    return `<div class="panel" data-a="tp-table">
        <h3>${ic("crosshair")}${esc(tx(B("Website arrivals · this month", "Lượt đến từ website · tháng này")))}
          <span class="chip a" style="margin-left:auto" data-a="tp-unmatched">${ic("alert-triangle")}${esc(T("unmatched"))} · 4</span></h3>
        <div class="tblwrap"><table class="tbl">
          <thead><tr><th>${esc(tx(B("UTM campaign", "Chiến dịch UTM")))}</th><th>${esc(tx(B("Source / medium", "Nguồn / phương tiện")))}</th>
            <th>${esc(tx(B("Landing page", "Trang đích")))}</th><th style="text-align:right">${esc(tx(B("Enquiries", "Yêu cầu")))}</th></tr></thead>
          <tbody>${rows}<tr style="font-weight:700"><td colspan="3">${esc(tx(B("Total website enquiries", "Tổng yêu cầu từ website")))}</td><td class="n">34</td></tr></tbody>
        </table></div>
      </div>
      <div class="panel"><h3>${ic("target")}${esc(tx(B("The worked case", "Tình huống mẫu")))}</h3>
        <p style="font-size:12.5px;color:var(--muted);margin:0">${esc(tx(B(
          "Trần Mỹ Linh clicked a Google advert on 10 August and read the wound-care page. She did not fill in the form. Two days later she messaged the Zalo OA — and the touchpoint joined the conversation by phone number, not by channel.",
          "Trần Mỹ Linh nhấp vào một quảng cáo Google ngày 10 tháng 8 và đọc trang chăm sóc vết thương. Cô ấy không điền biểu mẫu. Hai ngày sau cô nhắn tới Zalo OA — và điểm chạm được nối với cuộc hội thoại qua số điện thoại, không phải qua kênh.")))}</p>
      </div>`;
  },

  leadanalysis() {
    const head = [B("Booked", "Đã đặt lịch"), B("Lead", "KHTN"), B("Lost", "Mất"), B("Spam", "Thư rác"), B("Total", "Tổng")];
    const data = PRACTICE.pivot.map((r) => `<tr><td><b>${esc(tx(r.ch))}</b></td>
      ${[r.booked, r.lead, r.lost, r.spam].map((v) => `<td class="n">${N(v)}</td>`).join("")}
      <td class="n" style="font-weight:800">${N(r.total)}</td></tr>`).join("");
    const m = CASE.month;
    return `<div class="panel">
      <h3>${ic("bar-chart")}${esc(tx(B("Enquiries by channel × status · this month", "Yêu cầu theo kênh × trạng thái · tháng này")))}</h3>
      <div class="tblwrap"><table class="tbl">
        <thead><tr><th>${esc(tx(B("Effective channel", "Kênh hiệu lực")))}</th>${head.map((h) => `<th style="text-align:right">${esc(tx(h))}</th>`).join("")}</tr></thead>
        <tbody>${data}
          <tr style="font-weight:800"><td>${esc(tx(B("Total", "Tổng")))}</td>
            <td class="n">${N(m.booking)}</td><td class="n">${N(m.lead)}</td><td class="n">${N(m.lost)}</td>
            <td class="n">${N(m.spam)}</td><td class="n">${N(m.total)}</td></tr></tbody>
      </table></div>
      <p style="font-size:12px;color:var(--muted);margin:var(--sp4) 0 0">${esc(tx(B(
        `Reconciles with the Dashboard only at the same period and catchment: ${N(m.booking)} ÷ ${N(m.real)} real enquiries = ${P(m.conversion)} conversion; ${N(m.spam)} ÷ ${N(m.total)} = ${P(m.spamRate)} spam.`,
        `Chỉ khớp với Bảng điều khiển khi cùng khoảng thời gian và cùng khu vực: ${N(m.booking)} ÷ ${N(m.real)} yêu cầu thật = ${P(m.conversion)} chuyển đổi; ${N(m.spam)} ÷ ${N(m.total)} = ${P(m.spamRate)} thư rác.`)))}</p>
    </div>`;
  },

  activities() {
    const groups = PRACTICE.activities.map((g) => `
      <div class="panel"><h3>${ic(g.icon)}${esc(tx(g.type))}<span class="chip" style="margin-left:auto">${g.n}</span></h3>
        <div class="rows">
          ${Array.from({ length: g.n }, (_, k) => `
            <div class="row"><span class="avatar">${ic(g.icon)}</span>
              <span><span class="nm">${esc(tx(k === 0 && g.icon === "phone"
                ? B("Call back Trần Mỹ Linh", "Gọi lại Trần Mỹ Linh")
                : B("Follow up enquiry", "Theo dõi yêu cầu tư vấn")))}</span><br>
                <span class="sub2">${esc(tx(B("Due 13 Aug · assigned to the CRM team", "Đến hạn 13/8 · giao cho nhóm CRM")))}</span></span>
            </div>`).join("")}
        </div></div>`).join("");
    return `<div class="tabs">
        <button aria-selected="true">${esc(T("all"))}</button>
        <button aria-selected="false">${esc(T("today"))}</button>
        <button aria-selected="false">${esc(T("week"))}</button>
        <button aria-selected="false">${esc(T("month"))}</button>
        <button class="btn sm pri" style="margin-left:auto">${ic("plus")}${esc(tx(B("Schedule activity", "Lên lịch hoạt động")))}</button>
      </div>
      <div class="grid g2">${groups}</div>
      <div class="panel"><p style="font-size:12.5px;color:var(--muted);margin:0">${esc(tx(B(
        `These ${CASE.kpis.pendingFollowups} open follow-ups are exactly the Dashboard's “Pending Follow-ups” card. If the two disagree, an activity was closed without the contact's status being updated.`,
        `${CASE.kpis.pendingFollowups} việc theo dõi đang mở này chính là thẻ “Đang chờ theo dõi” trên Bảng điều khiển. Nếu hai nơi lệch nhau, tức là một hoạt động đã được đóng mà chưa cập nhật trạng thái liên hệ.`)))}</p></div>`;
  },
};

/* --------------------------------------------------------------------------
   Row renderers. These read PRACTICE, never their own literals — that is what
   makes practice-data.js the single place to edit when the product changes.
   -------------------------------------------------------------------------- */
/* Vietnamese names put the given name last, so that is the initial to show. */
function initial(name) { const p = tx(name).trim().split(/\s+/); return ((p[p.length - 1] || "?")[0]).toUpperCase(); }
function statusChip(kind, key) {
  const s = (STATUS_LABELS[kind] || {})[key];
  return s ? `<span class="chip ${s.t}">${esc(tx(s.l))}</span>` : `<span class="chip">${esc(key)}</span>`;
}
function channelName(id) {
  const c = CASE.channels.find((x) => x.id === id);
  if (c) return tx(c.label);
  return { zns: "ZNS", whatsapp: "WhatsApp", telegram: "Telegram", email: "Email" }[id] || id;
}

function recentRows() {
  return PRACTICE.recent.map((r) => `
    <div class="row"><span class="avatar">${esc(initial(r.name))}</span>
      <span><span class="nm">${esc(tx(r.name))}</span><br><span class="sub2">${esc(tx(r.meta))}</span></span>
      <span class="rr"><span class="chip ${r.tone}">${esc(T("needsReply"))}</span></span></div>`).join("");
}

function wallRows() {
  return PRACTICE.conversations.map((r) => `
    <div class="row" ${r.anchor ? `data-a="${r.anchor}"` : ""}>
      <span class="urg ${r.urgency >= 90 ? "hi" : r.urgency >= 50 ? "md" : "lo"}">${r.urgency}</span>
      <span class="avatar">${esc(initial(r.name))}</span>
      <span><span class="nm">${esc(tx(r.name))} <span style="color:var(--faint);font-weight:400">#${r.id}</span></span><br>
        <span class="sub2">${esc(channelName(r.channel))} · ${esc(tx(r.note))}</span></span>
      <span class="rr">${statusChip("conversation", r.status)}</span>
    </div>`).join("");
}

function timelineHTML() {
  return PRACTICE.timeline.map((m) => {
    if (m.kind === "sys") return `<div class="bub sys">${esc(tx(m.text))}</div>`;
    return `<div class="bub ${m.kind}" ${m.anchor ? `data-a="${m.anchor}"` : ""}>${esc(tx(m.text))}
      ${m.ts ? `<span class="ts">${esc(m.ts)}</span>` : ""}</div>`;
  }).join("");
}

/* --------------------------------------------------------------- pipelines */
const CHAINS = {
  conv: {
    nodes: [B("Needs reply", "Cần trả lời"), B("Waiting", "Đang chờ"), B("Closed", "Đã đóng")],
    branch: B("Junk?", "Thư rác?"),
  },
  conn: {
    nodes: [B("Not connected", "Chưa kết nối"), B("Signing in", "Đang đăng nhập"),
            B("Choosing what to connect", "Chọn nội dung để kết nối"), B("Setting things up", "Đang thiết lập"),
            B("Testing", "Đang kiểm thử"), B("Connected", "Đã kết nối")],
    branch: B("Action required", "Cần xử lý"),
  },
  contact: {
    nodes: [B("New", "Mới"), B("Lead", "KHTN"), B("Appointment Scheduled", "Đã đặt lịch"), B("Service Used", "Đã dùng dịch vụ")],
    branch: B("Cancelled / Spam", "Đã hủy / Thư rác"),
  },
};
function pipeHTML(chain, active) {
  const c = CHAINS[chain];
  const parts = c.nodes.map((n, i) => `
    <span class="pn ${i === active ? "on" : i < active ? "past" : ""}" data-pn="${i}">
      ${i < active ? ic("check") : ""}${esc(tx(n))}</span>${i < c.nodes.length - 1 ? '<span class="pa"></span>' : ""}`).join("");
  return `<div class="pipe" data-chain="${chain}">${parts}
    <span class="pa"></span><span class="pn branch">${ic("git-branch")}${esc(tx(c.branch))}</span></div>`;
}
/* Animate a chain forward, one node at a time (instant under reduced motion). */
function runPipeline(root, chain) {
  const wrap = $(`.pipe[data-chain="${chain}"]`, root);
  if (!wrap) return;
  const nodes = $$(".pn[data-pn]", wrap);
  if (reduced()) { nodes.forEach((n, i) => n.className = "pn " + (i === nodes.length - 1 ? "on" : "past")); return; }
  let i = 0;
  const tick = () => {
    if (!document.body.contains(wrap)) return;
    nodes.forEach((n, k) => n.className = "pn " + (k === i ? "on" : k < i ? "past" : ""));
    i++;
    if (i < nodes.length) setTimeout(tick, 620);
  };
  tick();
}

/* --------------------------------------------------------------- morphs */
/* Morph: ONE state at a time with a toggle, so the change is felt rather than
   read side-by-side (DESIGN_SPEC §3.1). MORPH_STATE survives a re-render. */
let MORPH_STATE = "before";
const MORPHS = {
  junk: {
    before: { h: B("Before", "Trước"), big: CASE.urgencyTotal,
      d: B("On the wall · contact status “New” · number not flagged",
           "Trên bảng · trạng thái liên hệ “Mới” · số chưa bị ghi nhận") },
    after: { h: B("After “Junk?”", "Sau khi “Thư rác?”"), big: 0,
      d: B("Off the wall · contact status “Spam Call” · +84 912 345 678 flagged for every future call",
           "Rời khỏi bảng · trạng thái liên hệ “Cuộc gọi rác” · +84 912 345 678 bị ghi nhận cho mọi cuộc gọi sau"),
      delta: B("3 records changed, not 1", "3 bản ghi thay đổi, không phải 1") },
  },
  area: {
    before: { h: B("OA catchment = Hà Nội", "Khu vực OA = Hà Nội"), big: "12 · 7",
      d: B("Hà Nội wall open · HCMC wall open", "Bảng Hà Nội đang mở · Bảng TPHCM đang mở") },
    after: { h: B("OA catchment = TPHCM", "Khu vực OA = TPHCM"), big: "4 · 15",
      d: B("8 conversations move to a desk 1,700 km away that has never met these families",
           "8 cuộc hội thoại chuyển sang bàn cách 1.700 km, nơi chưa từng gặp các gia đình này"),
      delta: B("No error. No warning. Just a quiet morning.", "Không lỗi. Không cảnh báo. Chỉ là một buổi sáng yên ắng.") },
  },
};
function morphHTML(which) {
  const m = MORPHS[which], k = MORPH_STATE, s = m[k];
  return `<div class="morph one" data-morph="${which}">
    <div class="seg" style="margin-bottom:var(--sp3)">
      <button data-act="morph-before" aria-pressed="${k === "before"}">${esc(tx(m.before.h))}</button>
      <button data-act="morph-after" aria-pressed="${k === "after"}">${esc(tx(m.after.h))}</button>
    </div>
    <div class="side ${k === "after" ? "after" : ""}">
      <h4>${esc(tx(s.h))}</h4>
      <div class="big">${s.big}</div>
      <div style="font-size:12px">${esc(tx(s.d))}</div>
      ${s.delta ? `<div class="delta">${esc(tx(s.delta))}</div>` : ""}
    </div>
  </div>`;
}

function calcHTML(dark) {
  const rows = CASE.urgency.map((t) => `<div class="cr"><span>${esc(tx(t.k))}</span><b>+${t.v}</b></div>`).join("");
  return `<div class="calc">${rows}<div class="cr tot"><span>${esc(tx(B("Urgency score", "Điểm ưu tiên")))}</span><b>${CASE.urgencyTotal}</b></div></div>`;
}
function calcKpiHTML() {
  const m = CASE.month;
  const rows = [
    [B("Enquiries this month", "Yêu cầu trong tháng"), N(m.total)],
    [B("less spam", "trừ thư rác"), "− " + N(m.spam)],
    [B("Real enquiries (denominator)", "Yêu cầu thật (mẫu số)"), N(m.real)],
    [B("Converted to a booking", "Đã chuyển thành lịch hẹn"), N(m.booking)],
  ].map(([l, v]) => `<div class="cr"><span>${esc(tx(l))}</span><b>${v}</b></div>`).join("");
  return `<div class="calc">${rows}
    <div class="cr tot"><span>${N(m.booking)} ÷ ${N(m.real)}</span><b>${P(m.conversion)}</b></div></div>`;
}

/* =============================================================================
   HUB
   ========================================================================== */
const MODES = [
  ["grad-cap", B("Give me the complete guided journey", "Cho tôi toàn bộ hành trình hướng dẫn"), "full"],
  ["users", B("Teach me only what my role needs", "Chỉ dạy những gì vai trò của tôi cần"), "role"],
  ["target", B("Help me finish today's task", "Giúp tôi hoàn thành việc hôm nay"), "task"],
  ["compass", B("Let me explore independently", "Để tôi tự khám phá"), "explore"],
  ["award", B("Test what I already know", "Kiểm tra xem tôi đã biết gì"), "test"],
];

const HubView = {
  render() {
    const done = countDone();
    APP.innerHTML = topbarHTML(true) + `<div class="wrap hub">
      <h1>${esc(T("hubTitle"))}</h1>
      <p class="lead">${esc(T("hubLead"))}</p>
      ${S.last && S.visited && !S.last.hash.startsWith("#/hub") && S.last.hash !== "" ? `<div class="resume">${ic("rotate-ccw")}
        <span><b>${esc(T("resumeAt"))}</b><br><span style="color:var(--muted);font-size:12.5px">${esc(S.last.label)}</span></span>
        <button class="btn pri sm" data-go="${esc(S.last.hash)}">${esc(T("resume"))}</button></div>` : ""}
      <div class="slbl" style="font-weight:800;font-size:13px;margin-bottom:var(--sp3)">${esc(T("modeQ"))}</div>
      <div class="modes">${MODES.map(([i, l, k]) => `
        <button class="mode" data-act="mode-${k}" aria-pressed="${S.mode === k}">
          <span class="mi">${ic(i, "ic-lg")}</span><b>${esc(tx(l))}</b></button>`).join("")}</div>
      <div class="cards">
        ${hubCard("j", "map", T("journey"), T("journeyTag"),
          tx(B("A station map over the eight CRM screens. Cinematic lessons spotlight the real controls, trace how one setting produces one number, and end with a judgement check — not a Next button.",
               "Bản đồ trạm cho tám màn hình CRM. Các bài học dạng điện ảnh chiếu sáng đúng nút thật, vẽ đường nối từ một thiết lập tới một con số, và kết thúc bằng một tình huống phán đoán — không phải nút Tiếp theo.")),
          "#/journey", `${done}/8 ${tx(B("stations", "trạm"))}`)}
        ${hubCard("s", "flask", T("sim"), T("simTag"),
          tx(B("A clearly-marked practice clinic with realistic Hà Nội data. Consequence previews before every risky action, one seeded judgement per mission, mistake recovery, and a confidence score earned by deciding.",
               "Một phòng thực hành được đánh dấu rõ ràng với dữ liệu Hà Nội thực tế. Cảnh báo hệ quả trước mọi thao tác rủi ro, mỗi nhiệm vụ có một tình huống phán đoán được gài, có phần khôi phục khi sai, và mức tự tin kiếm được bằng việc ra quyết định.")),
          "#/sim", `${Object.keys(S.missions).length}/2 ${tx(B("missions", "nhiệm vụ"))}`)}
        ${hubCard("c", "bot", T("comp"), T("compTag"),
          tx(B("A dock on every CRM screen. It answers from CareJioX's own content with numbered steps that point at the real control, calculation breakdowns, role-aware refusals — and it never claims to have acted for you.",
               "Một khung trợ lý trên mọi màn hình CRM. Nó trả lời dựa trên nội dung của chính CareJioX với các bước đánh số trỏ tới đúng nút thật, bảng phân tích con số, lời từ chối trung thực theo vai trò — và không bao giờ nhận là đã thao tác thay bạn.")),
          "#/companion", "")}
      </div>
      <div class="note">${ic("info")}<span>${esc(tx(B(
        "All three surfaces run on one content spine and one simulated CMS shell — the real CRM menu inventory, the real urgency arithmetic, one worked Hà Nội case whose every number reconciles. Progress, role and language survive a refresh.",
        "Cả ba bề mặt chạy trên một trục nội dung và một vỏ CMS mô phỏng — đúng danh mục menu CRM thật, đúng phép tính điểm ưu tiên thật, một tình huống Hà Nội mẫu mà mọi con số đều khớp. Tiến độ, vai trò và ngôn ngữ được giữ lại sau khi tải lại trang.")))}
        &nbsp;<a href="analysis.html">${esc(T("readAnalysis"))}</a>.</span></div>
    </div>`;
    setLast(tx(B("Concept hub", "Trang tổng quan")));
  },
  onAct(name) {
    if (name.startsWith("mode-")) {
      S.mode = name.slice(5); save(); this.render();
      toast(tx(B("Starting mode saved. It shapes what the journey suggests first.",
                 "Đã lưu chế độ bắt đầu. Nó quyết định hành trình gợi ý gì trước tiên.")), "ok", "check");
    }
  },
};
function hubCard(k, icn, title, kick, body, href, meta) {
  const art = k === "j"
    ? `<span class="bar" style="left:12%;top:52%;width:76%;height:3px;background:#B9CFEC"></span>
       ${[18, 38, 58, 78].map((x, i) => `<span class="dot" style="left:${x}%;top:calc(52% - ${i === 3 ? 9 : 5}px);width:${i === 3 ? 18 : 10}px;height:${i === 3 ? 18 : 10}px;background:${i === 3 ? "#1565C0" : "#7FA9DD"}"></span>`).join("")}`
    : k === "s"
      ? `<span class="box" style="left:14%;top:24%;width:32%;height:52%"></span>
         <span class="box" style="left:54%;top:24%;width:32%;height:22%"></span>
         <span class="dot" style="left:46%;top:52%;width:20px;height:20px;background:#10B981"></span>`
      : `<span class="box" style="left:12%;top:26%;width:46%;height:16%"></span>
         <span class="box" style="left:12%;top:50%;width:62%;height:26%"></span>
         <span class="dot" style="left:80%;top:22%;width:26px;height:26px;background:#1565C0"></span>`;
  return `<div class="card">
    <div class="art ${k}">${art}</div>
    <div class="body">
      <h3>${ic(icn, "ic-lg")}${esc(title)}</h3>
      <div class="kick">${esc(kick)}</div>
      <p>${esc(body)}</p>
      <div class="go"><button class="btn pri" data-go="${href}">${esc(T("explore"))}${ic("arrow-right")}</button>
        ${meta ? `<span class="chip" style="margin-left:8px">${esc(meta)}</span>` : ""}</div>
    </div></div>`;
}

function topbarHTML(hub, backHash, label) {
  const langs = ["en", "vi"].map((l) => `<button data-act="lang-${l}" aria-pressed="${S.lang === l}">${l.toUpperCase()}</button>`).join("");
  const roles = ["crm", "nurse", "om", "owner"].map((r) =>
    `<button data-act="role-${r}" aria-pressed="${S.role === r}" title="${esc(T("roles")[r])}">${esc(T("rolesShort")[r])}</button>`).join("");
  return `<div class="top">
    ${hub ? `<span class="logo"><span class="mark">${ic("heart")}</span>CareJioX <span class="learn">${esc(T("learn"))}</span></span>
             <span class="tag">${esc(T("proto"))}</span>`
          : `<button class="btn ghost sm" data-go="${backHash || "#/hub"}">${ic("chevron-left")}${esc(T("allConcepts"))}</button>
             <span class="logo" style="font-size:14px">${ic("map", "ic-lg")}${esc(label || "")}</span>
             <span class="tag">${esc(T("proto"))}</span>`}
    <span class="spacer"></span>
    <span class="seg" role="group" aria-label="${esc(T("langNote"))}">${langs}</span>
    <span class="seg" role="group" aria-label="${esc(T("roleNote"))}">${roles}</span>
    <button class="btn ghost sm" data-act="motion" aria-pressed="${S.motion === "reduced"}">
      ${ic(S.motion === "reduced" ? "pause" : "play")}${esc(S.motion === "reduced" ? T("motionOn") : T("reduceMotion"))}</button>
    ${hub ? `<a class="btn ghost sm" href="analysis.html">${ic("book-open")}${esc(T("readAnalysis"))}</a>
             <button class="btn ghost sm" data-act="reset">${ic("rotate-ccw")}${esc(T("reset"))}</button>` : ""}
  </div>`;
}

/* =============================================================================
   JOURNEY
   ========================================================================== */
function allStations() {
  return [].concat(STATIONS.daily.stations, STATIONS.reach.stations);
}
function countDone() { return allStations().filter((s) => S.done[s.id]).length; }
function nextStation() {
  const all = allStations();
  return all.find((s) => !S.done[s.id] && s.lesson) || all.find((s) => !S.done[s.id]) || null;
}

const JourneyView = {
  q: "",
  render() {
    const all = allStations(), done = countDone();
    const nx = nextStation();
    const badge = S.done.carecommand && S.done.channelcenter;
    const linesHTML = ["daily", "reach"].map((key) => {
      const L = STATIONS[key];
      const list = L.stations.filter((s) => {
        if (!this.q) return true;
        const hay = (tx(s.title) + " " + tx(s.desc)).toLowerCase();
        return hay.indexOf(this.q.toLowerCase()) !== -1;
      });
      const dn = L.stations.filter((s) => S.done[s.id]).length;
      if (!list.length) return "";
      return `<section class="line">
        <header>${ic(L.icon)}<h2>${esc(S.lang === "vi" ? L.labelVi : L.label)}</h2>
          <span class="meter" style="width:128px"><i style="width:${(dn / L.stations.length * 100).toFixed(0)}%"></i></span>
          <span class="cnt">${dn}/${L.stations.length}</span></header>
        <div class="ldesc">${esc(tx(L.desc))}</div>
        <div class="stations">${list.map((s) => this.stn(s, nx)).join("")}</div>
      </section>`;
    }).join("");
    APP.innerHTML = topbarHTML(false, "#/hub", T("journey")) + `<div class="wrap">
      <div class="jhead">
        <div><h1>${esc(T("yourJourney"))}</h1>
          <p class="lead">${esc(tx(B(
            "Two lines over the eight CRM screens. Finish the two ★ flagship lessons to earn the CRM Desk badge; everything else is an outline you can read now and a full lesson later.",
            "Hai tuyến cho tám màn hình CRM. Hoàn thành hai bài học chủ đạo ★ để nhận huy hiệu Bàn CRM; những mục còn lại là đề cương bạn đọc được ngay và sẽ có bài học đầy đủ sau.")))}</p></div>
        <div class="prog"><div class="row"><span>${esc(T("overall"))}</span><span>${Math.round(done / all.length * 100)}%</span></div>
          <div class="meter"><i style="width:${(done / all.length * 100).toFixed(0)}%"></i></div>
          <div style="font-size:12px;color:var(--muted);margin-top:6px">${done}/${all.length} ${esc(tx(B("stations", "trạm")))}</div></div>
      </div>
      <div class="searchbox">${ic("search")}<input type="search" data-act="jsearch" placeholder="${esc(T("search"))}" value="${esc(this.q)}"/></div>
      ${linesHTML || `<div class="panel">${esc(tx(B("No station matches that search.", "Không có trạm nào khớp với tìm kiếm đó.")))}</div>`}
      <div class="badge ${badge ? "on" : ""}">${ic(badge ? "award" : "lock", "ic-lg")}
        <span>${esc(badge ? T("badgeGot") : tx(B("Complete both ★ flagship lessons — Care Command and Channel Center — to earn the CRM Desk badge.",
          "Hoàn thành cả hai bài học chủ đạo ★ — Care Command và Trung tâm kênh — để nhận huy hiệu Bàn CRM.")))}</span></div>
    </div>`;
    setLast(T("journey"));
  },
  stn(s, nx) {
    const done = !!S.done[s.id], isNext = nx && nx.id === s.id;
    return `<button class="stn ${done ? "done" : ""} ${isNext ? "next" : ""}" data-act="open-${s.id}">
      <span class="node"></span><span class="sic">${ic(s.icon)}</span>
      <span class="sbody">
        <span class="t"><b>${esc(tx(s.title))}</b>
          ${s.lesson ? `<span class="chip b">${ic("star")}${esc(T("fullLesson"))}</span>` : `<span class="chip a">${esc(T("outline"))}</span>`}
          ${s.required ? `<span class="chip">${esc(T("required"))}</span>` : `<span class="chip">${esc(T("optional"))}</span>`}
          ${done ? `<span class="chip g">${ic("check")}${esc(T("missionDone"))}</span>` : ""}</span>
        <span class="d">${esc(tx(s.desc))}</span>
        <span class="meta"><span class="chip">${ic("clock")}${esc(T("est"))} ${s.mins} ${esc(T("min"))}</span>
          ${s.after ? `<span class="chip a">${ic("alert-triangle")}${esc(T("after"))} ${esc(tx(allStations().find((x) => x.id === s.after).title))}</span>` : ""}</span>
      </span>
      <span class="go">${ic("chevron-right")}</span></button>`;
  },
  onChange(name, el) { if (name === "jsearch") { this.q = el.value; this.render(); $("[data-act=jsearch]").focus(); } },
  onAct(name) {
    if (!name.startsWith("open-")) return;
    const id = name.slice(5);
    const s = allStations().find((x) => x.id === id);
    if (s.lesson) { location.hash = "#/journey/lesson/" + s.lesson; return; }
    OutlineView.open(s);
  },
};

/* --------------------------------------------------------------- outlines */
const OutlineView = {
  open(s) {
    const o = s.outline;
    const box = openModal(`
      <h3>${ic(s.icon, "ic-lg")} ${esc(tx(s.title))}</h3>
      <div class="cal warn" style="margin-bottom:var(--sp4)">${ic("info")}<span>${esc(T("outlineNote"))}</span></div>
      ${["whatIs:what", "whyMatters:why", "whenUse:when", "prereq:prereq"].map((p) => {
        const [k, f] = p.split(":");
        return `<div style="margin-bottom:var(--sp4)">
          <div class="slbl" style="color:var(--primary)">${esc(T(k))}</div>
          <p style="margin:0;font-size:13px">${esc(tx(o[f]))}</p></div>`;
      }).join("")}
      <div class="slbl" style="color:var(--warn)">${esc(T("mistakes"))}</div>
      <ul style="font-size:13px;padding-left:20px;margin:0">${o.mistakes.map((m) => `<li style="margin-bottom:6px">${esc(tx(m))}</li>`).join("")}</ul>
      <div class="mfoot">
        <button class="btn" data-act="ol-coach-${s.id}">${ic("bot")}${esc(T("askCoach"))}</button>
        <button class="btn pri" data-act="ol-done-${s.id}">${ic("check")}${esc(tx(B("Mark as read", "Đánh dấu đã đọc")))}</button>
      </div>`);
    box.focus();
  },
};

/* =============================================================================
   LESSON PLAYER
   ========================================================================== */
const LessonView = {
  lesson: null, i: 0, quiz: false, answered: null, playing: false, timer: null,
  open(id) {
    this.lesson = LESSONS[id];
    if (!this.lesson) { location.hash = "#/journey"; return; }
    this.i = (S.lessonPos[id] || 0);
    if (this.i >= this.lesson.steps.length) this.i = 0;
    MORPH_STATE = "before";
    this.quiz = false; this.answered = null;
    this.renderStep();
  },
  words(step) { return (tx(step.title) + " " + tx(step.body)).replace(/<[^>]+>/g, "").split(/\s+/).length; },
  renderStep() {
    const L = this.lesson;
    if (this.quiz) return this.renderQuiz();
    const st = L.steps[this.i];
    APP.innerHTML = shellHTML(st.screen, { guided: true });
    const nav = `<div class="cfoot">
        <span class="cmeter"><i style="width:${((this.i + 1) / L.steps.length * 100).toFixed(0)}%"></i></span>
        <span class="cstep">${esc(T("step"))} ${this.i + 1} ${esc(T("of"))} ${L.steps.length}</span></div>
      <div class="cbtns">
        <button class="btn sm" data-act="l-back" ${this.i === 0 ? "disabled" : ""}>${ic("chevron-left")}${esc(T("back"))}</button>
        <button class="btn sm pri" data-act="l-next">${esc(this.i === L.steps.length - 1 ? T("check") : T("next"))}${ic("chevron-right")}</button>
        <button class="btn sm ghost" data-act="l-replay" title="${esc(T("replay"))}">${ic("rotate-ccw")}</button>
      </div>`;
    let moment = "";
    if (st.moment) {
      if (st.moment.kind === "calc") moment = `<div class="moment">${calcHTML(true)}</div>`;
      else if (st.moment.kind === "morph") moment = `<div class="moment">${morphHTML(st.moment.which)}</div>`;
      else if (st.moment.kind === "pipeline") moment = `<div class="moment">${pipeHTML(st.moment.chain, 0)}</div>`;
    }
    // Playbar first: Spot.position() reserves the strip it occupies.
    let pb = $(".playbar");
    if (!pb) { pb = document.createElement("div"); pb.className = "playbar"; OVER.appendChild(pb); }
    Spot.show(st.anchor, `
      <div class="kick">${ic("sparkles")}${esc(tx(st.kicker))}</div>
      <h3>${esc(tx(st.title))}</h3>
      <div class="cbody">${tx(st.body)}</div>
      ${st.consequence ? `<div class="cq"><b>${esc(T("consequence"))}</b><br>${esc(tx(st.consequence))}</div>` : ""}
      ${st.tip ? `<div class="ct2"><b>${esc(T("tip"))}</b> ${esc(tx(st.tip))}</div>` : ""}
      ${moment}${nav}`);
    pb.innerHTML = `
      <button data-act="l-exit" title="${esc(T("exit"))}">${ic("x")}</button>
      <button data-act="l-back" title="${esc(T("back"))}">${ic("chevron-left")}</button>
      <button data-act="l-play" title="${esc(this.playing ? T("paused") : T("playing"))}">${ic(this.playing ? "pause" : "play")}</button>
      <button data-act="l-next" title="${esc(T("next"))}">${ic("chevron-right")}</button>
      <span class="n">${esc(T("step"))} ${this.i + 1} / ${L.steps.length}</span>
      <button data-act="l-quiz" title="${esc(T("skipQuiz"))}">${ic("skip-forward")}</button>`;
    // moments that animate after paint
    setTimeout(() => {
      if (!st.moment) return;
      if (st.moment.kind === "trace") Trace.run(st.moment.from, st.moment.to);
      if (st.moment.kind === "pipeline") runPipeline(Spot.card, st.moment.chain);
    }, reduced() ? 0 : 480);
    S.lessonPos[L.id] = this.i; save();
    setLast(tx(B("Lesson: ", "Bài học: ")) + tx(allStations().find((s) => s.lesson === L.id).title) + " · " + T("step") + " " + (this.i + 1));
    this.arm();
  },
  arm() {
    clearTimeout(this.timer);
    if (!this.playing || this.quiz) return;
    const ms = Math.max(4200, this.words(this.lesson.steps[this.i]) * 260);
    this.timer = setTimeout(() => this.next(), ms);
  },
  next() {
    MORPH_STATE = "before";
    if (this.i < this.lesson.steps.length - 1) { this.i++; this.renderStep(); }
    else { this.quiz = true; this.playing = false; this.renderQuiz(); }
  },
  back() { MORPH_STATE = "before"; if (this.i > 0) { this.i--; this.renderStep(); } },
  renderQuiz() {
    clearTimeout(this.timer);
    const q = this.lesson.quiz, L = this.lesson;
    const st = allStations().find((s) => s.lesson === L.id);
    Spot.hide(); const pb = $(".playbar"); if (pb) pb.remove();
    APP.innerHTML = topbarHTML(false, "#/journey", T("journey")) + `<div class="wrap"><div class="quiz">
      <div class="slbl" style="color:var(--primary)">${esc(T("check"))} · ${esc(tx(st.title))}</div>
      <div class="q">${esc(tx(q.question))}</div>
      <div style="font-size:12.5px;color:var(--muted);margin-bottom:var(--sp4)">${esc(T("checkNote"))}</div>
      <div id="opts">${q.options.map((o, i) => `
        <button class="opt" data-act="q-${i}">${esc(tx(o.text))}</button>`).join("")}</div>
      <div id="qfoot"></div>
    </div></div>`;
    setLast(tx(B("Understanding check", "Kiểm tra hiểu bài")));
  },
  answer(i) {
    const q = this.lesson.quiz, o = q.options[i], L = this.lesson;
    const btns = $$("#opts .opt");
    btns[i].classList.add(o.correct ? "right" : "wrong");
    btns[i].insertAdjacentHTML("beforeend",
      `<div class="exp"><b>${esc(o.correct ? T("correct") : T("rethink"))}</b> ${esc(tx(o.explanation))}</div>`);
    if (o.correct) {
      btns.forEach((b, k) => { if (k !== i) b.disabled = true; });
      const st = allStations().find((s) => s.lesson === L.id);
      S.done[st.id] = true; save();
      const nx = nextStation();
      $("#qfoot").innerHTML = `<div class="cal ok" style="margin-top:var(--sp4)">${ic("check-circle")}
          <span>${esc(tx(B("Station complete — credited because you judged it, not because you clicked Next.",
                            "Hoàn thành trạm — được ghi nhận vì bạn đã phán đoán, không phải vì bạn bấm Tiếp theo.")))}</span></div>
        <div class="mfoot" style="justify-content:flex-start">
          ${nx ? `<button class="btn pri" data-act="q-next">${esc(tx(B("Next: ", "Tiếp theo: ")))}${esc(tx(nx.title))}${ic("arrow-right")}</button>` : ""}
          <button class="btn" data-go="#/sim">${ic("flask")}${esc(T("practiceHere"))}</button>
          <button class="btn ghost" data-go="#/journey">${esc(tx(B("Back to the map", "Về bản đồ")))}</button></div>`;
      $("#qfoot").scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
    } else {
      S.quizTries[L.id] = (S.quizTries[L.id] || 0) + 1; save();
      btns[i].disabled = true;
      $("#qfoot").innerHTML = `<div class="recov" style="margin-top:var(--sp3)">
        <h4>${ic("rotate-ccw")} ${esc(T("tryAgain"))}</h4>
        <div>${esc(tx(B("Nothing is scored against you. Re-read the two remaining options with the consequence in mind.",
                        "Không có gì bị trừ điểm. Hãy đọc lại hai phương án còn lại với hệ quả vừa nêu trong đầu.")))}</div></div>
        ${S.quizTries[L.id] >= 2 ? `<div class="mfoot" style="justify-content:flex-start">
          <button class="btn" data-act="q-simpler">${ic("lightbulb")}${esc(T("simpler"))}</button>
          <button class="btn" data-go="#/sim">${ic("flask")}${esc(T("letMePractise"))}</button></div>` : ""}`;
    }
  },
  onAct(name) {
    if (name === "l-next") { this.playing = false; this.next(); return; }
    if (name === "l-back") { this.playing = false; this.back(); return; }
    if (name === "l-replay") { this.renderStep(); return; }
    if (name === "l-quiz") { this.quiz = true; this.playing = false; this.renderQuiz(); return; }
    if (name === "l-exit") { clearTimeout(this.timer); location.hash = "#/journey"; return; }
    if (name === "l-play") { this.playing = !this.playing; this.renderStep(); return; }
    if (name.startsWith("q-")) {
      const r = name.slice(2);
      if (r === "next") { const nx = nextStation(); if (nx && nx.lesson) location.hash = "#/journey/lesson/" + nx.lesson; else location.hash = "#/journey"; return; }
      if (r === "simpler") {
        openModal(`<h3>${ic("lightbulb", "ic-lg")} ${esc(T("simpler"))}</h3>
          <p style="font-size:13.5px">${esc(tx(this.lesson.id === "L1"
            ? B("Two questions, in this order. First: how fast must I answer? (Very — 110.) Second: what am I allowed to say to this particular person? (Nothing clinical — the patient said no in June.) Answer fast, say little, and pass the medical question to someone qualified.",
                "Hai câu hỏi, theo thứ tự này. Một: tôi phải trả lời nhanh thế nào? (Rất nhanh — 110 điểm.) Hai: tôi được nói gì với đúng người này? (Không nói gì về lâm sàng — bệnh nhân đã từ chối hồi tháng 6.) Hãy trả lời nhanh, nói ít, và chuyển câu hỏi y khoa cho người có chuyên môn.")
            : B("If work vanished, a channel is down. If work moved to another team, a channel is pointing at the wrong area. Both walls are healthy here and the volume simply changed hands — so look at the account each connection is pointing at.",
                "Nếu công việc biến mất, tức là một kênh đang ngừng. Nếu công việc chuyển sang nhóm khác, tức là một kênh đang trỏ nhầm khu vực. Ở đây cả hai bảng đều khỏe mạnh và khối lượng chỉ đổi chủ — nên hãy xem mỗi kết nối đang trỏ tới tài khoản nào.")))}</p>
          <div class="mfoot"><button class="btn pri" data-act="closemodal">${esc(T("continueBtn"))}</button></div>`);
        return;
      }
      this.answer(parseInt(r, 10));
    }
  },
  onKey(e) {
    if (this.quiz) return;
    if (e.key === "ArrowRight") { this.playing = false; this.next(); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { this.playing = false; this.back(); e.preventDefault(); }
    else if (e.key === " ") { this.playing = !this.playing; this.renderStep(); e.preventDefault(); }
    else if (e.key === "Escape") { clearTimeout(this.timer); location.hash = "#/journey"; }
  },
};

/* =============================================================================
   SIMULATOR
   ========================================================================== */
const SimView = {
  mission: null, i: 0, usedRecovery: false, hint: false,
  render() {
    const confRows = Object.keys(S.conf).length
      ? Object.keys(S.conf).map((k) => `<div class="confbar"><span>${esc(CONF_LABEL[k] ? tx(CONF_LABEL[k]) : k)}</span>
          <span class="meter g"><i style="width:${Math.min(100, S.conf[k])}%"></i></span><b>${S.conf[k]}%</b></div>`).join("")
      : `<p style="color:var(--muted);font-size:13px;margin:0">${esc(tx(B("No confidence earned yet — it is earned by deciding, not by reading.",
          "Chưa có mức tự tin nào — nó kiếm được bằng việc ra quyết định, không phải bằng việc đọc.")))}</p>`;
    APP.innerHTML = topbarHTML(false, "#/hub", T("sim")) + `<div class="wrap">
      <div class="pbanner" style="border-radius:var(--r-sm);margin-bottom:var(--sp5);border:1px solid #BFE7D6">
        ${ic("shield-check")}<span>${esc(T("practiceBanner"))}</span></div>
      <div class="jhead"><div><h1>${esc(T("missions"))}</h1><p class="lead">${esc(T("missionsLead"))}</p></div></div>
      <div class="mcards">${MISSIONS.map((m) => this.card(m)).join("")}</div>
      <div class="panel" style="margin-top:var(--sp5)"><h3>${ic("trending-up")}${esc(T("confidence"))}</h3>
        <div class="confbars">${confRows}</div></div>
    </div>`;
    setLast(T("sim"));
  },
  card(m) {
    const done = S.missions[m.id];
    return `<div class="mcard">
      <h3>${ic(m.icon, "ic-lg")}${esc(tx(m.title))}
        ${m.full ? "" : `<span class="chip a">${esc(T("outlineMission"))}</span>`}
        ${done ? `<span class="chip g">${ic("check")}${esc(T("missionDone"))}</span>` : ""}</h3>
      <p>${esc(tx(m.desc))}</p>
      ${m.outlineNote ? `<div class="cal warn">${ic("info")}<span>${esc(tx(m.outlineNote))}</span></div>` : ""}
      <div class="meta" style="display:flex;gap:6px;flex-wrap:wrap">
        <span class="chip">${ic("clock")}${esc(T("est"))} ${m.mins} ${esc(T("min"))}</span>
        <span class="chip b">${esc(T("confidence"))} +${m.conf.gain}</span></div>
      <div class="go"><button class="btn ${m.full ? "pri" : ""}" ${m.full ? "" : "disabled"} data-act="m-start-${m.id}">
        ${ic("play")}${esc(T("startMission"))}</button></div>
    </div>`;
  },
  start(id) {
    this.mission = MISSIONS.find((m) => m.id === id);
    this.i = 0; this.usedRecovery = false; this.hint = false;
    this.renderMission();
  },
  renderMission() {
    const m = this.mission, st = m.steps[this.i];
    if (!st) return this.debrief();
    APP.innerHTML = shellHTML(st.nav || this.screenFor(), { guided: true, practice: true });
    $$(".glow").forEach((e) => e.classList.remove("glow"));
    if (st.target) { const el = $(`[data-a="${st.target}"]`); if (el) { el.classList.add("glow"); el.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" }); } }
    const box = document.createElement("div");
    box.className = "mstep"; box.setAttribute("aria-live", "polite");
    box.innerHTML = `
      <div class="kick">${esc(tx(m.title))} · ${esc(T("step"))} ${this.i + 1}/${m.steps.length}</div>
      <h4>${esc(tx(st.instruction))}</h4>
      <p>${esc(tx(st.detail))}</p>
      ${this.hint ? `<div class="hintbox">${ic("lightbulb")} ${esc(tx(st.hint))}</div>` : ""}
      ${st.options ? `<div class="opts">${st.options.map((o) => `<button data-act="m-opt-${o.id}">${esc(tx(o.label))}</button>`).join("")}</div>`
        : `<div style="display:flex;gap:8px;flex-wrap:wrap">
             <button class="btn sm pri" data-act="m-do">${ic("check")}${esc(tx(B("Do it", "Thực hiện")))}</button>
             ${this.hint ? "" : `<button class="btn sm" data-act="m-hint">${ic("help-circle")}${esc(T("showHint"))}</button>`}
             <button class="btn sm ghost" data-act="m-quit">${esc(tx(B("Leave", "Thoát")))}</button>
           </div>`}`;
    OVER.appendChild(box);
    // Never cover the control being taught (DESIGN_SPEC §6): if the glowing
    // target sits under the step panel, move the panel to the other corner.
    if (st.target) {
      const el = $(`[data-a="${st.target}"]`);
      if (el) {
        const r = el.getBoundingClientRect(), p = box.getBoundingClientRect();
        if (!(r.right < p.left || r.left > p.right || r.bottom < p.top || r.top > p.bottom)) {
          box.style.right = "auto"; box.style.left = "20px";
        }
      }
    }
    mountCoachLauncher(st.nav || this.screenFor());
    setLast(tx(B("Mission: ", "Nhiệm vụ: ")) + tx(m.title) + " · " + T("step") + " " + (this.i + 1));
  },
  screenFor() {
    for (let k = this.i; k >= 0; k--) if (this.mission.steps[k].nav) return this.mission.steps[k].nav;
    return "carecommand";
  },
  advance() { this.i++; this.hint = false; this.renderMission(); },
  doStep() {
    const st = this.mission.steps[this.i];
    if (st.consequence) return this.showConsequence();
    if (st.undo) {
      toast(tx(B("Undo demonstrated — and it is audited.", "Đã minh họa hoàn tác — và nó được ghi nhật ký.")), "ok", "rotate-ccw");
    }
    this.advance();
  },
  showConsequence() {
    const c = this.mission.consequence;
    openModal(`<div class="conseq">
        <h4>${ic("alert-triangle")}${esc(tx(c.title))}</h4>
        <dl>
          <dt>${esc(T("scope"))}</dt><dd>${esc(tx(c.scope))}</dd>
          <dt>${esc(T("reversible"))}</dt><dd>${esc(tx(c.reversible))}</dd>
          <dt>${esc(T("verify"))}</dt><dd>${esc(tx(c.verify))}</dd>
        </dl></div>
      <div class="mfoot">
        <button class="btn" data-act="closemodal">${esc(T("cancelAct"))}</button>
        <button class="btn pri" data-act="m-proceed">${esc(T("proceed"))}</button></div>`, { dismissable: false });
  },
  choose(optId) {
    const st = this.mission.steps[this.i];
    const o = st.options.find((x) => x.id === optId);
    if (o.correct) { this.advance(); return; }
    this.usedRecovery = true;
    openModal(`<div class="recov">
        <h4>${ic("rotate-ccw")} ${esc(T("rethink"))}</h4>
        <div>${tx(st.recovery[optId])}</div></div>
      <div class="mfoot"><button class="btn pri" data-act="closemodal">${esc(tx(B("Let me choose again", "Cho tôi chọn lại")))}</button></div>`);
  },
  debrief() {
    const m = this.mission;
    const gain = this.usedRecovery ? Math.round(m.conf.gain * 0.6) : m.conf.gain;
    S.missions[m.id] = true;
    S.conf[m.conf.key] = Math.min(100, (S.conf[m.conf.key] || 0) + gain);
    save();
    $$(".mstep").forEach((e) => e.remove());
    APP.innerHTML = topbarHTML(false, "#/sim", T("sim")) + `<div class="wrap"><div class="quiz debrief">
      <div class="slbl" style="color:var(--primary)">${esc(T("debriefTitle"))}</div>
      <h1 style="font-size:22px;margin-bottom:var(--sp4)">${esc(tx(m.title))}</h1>
      <div class="cal warn" style="margin-bottom:var(--sp5)">${ic("alert-triangle")}
        <span><b>${esc(tx(m.anomaly.title))}</b><br>${esc(tx(m.anomaly.body))}</span></div>
      <div class="slbl">${esc(T("whatYouDid"))}</div>
      <ul>${m.debrief.did.map((d) => `<li>${esc(tx(d))}</li>`).join("")}</ul>
      <div class="slbl">${esc(T("checklist"))}</div>
      <ul>${m.debrief.checklist.map((d) => `<li>${esc(tx(d))}</li>`).join("")}</ul>
      <div class="panel" style="background:var(--ok-bg);border-color:#BFE7D6">
        <div style="display:flex;align-items:center;gap:var(--sp3)">
          ${ic("trending-up", "ic-xl")}
          <div><b>${esc(T("confGain"))}: +${gain}%</b>
          <div style="font-size:12.5px;color:var(--ok-ink)">${esc(CONF_LABEL[m.conf.key] ? tx(CONF_LABEL[m.conf.key]) : m.conf.key)}
            ${this.usedRecovery ? " · " + esc(T("recoveryUsed")) : ""}</div></div></div></div>
      <div class="cal ok">${ic("rotate-ccw")}<span>${esc(T("undoShown"))} — ${esc(tx(B(
        "you saw where the way back is, and what it costs.", "bạn đã thấy lối quay lại ở đâu, và cái giá của nó.")))}</span></div>
      <div class="mfoot" style="justify-content:flex-start">
        <button class="btn pri" data-go="#/sim">${esc(T("backToMissions"))}</button>
        <button class="btn" data-go="#/companion">${ic("bot")}${esc(T("comp"))}</button></div>
    </div></div>`;
  },
  onAct(name) {
    if (name.startsWith("m-start-")) { this.start(name.slice(8)); return; }
    if (name === "m-do") { this.doStep(); return; }
    if (name === "m-hint") { this.hint = true; this.renderMission(); return; }
    if (name === "m-quit") { this.mission = null; $$(".mstep").forEach((e) => e.remove()); this.render(); return; }
    if (name === "m-proceed") { closeModal(); this.advance(); return; }
    if (name.startsWith("m-opt-")) { this.choose(name.slice(6)); return; }
  },
  nav() { toast(tx(B("The mission drives navigation — follow the highlighted control.",
                     "Nhiệm vụ điều hướng thay bạn — hãy theo nút đang được làm nổi.")), "", "info"); },
};
const CONF_LABEL = {
  triage: B("Triage & replying safely", "Phân loại ưu tiên & trả lời an toàn"),
  channels: B("Channel setup & routing", "Thiết lập kênh & định tuyến"),
  records: B("Records & booking", "Hồ sơ & đặt lịch"),
  attribution: B("Attribution", "Quy nguồn"),
};

/* =============================================================================
   RESOLVER — the ONE seam between "what did the user ask" and "which grounded
   answer is that".
   -----------------------------------------------------------------------------
   Deliberately isolated so an LLM can be dropped in later WITHOUT touching the
   content spine, the answer renderer or the honesty rules. Everything downstream
   consumes a QA intent object; nothing downstream knows how it was chosen.

   To plug in an LLM, implement `resolve()` to call out and return either an
   existing intent (best — the answer stays grounded and citable) or null (the
   honest fallback). It must NEVER synthesise blocks: the guarantee that the
   Coach cannot invent a price, a rate or a clinical fact comes from the fact
   that every block it can render was written by a human and lives in data.js.

   Retrieval is the default because that guarantee is worth more than coverage,
   and because in a PHI context a confidently wrong answer is a safety problem,
   not a quality problem.
   ========================================================================== */
const Resolver = {
  mode: "retrieval",   // "retrieval" | "llm" (not implemented — see above)

  /* Normalise for matching: lowercase, strip Vietnamese diacritics and
     punctuation. Diacritic-folding matters — operators type "khong nhan duoc
     tin nhan" as often as "không nhận được tin nhắn". */
  norm(s) {
    return (s || "").toLowerCase()
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/đ/g, "d")
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .replace(/\s+/g, " ").trim();
  },

  /* Words that carry no topic. Without these, "what dose of antibiotic" scores
     against "what does this page do" on the word "what" alone, and a clinical
     question gets a confident non-clinical answer — measured, and exactly the
     failure this Coach must never have. */
  STOP: new Set([
    "what", "when", "where", "which", "does", "this", "that", "they", "them", "with",
    "from", "have", "here", "there", "your", "mine", "will", "should", "could", "would",
    "about", "into", "just", "some", "than", "then", "only", "also",
    "gi", "nao", "sao", "the", "cho", "cua", "tai", "khi", "nay", "duoc", "khong",
    "lam", "minh", "toi", "ban", "mot", "nhu", "voi", "hay", "phai", "co",
  ]),

  /* Score an intent against the question. Longer literal phrase hits win, so
     "take over" beats a stray "over"; same-screen intents win ties, because the
     question is nearly always about the screen you are standing on. */
  score(q, nq, ctx) {
    let best = 0;
    for (const m of q.match) {
      const nm = this.norm(m);
      if (!nm) continue;
      if (nq === nm) { best = Math.max(best, 100 + nm.length); continue; }
      if (nq.indexOf(nm) !== -1) { best = Math.max(best, 40 + nm.length * 2); continue; }
      if (nm.indexOf(nq) !== -1 && nq.length >= 4) { best = Math.max(best, 20 + nq.length); continue; }
      // Loose word overlap — the weakest signal, so it demands real evidence:
      // topic words only, and at least two of them (or one long, fully-matched
      // phrase). One shared word is a coincidence, not a question.
      const words = nm.split(" ").filter((w) => w.length > 3 && !this.STOP.has(w));
      if (!words.length) continue;
      const hits = words.filter((w) => nq.indexOf(w) !== -1).length;
      const strong = hits >= 2 || (hits === words.length && words[0].length >= 6);
      if (strong) best = Math.max(best, 10 * hits + (hits === words.length ? 10 : 0));
    }
    if (!best) return 0;
    const onScreen = q.screens === "*" || q.screens.indexOf(ctx.screen) !== -1;
    return best + (onScreen ? 25 : 0) + (q.screens === "*" ? -5 : 0);
  },

  resolve(text, ctx) {
    const nq = this.norm(text);
    if (!nq) return null;
    let bestQ = null, bestS = 0;
    for (const q of QA) {
      const s = this.score(q, nq, ctx);
      if (s > bestS) { bestS = s; bestQ = q; }
    }
    // Below the floor we return null and let the honest fallback speak, rather
    // than serving a weak match dressed up as an answer.
    return bestS >= 20 ? bestQ : null;
  },
};

/* =============================================================================
   COACH — ONE implementation, TWO mount points.
   -----------------------------------------------------------------------------
   In production the Coach is not a place you navigate to; it is present on every
   in-scope screen behind a persistent launcher, because the moment you need it
   is the moment you are stuck in the middle of something. So the same dock
   renders in two places and shares one state:

     · CompView      — the dedicated surface (a permanent right-hand dock),
                       used to demonstrate/evaluate the Coach on its own.
     · CoachOverlay  — a drawer over ANY live screen, opened by the floating
                       launcher or the "?" key. This is the production shape.

   `bodyHTML()` is the single source for both. Do not fork it.
   ========================================================================== */
const Coach = {
  screen: "carecommand", answers: [],

  /* The dock's inner markup — header, honesty banner, context card, suggested
     questions, answers, composer. Identical in both mount points. */
  bodyHTML(opts) {
    opts = opts || {};
    return `
      <div class="dh"><span class="glyph">${ic("bot")}</span>
        <span><b>${esc(T("coachName"))}</b><span>${esc(T("groundedIn"))} ${esc(screenTitle(this.screen))}</span></span>
        ${opts.closable ? `<button class="btn ghost sm dclose" data-act="coach-close"
            aria-label="${esc(tx(B("Close", "Đóng")))}">${ic("x")}</button>` : ""}</div>
      <div class="honest">${ic("shield-check")}<span>${esc(T("honest"))}</span></div>
      <div class="dbody" id="dbody">
        <div class="ctx"><div class="lbl">${esc(T("youreOn"))} ${esc(screenTitle(this.screen).toUpperCase())}</div>
          <p>${esc(tx(SCREEN_CTX[this.screen] || B("", "")))}</p></div>
        <div class="slbl">${esc(T("suggested"))}</div>
        <div class="sugg">${(QA_SUGGEST[this.screen] || []).map((id) => {
          const q = QA.find((x) => x.id === id);
          return q ? `<button data-act="c-ask-${id}">${esc(tx(q.label))}</button>` : "";
        }).join("")}</div>
        <div id="answers">${this.answers.join("")}</div>
      </div>
      <div class="dfoot">
        <input id="cin" type="text" placeholder="${esc(T("askPlaceholder"))}" aria-label="${esc(T("askPlaceholder"))}"/>
        <button data-act="c-send" aria-label="${esc(tx(B("Send", "Gửi")))}">${ic("send")}</button>
      </div>`;
  },

  /* Re-ground on a new screen. Answers are kept: a user who asked about the
     wall and then opened Contacts has not stopped caring about the answer. */
  ground(screen) { if (this.screen !== screen) { this.screen = screen; } },

  render() { if (CoachOverlay.open) CoachOverlay.render(); else if (CUR === CompView) CompView.render(); },

  ask(text) {
    const t = (text || "").trim();
    if (!t) return;
    const q = Resolver.resolve(t, { screen: this.screen, role: S.role, lang: S.lang });
    this.push(q ? this.answerHTML(q, t) : this.fallbackHTML(t));
  },
  askId(id) { const q = QA.find((x) => x.id === id); if (q) this.push(this.answerHTML(q, tx(q.label))); },
  push(html) {
    this.answers.unshift(html);
    const box = $("#answers");
    if (box) { box.insertAdjacentHTML("afterbegin", html); box.firstElementChild.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" }); }
    else this.render();
  },
  answerHTML(q, asked) {
    let blocks = q.blocks;
    if (q.dynamic === "screenCtx") {
      const s = allStations().find((x) => x.id === this.screen);
      blocks = [
        { k: "p", v: SCREEN_CTX[this.screen] },
        { k: "p", v: s.outline.why },
        { k: "ok", v: s.outline.when },
        { k: "source", v: B("This screen's station in the guided journey.", "Trạm của màn hình này trong hành trình hướng dẫn.") },
      ];
    } else if (q.dynamic === "nextStep") {
      const nx = nextStation();
      blocks = [
        { k: "p", v: nx ? B(`Your next station is <b>${tx(nx.title)}</b> — ${tx(nx.desc)}`, `Trạm tiếp theo của bạn là <b>${tx(nx.title)}</b> — ${tx(nx.desc)}`)
                        : B("You have finished every station. Try a mission in the practice clinic.", "Bạn đã hoàn thành mọi trạm. Hãy thử một nhiệm vụ trong phòng thực hành.") },
        { k: "ok", v: B("On this screen, right now: read the suggested questions above — they are the three things people actually get wrong here.",
                        "Ngay trên màn hình này: hãy đọc các câu hỏi gợi ý ở trên — đó là ba điều người dùng thật sự hay làm sai tại đây.") },
      ];
    } else if (q.roleAware && q.roleVariants) {
      blocks = q.roleVariants[S.role] || q.roleVariants.crm;
    }
    const body = (blocks || []).map((b) => this.block(b)).join("");
    const modes = [];
    if (q.showMe) modes.push(`<button class="btn sm" data-act="c-show-${q.id}">${ic("eye")}${esc(T("showMe"))}</button>`);
    if (q.simpler) modes.push(`<button class="btn sm" data-act="c-simple-${q.id}">${ic("lightbulb")}${esc(T("simpler"))}</button>`);
    if (q.practice) modes.push(`<button class="btn sm" data-act="c-prac-${q.practice}">${ic("flask")}${esc(T("letMePractise"))}</button>`);
    const st = allStations().find((x) => x.id === this.screen);
    if (st && st.lesson) modes.push(`<button class="btn sm" data-act="c-lesson-${st.lesson}">${ic("book-open")}${esc(T("openLesson"))}</button>`);
    return `<div class="ans"><div class="aq">${ic("message-circle")}<span>${esc(asked)}</span></div>
      ${body}${modes.length ? `<div class="amodes">${modes.join("")}</div>` : ""}</div>`;
  },
  block(b) {
    switch (b.k) {
      case "p": return `<p>${glossify(tx(b.v))}</p>`;
      case "warn": return `<div class="cal warn">${ic("alert-triangle")}<span>${tx(b.v)}</span></div>`;
      case "ok": return `<div class="cal ok">${ic("check-circle")}<span>${tx(b.v)}</span></div>`;
      case "refusal": return `<div class="cal ref">${ic("lock")}<span><b>${esc(T("refusal"))}.</b> ${tx(b.v)}</span></div>`;
      case "who": return `<p style="font-size:12.5px"><b>${esc(T("whoCan"))}</b> ${tx(b.v)}</p>`;
      case "how": return `<p style="font-size:12.5px"><b>${esc(T("howAsk"))}</b> ${tx(b.v)}</p>`;
      case "steps": return `<ol>${b.v.map((s) => `<li>${glossify(tx(s.t))}
          <button class="pt" data-act="c-point-${s.a}">${esc(tx(B("point at", "chỉ vào")))}</button></li>`).join("")}</ol>`;
      case "calc": return calcHTML();
      case "calcKpi": return calcKpiHTML();
      case "source": return `<div class="srcbox">${ic("database")} <b>${esc(T("source"))}:</b> ${esc(tx(b.v))}
          <div style="margin-top:4px">${esc(T("whyThis"))} ${esc(tx(B("You asked on this screen, and this is the content that covers it.",
            "Bạn đã hỏi trên màn hình này, và đây là nội dung bao phủ nó.")))}</div></div>`;
      default: return "";
    }
  },
  fallbackHTML(asked) {
    const ids = QA_FALLBACK[this.screen] || ["whatpage"];
    return `<div class="ans">
      <div class="aq">${ic("message-circle")}<span>${esc(asked)}</span></div>
      <div class="cal warn">${ic("alert-triangle")}<span><b>${esc(T("noAnswer"))}</b><br>${esc(T("noAnswerBody"))}</span></div>
      <div class="slbl" style="margin-top:var(--sp3)">${esc(T("canAnswer"))}</div>
      <div class="sugg">${ids.map((id) => { const q = QA.find((x) => x.id === id);
        return q ? `<button data-act="c-ask-${id}">${esc(tx(q.label))}</button>` : ""; }).join("")}</div></div>`;
  },
  onAct(name, el) {
    if (name === "c-send") { const i = $("#cin"); this.ask(i.value); i.value = ""; return; }
    if (name.startsWith("c-ask-")) { this.askId(name.slice(6)); return; }
    if (name.startsWith("c-point-")) {
      const a = name.slice(8);
      if (!flashRing(a)) toast(tx(B("That control is on another screen — open it from the sidebar.",
                                    "Nút đó nằm ở màn hình khác — hãy mở từ thanh bên.")), "", "info");
      return;
    }
    if (name.startsWith("c-show-")) {
      const q = QA.find((x) => x.id === name.slice(7));
      let k = 0;
      const seq = () => { if (k < q.showMe.length) { flashRing(q.showMe[k]); k++; setTimeout(seq, reduced() ? 260 : 1500); } };
      seq(); return;
    }
    if (name.startsWith("c-simple-")) {
      const q = QA.find((x) => x.id === name.slice(9));
      this.push(`<div class="ans"><div class="aq">${ic("lightbulb")}<span>${esc(T("simpler"))}</span></div>
        <p>${esc(tx(q.simpler))}</p></div>`);
      return;
    }
    if (name.startsWith("c-prac-")) { CoachOverlay.close(); location.hash = "#/sim"; setTimeout(() => SimView.start(name.slice(7)), 60); return; }
    if (name.startsWith("c-lesson-")) { CoachOverlay.close(); location.hash = "#/journey/lesson/" + name.slice(9); return; }
  },
  onKey(e) { if (e.key === "Enter" && e.target && e.target.id === "cin") { this.ask(e.target.value); e.target.value = ""; } },
};

/* --------------------------------------------------------------------------
   CoachOverlay — the production shape: a drawer over whatever you were doing.
   Never a modal: it does not block the screen behind it, and it does not cover
   the sidebar or the page header, so the thing you are stuck on stays visible
   while you read about it.
   -------------------------------------------------------------------------- */
const CoachOverlay = {
  open: false, el: null, returnFocus: null,
  toggle(screen) { this.open ? this.close() : this.show(screen); },
  show(screen) {
    if (screen) Coach.ground(screen);
    this.returnFocus = document.activeElement;
    this.open = true;
    this.render();
  },
  render() {
    if (this.el) this.el.remove();
    this.el = document.createElement("aside");
    this.el.className = "dock drawer";
    this.el.setAttribute("aria-label", T("coachName"));
    this.el.innerHTML = Coach.bodyHTML({ closable: true });
    OVER.appendChild(this.el);
    // The mission step panel lives in the same corner — move it rather than
    // letting the drawer bury the instruction the learner is following.
    document.body.classList.add("coach-open");
    const inp = $("#cin", this.el);
    if (inp) inp.focus();
  },
  close() {
    if (this.el) { this.el.remove(); this.el = null; }
    this.open = false;
    document.body.classList.remove("coach-open");
    if (this.returnFocus && document.body.contains(this.returnFocus)) this.returnFocus.focus();
    this.returnFocus = null;
  },
};

/* The persistent launcher. Present on every screen rendered inside the shell,
   with two deliberate exceptions:
     · during a lesson — the coach card IS the coaching; two coaches is noise;
     · on the CompView surface — the dock is already permanently open there. */
function mountCoachLauncher(screen) {
  const old = $(".coach-fab"); if (old) old.remove();
  if (CUR === LessonView && LessonView.lesson && !LessonView.quiz) return;
  const b = document.createElement("button");
  b.className = "coach-fab";
  b.setAttribute("data-act", "coach-toggle");
  b.setAttribute("aria-label", T("coachName"));
  b.innerHTML = ic("bot", "ic-lg") + `<span class="lbl">${esc(T("stuck"))}</span>`;
  b.title = T("stuckTip");
  OVER.appendChild(b);
  Coach.ground(screen);
}

/* The dedicated surface. Deliberately NOT a special layout: it is the live app
   with the launcher on it, which is exactly what production looks like. Browse
   the sidebar freely and open the Coach wherever you get stuck. The drawer
   auto-opens on first arrival so the surface explains itself. */
const CompView = {
  greeted: false,
  get screen() { return Coach.screen; },
  set screen(v) { Coach.screen = v; },
  get answers() { return Coach.answers; },
  set answers(v) { Coach.answers = v; },
  render() {
    APP.innerHTML = topbarHTML(false, "#/hub", T("comp")) + shellHTML(Coach.screen, {})
      + `<div class="coachhint">${ic("info")}<span>${esc(T("coachAlways"))}</span></div>`;
    mountCoachLauncher(Coach.screen);
    if (CoachOverlay.open) CoachOverlay.render();
    else if (!this.greeted) { this.greeted = true; CoachOverlay.show(Coach.screen); }
    setLast(T("comp") + " · " + screenTitle(Coach.screen));
  },
  nav(id) {
    const item = MENU[0].items.find((i) => i.id === id);
    if (!item) { toast(tx(B("That section is outside this prototype's scope (CRM only).",
                            "Khu vực đó nằm ngoài phạm vi của bản thử này (chỉ CRM).")), "", "info"); return; }
    Coach.screen = id; Coach.answers = []; this.render();
  },
  ask(t) { Coach.ask(t); },
  askId(id) { Coach.askId(id); },
  onAct(name, el) { Coach.onAct(name, el); },
  onKey(e) { Coach.onKey(e); },
};

/* Glossary hover-terms inside paragraphs. */
function glossify(html) {
  const map = [
    [/\burgency score\b|\bđiểm ưu tiên\b/i, "urgency"],
    [/\bcatchment( area)?\b|\bkhu vực phụ trách\b/i, "catchment"],
    [/\bwatch phrase\b|\bcụm từ cảnh báo\b/i, "watch"],
    [/\bconsent\b|\bđồng thuận\b/i, "consent"],
    [/\btouchpoint\b|\bđiểm chạm\b/i, "touchpoint"],
    [/\bOfficial Account\b/, "oa"],
    [/\bclaim(ing)?\b|\bnhận xử lý\b/i, "claim"],
  ];
  for (const [re, key] of map) {
    const m = html.match(re);
    if (m && html.indexOf('class="gloss"') === -1) {
      html = html.replace(re, `<span class="gloss" title="${esc(tx(GLOSSARY[key]))}">${m[0]}</span>`);
    }
  }
  return html;
}

/* =============================================================================
   ROUTER + delegated events
   ========================================================================== */
let CUR = HubView;
function route() {
  closeModal(); Spot.hide(); CoachOverlay.close();
  $$(".playbar,.mstep,.coach-fab").forEach((e) => e.remove());
  const h = location.hash || "#/hub";
  S.visited = true; save();
  if (h.startsWith("#/journey/lesson/")) { CUR = LessonView; LessonView.open(h.split("/").pop()); }
  else if (h.startsWith("#/journey")) { CUR = JourneyView; JourneyView.render(); }
  else if (h.startsWith("#/sim")) { CUR = SimView; SimView.mission = null; SimView.render(); }
  else if (h.startsWith("#/companion")) { CUR = CompView; CompView.render(); }
  else { CUR = HubView; HubView.render(); }
}
window.addEventListener("hashchange", route);

document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]");
  if (go) { location.hash = go.dataset.go; return; }
  const nav = e.target.closest("[data-nav]");
  if (nav) {
    if (CUR === CompView) CompView.nav(nav.dataset.nav);
    else if (CUR === SimView && SimView.mission) SimView.nav();
    else if (CUR === LessonView) toast(tx(B("Navigation is driven by the lesson here — use Next.",
                                            "Trong bài học, việc chuyển màn hình do bài dẫn dắt — hãy dùng Tiếp theo.")), "", "info");
    return;
  }
  const act = e.target.closest("[data-act]");
  if (!act) return;
  const name = act.dataset.act;
  if (name === "lang-en" || name === "lang-vi") {
    S.lang = name.slice(5); document.documentElement.lang = S.lang; save(); rerender(); return;
  }
  if (name.startsWith("role-")) {
    S.role = name.slice(5); save(); rerender();
    toast(T("roleNote") + ": " + roleLabel(), "", "users"); return;
  }
  if (name === "motion") {
    S.motion = S.motion === "reduced" ? "auto" : "reduced";
    document.documentElement.dataset.motion = S.motion; save(); rerender(); return;
  }
  if (name === "reset") {
    localStorage.removeItem("cjxLearn"); S = Object.assign({}, DEFAULT_STATE);
    document.documentElement.dataset.motion = S.motion; location.hash = "#/hub"; route();
    toast(tx(B("Progress reset.", "Đã đặt lại tiến độ.")), "ok", "rotate-ccw"); return;
  }
  if (name === "sb-open") { const sb = $(".sb"); if (sb) sb.classList.add("open"); return; }
  // The Coach is reachable from anywhere, so its actions are routed here rather
  // than through the active surface — the drawer can be open over any of them.
  if (name === "coach-toggle") { CoachOverlay.toggle(CURRENT_SCREEN); return; }
  if (name === "coach-close") { CoachOverlay.close(); return; }
  if (name.indexOf("c-") === 0) { Coach.onAct(name, act); return; }
  if (name === "morph-before" || name === "morph-after") {
    MORPH_STATE = name.slice(6);
    if (CUR === LessonView && LessonView.lesson) LessonView.renderStep();
    return;
  }
  if (name === "closemodal") { closeModal(); return; }
  if (name.startsWith("ol-done-")) {
    S.done[name.slice(8)] = true; save(); closeModal(); JourneyView.render();
    toast(tx(B("Outline marked as read.", "Đã đánh dấu đề cương là đã đọc.")), "ok", "check"); return;
  }
  if (name.startsWith("ol-coach-")) { closeModal(); CompView.screen = name.slice(9); location.hash = "#/companion"; return; }
  if (name.startsWith("sim-")) { return simAction(name); }
  if (CUR.onAct) CUR.onAct(name, act);
});

/* The practice shell's own buttons — always honest that nothing real happens. */
function simAction(name) {
  const m = {
    "sim-claim": B("Claimed. You are now the owner — a colleague opening this sees your name.", "Đã nhận xử lý. Bạn là người phụ trách — đồng nghiệp mở lên sẽ thấy tên bạn."),
    "sim-send": B("Practice only — nothing was sent. In production this reaches a real phone with no recall.", "Chỉ là thực hành — không có gì được gửi đi. Ở môi trường thật, tin này đến một điện thoại thật và không thu hồi được."),
    "sim-note": B("Internal note logged. The patient never sees it.", "Đã ghi chú nội bộ. Bệnh nhân không bao giờ nhìn thấy."),
    "sim-book": B("Practice only — the booking wizard would open with the duplicate check.", "Chỉ là thực hành — trình đặt lịch sẽ mở kèm bước kiểm tra trùng."),
    "sim-escalate": B("Escalated to the Duty Doctor. In production this pages a real clinician.", "Đã chuyển cấp cho Bác sĩ trực. Ở môi trường thật, thao tác này gọi một nhân viên y tế thật."),
    "sim-lead": B("Logged as a lead. Status is now “Lead”.", "Đã ghi nhận là khách hàng tiềm năng. Trạng thái hiện là “KHTN”."),
    "sim-consent": B("Data Sharing consent for Trần Mỹ Linh: WITHDRAWN on 30 June 2026.", "Đồng thuận chia sẻ dữ liệu cho Trần Mỹ Linh: ĐÃ THU HỒI ngày 30/6/2026."),
    "sim-junk": B("This would zero the urgency, mark the contact as spam AND flag the phone number.", "Thao tác này sẽ đưa điểm ưu tiên về 0, đánh dấu liên hệ là thư rác VÀ ghi nhận số điện thoại."),
    "sim-reauth": B("Practice only — a real re-authorisation takes the channel out of service while it runs.", "Chỉ là thực hành — cấp quyền lại thật sẽ đưa kênh ra khỏi trạng thái phục vụ trong lúc chạy."),
    "sim-prove": B("Test message sent (practice). Watch the Hà Nội wall count, not the green tick.", "Đã gửi tin nhắn thử (thực hành). Hãy nhìn số trên bảng Hà Nội, đừng nhìn dấu tích xanh."),
  }[name];
  if (!m) return;
  const kind = /junk|send|reauth|Thư rác|gửi|cấp quyền/i.test(name) ? "warn" : "ok";
  toast(tx(m), kind, kind === "warn" ? "alert-triangle" : "check");
  if (CUR === SimView && SimView.mission) {
    const st = SimView.mission.steps[SimView.i];
    if (st && st.target && !st.options) SimView.doStep();
  }
}

document.addEventListener("change", (e) => {
  const el = e.target.closest("[data-act]");
  if (el && CUR.onChange) CUR.onChange(el.dataset.act, el);
});
document.addEventListener("input", (e) => {
  const el = e.target.closest("[data-act=jsearch]");
  if (el && CUR === JourneyView) { CUR.onChange("jsearch", el); }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modalEl) { closeModal(); return; }
  if (e.key === "Escape" && CoachOverlay.open) { CoachOverlay.close(); return; }
  // "?" opens the Coach from anywhere — but never while the user is typing.
  const typing = e.target && /^(INPUT|TEXTAREA)$/.test(e.target.tagName);
  if (e.key === "?" && !typing && !modalEl && $(".coach-fab")) {
    CoachOverlay.toggle(CURRENT_SCREEN); e.preventDefault(); return;
  }
  if (CoachOverlay.open) { Coach.onKey(e); return; }
  if (CUR === CompView) CompView.onKey(e);
  if (CUR === LessonView && LessonView.lesson && !modalEl) LessonView.onKey(e);
});
window.addEventListener("resize", () => {
  if (CUR === LessonView && LessonView.lesson && !LessonView.quiz) LessonView.renderStep();
});

function rerender() {
  if (CUR === LessonView && LessonView.lesson) LessonView.renderStep();
  else if (CUR === SimView && SimView.mission) SimView.renderMission();
  else if (CUR.render) CUR.render();
}

/* boot */
document.documentElement.dataset.motion = S.motion;
document.documentElement.lang = S.lang;
route();
