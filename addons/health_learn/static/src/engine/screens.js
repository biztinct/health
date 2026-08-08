/** @odoo-module **/
/* =============================================================================
   The practice shell — a replica of the CRM screens, drawn from the fixture.

   It is a REPLICA, not the product: there is no server behind it, so it is
   structurally incapable of touching a real patient, phone or invoice. The
   banner is the last line of defence rather than the only one.

   Every control the content points at carries data-a="…" — the same anchor
   keys the real templates now carry, so a lesson step and a Phase-2 coach
   answer address a control by one name whichever surface it is on.

   Screen prose is inline B("en","vi") on purpose. These strings must mirror
   what the PRODUCT says in Vietnamese; putting them in the module's .po would
   hand a translator wording they do not own, and the two would diverge at the
   first product rename.
   ========================================================================== */
import { B, CASE, MENU, PRACTICE, STATUS_LABELS } from "./fixture";
import { esc, ic, initial, tx, T, N, P } from "./runtime";
import { pipeHTML } from "./visuals";

/* Which screen the shell is showing. Phase 2's Coach grounds on this. */
export let CURRENT_SCREEN = null;

/* ------------------------------------------------------------------- helpers */
export function statusChip(kind, key) {
    const s = (STATUS_LABELS[kind] || {})[key];
    return s
        ? `<span class="lrn-chip ${s.t}">${esc(tx(s.l))}</span>`
        : `<span class="lrn-chip">${esc(key)}</span>`;
}

function channelName(id) {
    const c = CASE.channels.find((x) => x.id === id);
    if (c) {
        return tx(c.label);
    }
    return { zns: "ZNS", whatsapp: "WhatsApp", telegram: "Telegram", email: "Email" }[id] || id;
}

export function screenTitle(id) {
    for (const sec of MENU) {
        for (const it of sec.items) {
            if (it.id === id) {
                return tx(it.label);
            }
        }
    }
    return "";
}

/* --------------------------------------------------------------- row renderers
   These read PRACTICE, never their own literals — which is what makes the
   fixture the single place to edit when the product changes. */
function recentRows() {
    return PRACTICE.recent.map((r) => `
        <div class="lrn-row"><span class="lrn-avatar">${esc(initial(r.name))}</span>
            <span><span class="lrn-nm">${esc(tx(r.name))}</span><br>
                <span class="lrn-sub2">${esc(tx(r.meta))}</span></span>
            <span class="lrn-rr"><span class="lrn-chip ${r.tone}">${esc(T("needsReply"))}</span></span>
        </div>`).join("");
}

function wallRows() {
    return PRACTICE.conversations.map((r) => `
        <div class="lrn-row" ${r.anchor ? `data-a="${esc(r.anchor)}"` : ""}>
            <span class="lrn-urg ${r.urgency >= 90 ? "hi" : r.urgency >= 50 ? "md" : "lo"}">${r.urgency}</span>
            <span class="lrn-avatar">${esc(initial(r.name))}</span>
            <span><span class="lrn-nm">${esc(tx(r.name))}
                    <span class="lrn-faint">#${r.id}</span></span><br>
                <span class="lrn-sub2">${esc(channelName(r.channel))}${" "}· ${esc(tx(r.note))}</span></span>
            <span class="lrn-rr">${statusChip("conversation", r.status)}</span>
        </div>`).join("");
}

function timelineHTML() {
    return PRACTICE.timeline.map((m) => {
        if (m.kind === "sys") {
            return `<div class="lrn-bub sys">${esc(tx(m.text))}</div>`;
        }
        return `<div class="lrn-bub ${m.kind}" ${m.anchor ? `data-a="${esc(m.anchor)}"` : ""}>
            ${esc(tx(m.text))}${m.ts ? `<span class="lrn-ts">${esc(m.ts)}</span>` : ""}</div>`;
    }).join("");
}

/* -------------------------------------------------------------------- screens */
export const SCREENS = {
    dashboard() {
        const m = CASE.month;
        const k = CASE.kpis;
        const cards = [
            ["phone", T("today"), N(k.contactsToday), B("Contacts Today", "Liên hệ hôm nay"), "", "db-contacts_today"],
            ["clock", T("all"), N(k.pendingFollowups), B("Pending Follow-ups", "Đang chờ theo dõi"), "warn", "db-pending_followups"],
            ["target", T("all"), N(k.activeLeads), B("Active Leads", "KHTN đang hoạt động"), "", "db-active_leads"],
            ["calendar", T("week"), N(k.bookingsWeek), B("Bookings This Week", "Lịch hẹn tuần này"), "pos", "db-bookings_this_week"],
            ["trending-up", T("month"), P(m.conversion), B("Conversion Rate", "Tỷ lệ chuyển đổi"), "pos", "db-conversion_rate"],
            ["ban", T("month"), P(m.spamRate), B("Spam Rate", "Tỷ lệ thư rác"), "", "db-spam_rate"],
        ].map(([i, per, v, lab, tone, a]) => `
            <div class="lrn-kpi ${tone}" data-a="${a}">
                <div class="lrn-kt">${ic(i)}<span>${esc(tx(lab))}</span></div>
                <div class="lrn-kv">${v}</div>
                <div class="lrn-kp">${esc(per)}</div>
            </div>`).join("");

        const segs = [
            [m.booking, "var(--vuf-ok)", B("Booking", "Đặt lịch")],
            [m.lead, "var(--vuf-primary)", B("Lead", "KHTN")],
            [m.lost, "var(--vuf-danger)", B("Lost Booking", "Mất cơ hội")],
            [m.spam, "var(--vuf-faint)", B("Spam", "Thư rác")],
        ];
        const stack = segs.map(([n, c]) =>
            `<i style="width:${(n / m.total * 100).toFixed(1)}%;background:${c}"></i>`).join("");
        const leg = segs.map(([n, c, l]) =>
            `<span><em style="background:${c}"></em>${esc(tx(l))}${" "}· <b>${N(n)}</b></span>`).join("");
        const max = Math.max(...CASE.channels.map((c) => c.n));
        const bars = CASE.channels.map((c) => `
            <div class="lrn-hbar"><span>${esc(tx(c.label))}</span>
                <span class="lrn-track"><i style="width:${(c.n / max * 100).toFixed(0)}%"></i></span>
                <b>${N(c.n)}</b></div>`).join("");

        return `
            <div class="lrn-tabs" data-a="db-period">
                ${["today", "week", "month", "all", "custom"].map((k2, i) =>
                    `<button aria-selected="${i === 0}">${esc(T(k2))}</button>`).join("")}
            </div>
            <div class="lrn-grid g6">${cards}</div>
            <div class="lrn-grid g2">
                <div class="lrn-panel" data-a="db-pipeline"><h3>${ic("pie")}${esc(tx(B("Contact Pipeline · this month", "Quy trình liên hệ · tháng này")))}</h3>
                    <div class="lrn-stack">${stack}</div><div class="lrn-legend">${leg}</div>
                    <p class="lrn-note">${esc(tx(B(
                        `${N(m.total)}${" "}enquiries = ${N(m.spam)}${" "}spam + ${N(m.real)}${" "}real; ${N(m.real)}${" "}= ${N(m.booking)}${" "}booked + ${N(m.lead)}${" "}leads + ${N(m.lost)}${" "}lost.`,
                        `${N(m.total)}${" "}yêu cầu = ${N(m.spam)}${" "}thư rác + ${N(m.real)}${" "}thật; ${N(m.real)}${" "}= ${N(m.booking)}${" "}đã đặt lịch + ${N(m.lead)}${" "}KHTN + ${N(m.lost)}${" "}mất cơ hội.`)))}</p>
                </div>
                <div class="lrn-panel" data-a="db-channels"><h3>${ic("bar-chart")}${esc(tx(B("Source Channels · this month", "Các kênh nguồn · tháng này")))}</h3>
                    <div class="lrn-hbars">${bars}</div></div>
            </div>
            <div class="lrn-panel" data-a="db-recent"><h3>${ic("clock")}${esc(tx(B("Recent Contacts", "Liên hệ gần đây")))}</h3>
                <div class="lrn-rows">${recentRows()}</div></div>`;
    },

    carecommand() {
        const calc = CASE.urgency.map((t) => {
            const isWatch = /watch|cảnh báo/i.test(tx(t.k));
            return `<div class="lrn-cr ${isWatch ? "hit" : ""}" ${isWatch ? 'data-a="cc-term-watch"' : ""}>
                <span>${esc(tx(t.k))}</span><b>+${t.v}</b></div>`;
        }).join("") +
            `<div class="lrn-cr tot"><span>${esc(tx(B("Urgency score", "Điểm ưu tiên")))}</span>
             <b>${CASE.urgencyTotal}</b></div>`;

        return `
            <div class="lrn-tabs" data-a="cc-tabs">
                <button aria-selected="true">${esc(T("attention"))}${" "}· ${CASE.wall.needsReply}</button>
                <button aria-selected="false">${esc(T("leadsTab"))}</button>
                <button aria-selected="false">${esc(T("allTab"))}${" "}· ${CASE.wall.open}</button>
                <span class="lrn-chip b lrn-push" data-a="cc-catchment">${ic("map-pin")}${esc(T("catchment"))}: ${esc(T("hanoi"))}</span>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-a="cc-wall">
                    <h3>${ic("zap")}${esc(tx(B("Attention wall", "Bảng cần chú ý")))}
                        <span class="lrn-chip lrn-push">${esc(tx(B(
                            `${CASE.wall.open}${" "}open · ${CASE.wall.unclaimed}${" "}unclaimed`,
                            `${CASE.wall.open}${" "}đang mở · ${CASE.wall.unclaimed}${" "}chưa ai nhận`)))}</span></h3>
                    <div class="lrn-rows">${wallRows()}</div>
                </div>
                <div class="lrn-panel">
                    <h3>${ic("message-circle")}#${CASE.convId}${" "}· ${esc(tx(CASE.sender))}</h3>
                    <div class="lrn-claimbar" data-a="cc-claim">${ic("user-plus")}
                        <span>${esc(T("unclaimed"))}</span>
                        <button class="lrn-btn sm pri" data-act="sim-claim" data-a="cc-release">${esc(T("claim"))}</button></div>
                    <div class="lrn-tl">${timelineHTML()}</div>
                    <div class="lrn-composer" data-a="cc-composer">
                        <textarea placeholder="${esc(tx(B("Type a reply…", "Nhập câu trả lời…")))}"></textarea>
                    </div>
                    <div class="lrn-strip" data-a="cc-actions">
                        <button class="lrn-btn sm pri" data-act="sim-send">${ic("send")}${esc(T("sendReply"))}</button>
                        <button class="lrn-btn sm" data-act="sim-note">${ic("file-text")}${esc(T("addNote"))}</button>
                        <button class="lrn-btn sm" data-act="sim-book">${ic("calendar")}${esc(T("bookBtn"))}</button>
                        <button class="lrn-btn sm" data-act="sim-escalate" data-a="cc-escalate">${ic("alert-triangle")}${esc(T("escalate"))}</button>
                        <button class="lrn-btn sm" data-act="sim-lead">${ic("target")}${esc(T("logLead"))}</button>
                        <button class="lrn-btn sm" data-act="sim-consent" data-a="cc-consent">${ic("shield-check")}${esc(T("consentBtn"))}</button>
                        <button class="lrn-btn sm danger" data-act="sim-junk" data-a="cc-junk">${ic("ban")}${esc(T("markJunk"))}</button>
                    </div>
                </div>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-a="cc-score-4172">
                    <h3>${ic("calculator")}${esc(tx(B("Urgency breakdown · #4172", "Chi tiết điểm ưu tiên · #4172")))}</h3>
                    <div class="lrn-calc">${calc}</div></div>
                <div class="lrn-panel" data-a="cc-pipeline">
                    <h3>${ic("git-branch")}${esc(tx(B("Conversation lifecycle", "Vòng đời cuộc hội thoại")))}</h3>
                    ${pipeHTML("conv", 0)}</div>
            </div>`;
    },

    channelcenter() {
        const cards = PRACTICE.channels.map((c) => {
            const connected = c.state !== "not_connected";
            return `
            <div class="lrn-chcard" data-a="${esc(c.a)}">
                <header><span class="lrn-glyph">${ic(c.glyph)}</span><b>${esc(tx(c.name))}</b>
                    <span class="lrn-push">${statusChip("connection", c.state)}</span></header>
                <div class="lrn-meta2"${c.areaAnchor ? ' data-a="ch-area-zalo-hn"' : ""}>${esc(tx(c.meta))}</div>
                <div class="lrn-acts">
                    ${!connected
                        ? `<button class="lrn-btn sm pri">${esc(T("connectBtn"))}</button>`
                        : `<button class="lrn-btn sm" data-act="sim-reauth" ${c.id === "zalo-hn" ? 'data-a="ch-reauth"' : ""}>${esc(T("reauth"))}</button>
                           <button class="lrn-btn sm ghost" ${c.id === "zalo-hn" ? 'data-a="ch-disable"' : ""}>${esc(T("disconnect"))}</button>`}
                </div>
            </div>`;
        }).join("");

        return `
            <div class="lrn-panel" data-a="ch-pipeline">
                <h3>${ic("git-branch")}${esc(tx(B("Connection lifecycle", "Vòng đời kết nối")))}</h3>
                ${pipeHTML("conn", 5)}
                <p class="lrn-note">${esc(tx(B(
                    "One server path writes this state and audits every move. Ready is derived from the readiness checks, never typed in.",
                    "Chỉ một luồng phía máy chủ ghi trạng thái này và ghi nhật ký mọi thay đổi. Trạng thái Đã kết nối được suy ra từ các bước kiểm tra sẵn sàng, không bao giờ nhập tay.")))}</p>
            </div>
            <div class="lrn-panel" data-a="ch-catalogue">
                <h3>${ic("plug")}${esc(tx(B("Connectable channels", "Các kênh có thể kết nối")))}
                    <span class="lrn-chip lrn-push">${esc(tx(B("Walk-in is not connectable — no provider", "Đến trực tiếp không kết nối được — không có nhà cung cấp")))}</span></h3>
                <div class="lrn-chcards">${cards}</div></div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-a="ch-checks">
                    <h3>${ic("clipboard-check")}${esc(tx(B("Readiness checks · Hà Nội OA", "Kiểm tra sẵn sàng · OA Hà Nội")))}</h3>
                    <div class="lrn-checks">
                        ${PRACTICE.readiness.map((k) => `<div class="lrn-chk ${k.pass ? "pass" : "fail"}">
                            ${ic(k.pass ? "check-circle" : "x")}<span>${esc(tx(k.l))}</span></div>`).join("")}
                    </div>
                    <p class="lrn-note">${esc(tx(B(
                        "These prove the connection is capable. Only real traffic proves it works.",
                        "Những bước này chứng minh kết nối có khả năng hoạt động. Chỉ lưu lượng thật mới chứng minh nó hoạt động.")))}</p>
                </div>
                <div class="lrn-panel" data-a="ch-prove">
                    <h3>${ic("target")}${esc(tx(B("Prove it works", "Chứng minh nó hoạt động")))}</h3>
                    <p class="lrn-note">${esc(tx(B(
                        "Send one message from a personal account to the OA and watch it appear on the wall.",
                        "Gửi một tin nhắn từ tài khoản cá nhân tới OA và xem nó xuất hiện trên bảng.")))}</p>
                    <button class="lrn-btn pri sm" data-act="sim-prove">${ic("send")}${esc(tx(B("Send test message", "Gửi tin nhắn thử")))}</button>
                    <div class="lrn-mt" data-a="ch-wall-hn">
                        <div class="lrn-hbar"><span>${esc(T("hanoi"))}</span>
                            <span class="lrn-track"><i style="width:100%"></i></span><b>${CASE.wall.open}</b></div>
                        <div class="lrn-hbar"><span>${esc(T("hcmc"))}</span>
                            <span class="lrn-track"><i style="width:58%"></i></span><b>7</b></div>
                    </div>
                </div>
            </div>
            <div class="lrn-panel" data-a="ch-golive">
                <h3>${ic("shield-check")}${esc(tx(B("Go-live console", "Bảng điều khiển phát hành")))}</h3>
                <p class="lrn-note">${esc(tx(B(
                    "Availability is reported honestly: a channel is offered only when this deployment has an adapter AND the tenant has credentials. Three channels above are shown as Not connected for exactly that reason — the console does not draw a Connect button that could only fail.",
                    "Khả dụng được báo cáo trung thực: một kênh chỉ được đưa ra khi bản triển khai này có bộ chuyển đổi VÀ đơn vị có thông tin xác thực. Ba kênh ở trên hiển thị Chưa kết nối đúng vì lý do đó — bảng điều khiển không vẽ ra nút Kết nối chắc chắn sẽ thất bại.")))}</p>
            </div>`;
    },

    unrouted() {
        const items = PRACTICE.captures.map((c) => `
            <div class="lrn-row">
                <span class="lrn-avatar">${ic("inbox")}</span>
                <span><span class="lrn-nm">${esc(tx(c.what))}</span><br>
                    <span class="lrn-sub2">${esc(tx(c.got))}</span></span>
                <span class="lrn-rr">
                    <button class="lrn-btn sm ${c.anchored ? "pri" : ""}" ${c.anchored ? "" : "disabled"}
                        ${c.anchorA ? 'data-a="ur-convert"' : ""}>${esc(T("convert"))}</button>
                    <button class="lrn-btn sm ghost" ${c.anchorA ? 'data-a="ur-dismiss"' : ""}>${esc(T("dismiss"))}</button>
                </span>
            </div>`).join("");
        return `<div class="lrn-panel" data-a="ur-list">
            <h3>${ic("inbox")}${esc(tx(B("New today", "Mới hôm nay")))}
                <span class="lrn-chip a lrn-push">${CASE.unrouted}</span></h3>
            <div class="lrn-rows">${items}</div>
            <p class="lrn-note">${esc(tx(B(
                "These records cannot be edited — they are evidence of exactly what the channel sent. Convert needs at least one anchor (a contact, a phone number or an email); the first row has none, so Convert is refused rather than creating an unreachable record.",
                "Các bản ghi này không sửa được — chúng là bằng chứng về đúng những gì kênh đã gửi. Chuyển đổi cần ít nhất một điểm neo (một liên hệ, một số điện thoại hoặc email); dòng đầu tiên không có, nên Chuyển đổi bị từ chối thay vì tạo ra một bản ghi không liên lạc được.")))}</p>
        </div>`;
    },

    contacts() {
        const tabs = [B("All", "Tất cả"), B("Active", "Đang hoạt động"), B("Leads", "KHTN"),
            B("Bookings", "Đặt lịch"), B("Lost", "Thất bại"), B("Spam", "Thư rác")]
            .map((l, i) => `<button aria-selected="${i === 0}">${esc(tx(l))}</button>`).join("");
        const rows = PRACTICE.contacts.map((c) => `
            <div class="lrn-row">
                <span class="lrn-avatar">${esc(initial(c.name))}</span>
                <span><span class="lrn-nm">${esc(tx(c.name))}</span><br>
                    <span class="lrn-sub2">${esc(tx(c.meta))}</span></span>
                <span class="lrn-rr">
                    ${statusChip("contact", c.status)}
                    <button class="lrn-btn sm" data-a="co-book">${esc(T("bookBtn"))}</button>
                    <button class="lrn-btn sm ghost">${esc(T("escalate"))}</button>
                    <button class="lrn-btn sm ghost">${esc(T("markJunk"))}</button>
                </span>
            </div>`).join("");
        return `<div class="lrn-tabs" data-a="co-tabs">${tabs}</div>
            <div class="lrn-panel" data-a="co-rows"><div class="lrn-rows">${rows}</div></div>
            <div class="lrn-panel" data-a="co-pipeline"><h3>${ic("git-branch")}${esc(tx(B("Contact lifecycle", "Vòng đời liên hệ")))}</h3>
                ${pipeHTML("contact", 2)}</div>`;
    },

    touchpoints() {
        const rows = CASE.attribution.map((a) => `
            <tr><td>${esc(typeof a.c === "string" ? a.c : tx(a.c))}</td>
                <td>${esc(typeof a.src === "string" ? a.src : tx(a.src))}</td>
                <td>pkgdvietuc.com/dich-vu/…</td><td class="n">${N(a.n)}</td></tr>`).join("");
        return `<div class="lrn-panel" data-a="tp-table">
                <h3>${ic("crosshair")}${esc(tx(B("Website arrivals · this month", "Lượt đến từ website · tháng này")))}
                    <span class="lrn-chip a lrn-push" data-a="tp-unmatched">${ic("alert-triangle")}${esc(T("unmatched"))}${" "}· 4</span></h3>
                <div class="lrn-tblwrap"><table class="lrn-tbl">
                    <thead><tr><th>${esc(tx(B("UTM campaign", "Chiến dịch UTM")))}</th>
                        <th>${esc(tx(B("Source / medium", "Nguồn / phương tiện")))}</th>
                        <th>${esc(tx(B("Landing page", "Trang đích")))}</th>
                        <th class="n">${esc(tx(B("Enquiries", "Yêu cầu")))}</th></tr></thead>
                    <tbody>${rows}<tr class="lrn-tot"><td colspan="3">${esc(tx(B("Total website enquiries", "Tổng yêu cầu từ website")))}</td>
                        <td class="n">34</td></tr></tbody>
                </table></div>
            </div>
            <div class="lrn-panel"><h3>${ic("target")}${esc(tx(B("The worked case", "Tình huống mẫu")))}</h3>
                <p class="lrn-note">${esc(tx(B(
                    "Trần Mỹ Linh clicked a Google advert on 10 August and read the wound-care page. She did not fill in the form. Two days later she messaged the Zalo OA — and the touchpoint joined the conversation by phone number, not by channel.",
                    "Trần Mỹ Linh nhấp vào một quảng cáo Google ngày 10 tháng 8 và đọc trang chăm sóc vết thương. Cô ấy không điền biểu mẫu. Hai ngày sau cô nhắn tới Zalo OA — và điểm chạm được nối với cuộc hội thoại qua số điện thoại, không phải qua kênh.")))}</p>
            </div>`;
    },

    leadanalysis() {
        const head = [B("Booked", "Đã đặt lịch"), B("Lead", "KHTN"), B("Lost", "Mất"),
            B("Spam", "Thư rác"), B("Total", "Tổng")];
        const rows = PRACTICE.pivot.map((r) => `<tr><td><b>${esc(tx(r.ch))}</b></td>
            ${[r.booked, r.lead, r.lost, r.spam].map((v) => `<td class="n">${N(v)}</td>`).join("")}
            <td class="n lrn-strong">${N(r.total)}</td></tr>`).join("");
        const m = CASE.month;
        return `<div class="lrn-panel" data-a="la-pivot">
            <h3>${ic("bar-chart")}${esc(tx(B("Enquiries by channel × status · this month", "Yêu cầu theo kênh × trạng thái · tháng này")))}</h3>
            <div class="lrn-tblwrap"><table class="lrn-tbl">
                <thead><tr><th>${esc(tx(B("Effective channel", "Kênh hiệu lực")))}</th>
                    ${head.map((h) => `<th class="n">${esc(tx(h))}</th>`).join("")}</tr></thead>
                <tbody>${rows}
                    <tr class="lrn-tot" data-a="la-total"><td>${esc(tx(B("Total", "Tổng")))}</td>
                        <td class="n">${N(m.booking)}</td><td class="n">${N(m.lead)}</td>
                        <td class="n">${N(m.lost)}</td><td class="n">${N(m.spam)}</td>
                        <td class="n">${N(m.total)}</td></tr></tbody>
            </table></div>
            <p class="lrn-note">${esc(tx(B(
                `Reconciles with the Dashboard only at the same period and catchment: ${N(m.booking)}${" "}÷ ${N(m.real)}${" "}real enquiries = ${P(m.conversion)}${" "}conversion; ${N(m.spam)}${" "}÷ ${N(m.total)}${" "}= ${P(m.spamRate)}${" "}spam.`,
                `Chỉ khớp với Bảng điều khiển khi cùng khoảng thời gian và cùng khu vực: ${N(m.booking)}${" "}÷ ${N(m.real)}${" "}yêu cầu thật = ${P(m.conversion)}${" "}chuyển đổi; ${N(m.spam)}${" "}÷ ${N(m.total)}${" "}= ${P(m.spamRate)}${" "}thư rác.`)))}</p>
        </div>`;
    },

    activities() {
        const groups = PRACTICE.activities.map((g) => `
            <div class="lrn-panel"><h3>${ic(g.icon)}${esc(tx(g.type))}
                <span class="lrn-chip lrn-push">${g.n}</span></h3>
                <div class="lrn-rows">
                    ${Array.from({ length: g.n }, (_, k) => `
                        <div class="lrn-row"><span class="lrn-avatar">${ic(g.icon)}</span>
                            <span><span class="lrn-nm">${esc(tx(k === 0 && g.icon === "phone"
                                ? B("Call back Trần Mỹ Linh", "Gọi lại Trần Mỹ Linh")
                                : B("Follow up enquiry", "Theo dõi yêu cầu tư vấn")))}</span><br>
                                <span class="lrn-sub2">${esc(tx(B("Due 13 Aug · assigned to the CRM team", "Đến hạn 13/8 · giao cho nhóm CRM")))}</span></span>
                        </div>`).join("")}
                </div></div>`).join("");
        return `<div class="lrn-tabs" data-a="ac-filter">
                <button aria-selected="true">${esc(T("all"))}</button>
                <button aria-selected="false">${esc(T("today"))}</button>
                <button aria-selected="false">${esc(T("week"))}</button>
                <button aria-selected="false">${esc(T("month"))}</button>
                <button class="lrn-btn sm pri lrn-push">${ic("plus")}${esc(tx(B("Schedule activity", "Lên lịch hoạt động")))}</button>
            </div>
            <div class="lrn-grid g2" data-a="ac-groups">${groups}</div>
            <div class="lrn-panel"><p class="lrn-note">${esc(tx(B(
                `These ${CASE.kpis.pendingFollowups}${" "}open follow-ups are exactly the Dashboard's “Pending Follow-ups” card. If the two disagree, an activity was closed without the contact's status being updated.`,
                `${CASE.kpis.pendingFollowups}${" "}việc theo dõi đang mở này chính là thẻ “Đang chờ theo dõi” trên Bảng điều khiển. Nếu hai nơi lệch nhau, tức là một hoạt động đã được đóng mà chưa cập nhật trạng thái liên hệ.`)))}</p></div>`;
    },
};

/* ---------------------------------------------------------------------- shell
   `visible` is the set of station keys the LEARNER's own sidebar shows — it
   comes from the server, which computes it by calling the real sidebar. So the
   replica's menu is not a guess about the role gate; it is the role gate. */
export function shellHTML(screen, opts) {
    const o = opts || {};
    const visible = o.visible || new Set();
    CURRENT_SCREEN = screen;

    const secs = MENU.map((sec) => {
        const items = sec.items.map((it) => {
            const inScope = sec.inScope;
            const seen = !inScope || visible.has(it.id);
            // During a guided lesson the full menu stays legible: a learner who
            // cannot open a screen is exactly the person who needs to read what
            // it is before asking for access.
            const off = !inScope || (!seen && !o.guided);
            const on = it.id === screen;
            return `<button class="lrn-item ${on ? "on" : ""}${" "}${off ? "off" : ""}" data-nav="${esc(it.id)}"
                ${off ? 'tabindex="-1" aria-disabled="true"' : ""}>${ic(it.icon)}
                <span>${esc(tx(it.label))}</span></button>`;
        }).join("");
        return `<div class="lrn-sec">${esc(tx(sec.label))}</div>${items}`;
    }).join("");

    const body = SCREENS[screen] ? SCREENS[screen]() : "";
    const gated = MENU[0].items.find((i) => i.id === screen);
    const blocked = gated && !visible.has(screen) && !o.guided;

    return `
    <div class="lrn-shell">
        <aside class="lrn-sb" aria-label="CareJioX navigation">
            <div class="lrn-brand"><span class="lrn-mark">${ic("heart")}</span><span>CareJioX</span></div>
            <div class="lrn-catch"><b>${esc(T("catchment"))}</b>${esc(T("hanoi"))}</div>
            ${secs}
            <div class="lrn-foot">${esc(tx(B("Practice data · not your clinic", "Dữ liệu thực hành · không phải phòng khám của bạn")))}</div>
        </aside>
        <div class="lrn-main">
            <div class="lrn-pbanner">${ic("shield-check")}<span>${esc(T("practiceBanner"))}</span></div>
            <div class="lrn-mhead">
                <h2>${esc(screenTitle(screen))}</h2>
                <span class="lrn-sub">${esc(tx(B("Practice clinic — demo data", "Phòng khám thực hành — dữ liệu mô phỏng")))}</span>
            </div>
            <div class="lrn-screen">${blocked ? blockedHTML() : body}</div>
        </div>
    </div>`;
}

function blockedHTML() {
    return `<div class="lrn-panel lrn-blocked">
        <h3>${ic("lock")}${esc(T("notVisible"))}</h3>
        <p class="lrn-note">${esc(T("notVisibleBody"))}</p>
        <p class="lrn-note">${esc(tx(B(
            "You can still read what this screen does, and what it would take to be given access.",
            "Bạn vẫn có thể đọc màn hình này làm gì, và cần gì để được cấp quyền truy cập.")))}</p>
    </div>`;
}
