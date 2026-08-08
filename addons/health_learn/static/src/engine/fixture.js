/* GENERATED FILE. Do not edit.
            Source: docs/tutorial_crm/ · Regenerate: python3 docs/tutorial_crm/tools/gen_learn_data.py
            Hand edits are erased on the next run and fail the CI check. */
/** @odoo-module **/

/* =============================================================================
   CareJioX Learn — PRACTICE DATASET
   -----------------------------------------------------------------------------
   THE ONLY FILE THAT MIRRORS THE PRODUCT.

   There is no demo tenant and none is needed: the practice clinic is this
   JavaScript fixture. Nothing here can reach a real patient, phone, channel or
   invoice, because there is no server on the other end of it.

   THE COST OF THAT CHOICE, AND HOW IT IS PAID
   -------------------------------------------
   A fixture drifts. When a selection value is renamed, a scoring constant is
   re-weighted or a menu leaf moves, this file silently starts teaching a
   product that no longer exists — and a confidently wrong tutorial is worse
   than none.

   So every value below that mirrors something real is declared in
   `contract.json`, and `tools/check_contract.py` verifies each declaration
   against the actual addons. Run it in CI. When it fails, THIS file (and the
   content that quotes it) is what needs updating — the checker tells you which
   entries and which lessons quote them.

       python3 docs/tutorial_crm/tools/check_contract.py

   RULE FOR EDITORS: teaching content lives in `data.js`. Anything that is a
   fact about the product lives HERE, once, and is referenced from there. If you
   find yourself typing a number into a lesson step, it belongs in this file.
   ========================================================================== */

const B = (en, vi) => ({ en, vi });

/* Bump the minor when you add records; bump the major when a shape changes,
   because `check_contract.py` pins to it. */
const PRACTICE_META = {
  schemaVersion: "1.1.0",
  contract: "contract.json",
  derivedFrom: "health19 branch 19.0",
  isolation: B(
    "No server, no tenant, no credentials. Every action in the practice clinic resolves inside this file.",
    "Không máy chủ, không đơn vị riêng, không thông tin xác thực. Mọi thao tác trong phòng thực hành đều xử lý bên trong tệp này."),
};

/* =============================================================================
   0. TENANT OVERRIDES — the named slots a clinic may fill in.
   -----------------------------------------------------------------------------
   ONE IMPORTANT DISTINCTION, because it is easy to conflate these two:

     · This PRACTICE FIXTURE is module-shipped and identical in every tenant.
       It is fake data, and it lives in JavaScript precisely so that it can
       never touch a real record.

     · A TENANT OVERRIDE is a REAL fact about one clinic — its actual hotline
       number, its actual Official Account names. Those differ per tenant, so
       they CANNOT live in a module-shipped file: the module ships the same
       bytes to everyone. In production this is one small database row per
       tenant, holding exactly the named keys below and nothing else.

   So: JSON-shaped, authored like JSON, but DB-resident. It is configuration,
   not business data — it never reads or writes a patient, a booking or an
   invoice, which is what makes it safe to expose to a tenant admin.

   HOW IT IS USED
   --------------
   Content writes `{{key}}` in any translatable string. `tx()` resolves it at
   render time: tenant value if set, otherwise the default below. Content never
   hard-codes a clinic-specific fact.

   THE HARD RULE
   -------------
   Overrides fill NAMED SLOTS. They can never replace a lesson step, a quiz
   option, a consequence card or a coach answer. The moment a tenant can edit
   prose, you have twelve divergent tutorials and the contract check can no
   longer guard any of them. An unknown `{{key}}` renders as the key itself and
   is caught by `check_contract.py`, not silently swallowed.
   ========================================================================== */
const TENANT_DEFAULTS = {
  /* --- identity ---------------------------------------------------------- */
  productName: B("CareJioX", "CareJioX"),
  clinicName: B("Việt Úc Care", "Việt Úc Care"),
  clinicShort: B("Việt Úc", "Việt Úc"),

  /* --- how people reach this clinic -------------------------------------- */
  hotline: B("1900 xxxx", "1900 xxxx"),
  supportEmail: B("cskh@vietuccare.vn", "cskh@vietuccare.vn"),
  website: B("pkgdvietuc.com", "pkgdvietuc.com"),
  oaNameNorth: B("Việt Úc Care – Hà Nội", "Việt Úc Care – Hà Nội"),
  oaNameSouth: B("Việt Úc Care – TPHCM", "Việt Úc Care – TPHCM"),

  /* --- geography ---------------------------------------------------------- */
  areaNorth: B("Hà Nội", "Hà Nội"),
  areaSouth: B("TPHCM", "TPHCM"),

  /* --- who to escalate to, in this clinic's own words --------------------- */
  roleHeadNurse: B("Head Nurse", "Điều dưỡng trưởng"),
  roleOpsManager: B("Operations Manager", "Quản lý vận hành"),
  roleDutyDoctor: B("Duty Doctor", "Bác sĩ trực"),
  roleReception: B("CRM / Reception", "CRM / Lễ tân"),

  /* --- who to ask for things the tutorial tells you to ask for ------------ */
  accessRequestPath: B("your Operations Manager", "Quản lý vận hành của bạn"),
  itContact: B("the IT team", "bộ phận CNTT"),
  contentOwner: B("Product", "bộ phận Sản phẩm"),

  /* --- shift shape, so lessons can say "before handover" concretely ------- */
  shiftStart: B("07:30", "07:30"),
  shiftEnd: B("17:30", "17:30"),
  handoverTime: B("17:00", "17:00"),
  quietHours: B("13:00–14:00", "13:00–14:00"),

  /* --- policy names a clinic may call something else ---------------------- */
  consentPolicyName: B("the Data Sharing consent", "đồng thuận chia sẻ dữ liệu"),
  phiPolicyName: B("the patient information policy", "quy định thông tin bệnh nhân"),

  /* --- money / locale ----------------------------------------------------- */
  currency: B("₫", "₫"),
  replySlaMinutes: B("15", "15"),
};

/* What a tenant has actually overridden. Empty here — the prototype ships the
   defaults, which is the point: the tutorial must be fully usable at a brand
   new tenant with zero configuration. */
const TENANT_OVERRIDES = {};

/* Resolution order: tenant value -> default -> the key itself (visible on
   purpose, so a typo is obvious rather than rendering an empty gap). */
function tenantValue(key, lang) {
  const src = TENANT_OVERRIDES[key] || TENANT_DEFAULTS[key];
  if (!src) return "{{" + key + "}}";
  return src[lang] || src.en || ("{{" + key + "}}");
}

/* =============================================================================
   1. THE WORKED CASE — one story, every number reconciles.
   -----------------------------------------------------------------------------
   Urgency arithmetic is NOT invented: it is the stored compute at
   addons/health_care_command/models/care_conversation.py::_compute_urgency_score
       needs_reply +40 · booking within 24h +30 · unread>0 +15
       · unhandled missed call +10 · watch phrase +15
       · ageing min(20, whole hours since last inbound)
   Contract id: `urgency-terms`.
   ========================================================================== */
const CASE = {
  now: B("Wednesday 12 August 2026 · 08:00", "Thứ Tư, 12 tháng 8 năm 2026 · 08:00"),
  area: B("Hà Nội", "Hà Nội"),
  convId: 4172,
  // The person who messaged us — the CLIENT'S DAUGHTER, not the client.
  sender: B("Trần Mỹ Linh", "Trần Mỹ Linh"),
  senderRel: B("daughter of the client", "con gái của khách hàng"),
  client: B("Nguyễn Thị Hoa", "Nguyễn Thị Hoa"),
  clientAge: 78,
  phone: "+84 912 345 678",
  oa: B("Việt Úc Care – Hà Nội (Zalo OA)", "Việt Úc Care – Hà Nội (Zalo OA)"),
  msg: B("Mum's wound smells bad and she's short of breath since last night — is the wound infected?",
         "Vết thương của mẹ tôi có mùi và từ tối qua mẹ bị khó thở — có phải vết thương nhiễm trùng không ạ?"),
  watchTerm: B("shortness of breath (\"khó thở\")", "khó thở"),
  service: B("Wound care at home", "Chăm sóc vết thương tại nhà"),
  serviceMins: 60,
  servicePrice: 450000,
  packageVisits: 8,
  packagePrice: 3400000,
  bookingAt: B("Wed 12 Aug, 16:30", "Thứ Tư 12/8, 16:30"),
  // Contract id: `urgency-terms`. These six sum to the score shown everywhere.
  urgency: [
    { k: B("Status is “Needs reply”", "Trạng thái “Cần trả lời”"), v: 40 },
    { k: B("A booking falls inside the next 24 hours", "Có lịch hẹn trong vòng 24 giờ tới"), v: 30 },
    { k: B("Unread inbound messages (2)", "Tin nhắn đến chưa đọc (2)"), v: 15 },
    { k: B("An unhandled missed call (07:55)", "Cuộc gọi nhỡ chưa xử lý (07:55)"), v: 10 },
    { k: B("A watch phrase matched: “khó thở”", "Khớp cụm từ cảnh báo: “khó thở”"), v: 15 },
    { k: B("Ageing — 0 whole hours since 07:42", "Thời gian chờ — 0 giờ tròn kể từ 07:42"), v: 0 },
  ],
  urgencyTotal: 110,
  urgencyLater: 114,
  urgencyLaterAt: B("11:42 — four whole hours after the last inbound, the ageing term becomes +4.",
                    "11:42 — bốn giờ tròn sau tin nhắn đến cuối cùng, thành phần thời gian chờ thành +4."),
  // The seeded judgement in Mission 1. Contract id: `consent-types`.
  consentType: B("Data Sharing", "Chia sẻ dữ liệu"),
  consentState: B("Withdrawn on 30 June 2026", "Đã thu hồi ngày 30/6/2026"),
  // Month figures. 224 = 14 + 210; 210 = 63 + 129 + 18.
  month: {
    total: 224, spam: 14, real: 210, booking: 63, lead: 129, lost: 18,
    conversion: 30.0, spamRate: 6.3,
  },
  kpis: { contactsToday: 24, pendingFollowups: 9, activeLeads: 31, bookingsWeek: 46 },
  // Source channels this month — sums to 224. Contract id: `channel-selection`.
  channels: [
    { id: "zalo", label: B("Zalo", "Zalo"), n: 96 },
    { id: "call", label: B("Hotline", "Tổng đài"), n: 58 },
    { id: "webchat", label: B("Website form", "Biểu mẫu website"), n: 34 },
    { id: "fb", label: B("Facebook", "Facebook"), n: 21 },
    { id: "walk_in", label: B("Walk-in", "Đến trực tiếp"), n: 9 },
    { id: "referral", label: B("Referral", "Giới thiệu"), n: 6 },
  ],
  // The 34 website-form enquiries, split by attribution. 19 + 11 + 4 = 34.
  attribution: [
    { c: "vn-home-nursing-hanoi", src: "google / cpc", n: 19 },
    { c: "fb-wound-care-aug", src: "facebook / paid", n: 11 },
    { c: B("— no UTM captured —", "— không có UTM —"), src: B("unmatched", "chưa khớp"), n: 4 },
  ],
  wall: { open: 12, needsReply: 7, unclaimed: 3 },
  unrouted: 3,
};

/* =============================================================================
   2. PRACTICE RECORDS — what the simulated screens render.
   -----------------------------------------------------------------------------
   Previously these were literals inside the screen renderers. They live here so
   that a product change is a ONE-FILE edit, and so `check_contract.py` can
   validate their status/state values against the real selections.
   ========================================================================== */
const PRACTICE = {

  /* care.conversation rows. `status` ∈ contract `conversation-status`.
     `channel` ∈ contract `channel-selection`. `urgency` follows `urgency-terms`. */
  conversations: [
    { id: 4172, name: B("Trần Mỹ Linh", "Trần Mỹ Linh"), channel: "zalo", status: "needs_reply",
      urgency: 110, owner: null, anchor: "cc-row-4172",
      note: B("watch: khó thở · booking 16:30", "cảnh báo: khó thở · lịch hẹn 16:30") },
    { id: 4168, name: B("Phạm Quốc Anh", "Phạm Quốc Anh"), channel: "call", status: "needs_reply",
      urgency: 62, owner: null,
      note: B("missed call · no booking", "gọi nhỡ · chưa có lịch hẹn") },
    { id: 4166, name: B("Lê Thị Bích", "Lê Thị Bích"), channel: "webchat", status: "needs_reply",
      urgency: 55, owner: null,
      note: B("unread ×1", "chưa đọc ×1") },
    { id: 4159, name: B("Đỗ Văn Hưng", "Đỗ Văn Hưng"), channel: "fb", status: "needs_reply",
      urgency: 43, owner: null,
      note: B("waiting on our reply since yesterday", "chờ phản hồi từ hôm qua") },
    { id: 4141, name: B("Vũ Thị Mai", "Vũ Thị Mai"), channel: "email", status: "waiting",
      urgency: 21, owner: B("Ngọc", "Ngọc"),
      note: B("claimed by Ngọc", "Ngọc đang xử lý") },
  ],

  /* The merged timeline of conversation #4172, composed read-time in the real
     product from the Zalo thread and the call log. */
  timeline: [
    { kind: "sys", text: B("Zalo · Việt Úc Care – Hà Nội (OA)", "Zalo · Việt Úc Care – Hà Nội (OA)") },
    { kind: "in", ts: "07:42",
      text: B("Hello, I'm Hoa's daughter. Is the nurse still coming this afternoon?",
              "Chào anh/chị, tôi là con gái bà Hoa. Chiều nay điều dưỡng vẫn đến chứ ạ?") },
    { kind: "in", ts: "07:43", anchor: "cc-watch-4172", text: CASE.msg },
    { kind: "sys", text: B("Missed call from +84 912 345 678 · 07:55",
                           "Cuộc gọi nhỡ từ +84 912 345 678 · 07:55") },
  ],

  /* crm.lead rows. `status` ∈ contract `contact-status`. */
  contacts: [
    { name: CASE.client, status: "booking", tone: "g",
      meta: B("Zalo · wound care · booking 16:30 today", "Zalo · chăm sóc vết thương · lịch hẹn 16:30 hôm nay") },
    { name: B("Phạm Quốc Anh", "Phạm Quốc Anh"), status: "lead", tone: "b",
      meta: B("Hotline · IV infusion enquiry", "Tổng đài · hỏi truyền dịch") },
    { name: B("Lê Thị Bích", "Lê Thị Bích"), status: "active", tone: "",
      meta: B("Website form · google / cpc", "Biểu mẫu web · google / cpc") },
    { name: B("Đỗ Văn Hưng", "Đỗ Văn Hưng"), status: "thinking", tone: "a",
      meta: B("Facebook · palliative care", "Facebook · chăm sóc giảm nhẹ") },
    { name: B("Vũ Thị Mai", "Vũ Thị Mai"), status: "recontact", tone: "a",
      meta: B("Email · asked us to call back next week", "Email · nhờ gọi lại tuần sau") },
    { name: B("Unknown caller", "Người gọi không rõ"), status: "spam", tone: "r",
      meta: B("Hotline · advertising", "Tổng đài · quảng cáo") },
  ],

  /* care.channel.connection rows. `state` ∈ contract `connection-states`. */
  channels: [
    { id: "zalo-hn", a: "ch-card-zalo-hn", glyph: "message-circle", group: "zalo",
      name: B("Zalo · Việt Úc Care – Hà Nội", "Zalo · Việt Úc Care – Hà Nội"),
      state: "ready", areaAnchor: true,
      meta: B("OA id 3771554 · catchment Hà Nội · 96 messages this month",
              "OA id 3771554 · khu vực Hà Nội · 96 tin nhắn tháng này") },
    { id: "zalo-hcm", a: "ch-card-zalo-hcm", glyph: "message-circle", group: "zalo",
      name: B("Zalo · Việt Úc Care – TPHCM", "Zalo · Việt Úc Care – TPHCM"),
      state: "expiring",
      meta: B("OA id 4009182 · grant expires in 6 days · still sending today",
              "OA id 4009182 · quyền hết hạn sau 6 ngày · hôm nay vẫn gửi được") },
    { id: "fb", a: "ch-card-fb", glyph: "message-circle", group: "fb",
      name: B("Messenger · Việt Úc Care", "Messenger · Việt Úc Care"),
      state: "action_required",
      meta: B("Permission lost at the provider · neither sends nor receives",
              "Đã mất quyền ở phía nhà cung cấp · không gửi cũng không nhận") },
    { id: "email", a: "ch-card-email", glyph: "mail", group: "email",
      name: B("Email · cskh@vietuccare.vn", "Email · cskh@vietuccare.vn"),
      state: "ready",
      meta: B("Verified · 18 threads this month", "Đã xác minh · 18 luồng tháng này") },
    { id: "call", a: "ch-card-call", glyph: "phone", group: "call",
      name: B("Calls · hotline 1900 xxxx", "Cuộc gọi · tổng đài 1900 xxxx"),
      state: "ready",
      meta: B("58 calls this month", "58 cuộc gọi tháng này") },
    { id: "zns", a: "ch-card-zns", glyph: "send", group: "zns",
      name: B("ZNS · templated notifications", "ZNS · thông báo theo mẫu"),
      state: "not_connected",
      meta: B("Adapter available · no tenant credentials configured",
              "Có bộ chuyển đổi · chưa cấu hình thông tin xác thực") },
    { id: "wa", a: "ch-card-wa", glyph: "message-circle", group: "whatsapp",
      name: B("WhatsApp", "WhatsApp"), state: "not_connected",
      meta: B("Adapter available · no tenant credentials configured",
              "Có bộ chuyển đổi · chưa cấu hình thông tin xác thực") },
    { id: "tg", a: "ch-card-tg", glyph: "send", group: "telegram",
      name: B("Telegram", "Telegram"), state: "not_connected",
      meta: B("Adapter available · no tenant credentials configured",
              "Có bộ chuyển đổi · chưa cấu hình thông tin xác thực") },
    { id: "web", a: "ch-card-web", glyph: "globe", group: "webchat",
      name: B("Web chat", "Web chat"), state: "not_connected",
      meta: B("Adapter available · no tenant credentials configured",
              "Có bộ chuyển đổi · chưa cấu hình thông tin xác thực") },
  ],

  /* care.channel.readiness.check rows for the Hà Nội OA. */
  readiness: [
    { l: B("Credentials valid", "Thông tin xác thực hợp lệ"), pass: true },
    { l: B("Webhook verified", "Webhook đã xác minh"), pass: true },
    { l: B("Send permission granted", "Đã có quyền gửi"), pass: true },
    { l: B("Official Account selected", "Đã chọn Official Account"), pass: true },
  ],

  /* The two Official Accounts the provider returns during re-authorisation.
     Ordered by creation date, exactly as the provider returns them — which is
     why TPHCM comes first and Mission 2's anomaly works. */
  oaChoices: [
    { id: "hcm", correct: false, label: B("Việt Úc Care – TPHCM  ·  OA id 4009182  ·  verified",
                                          "Việt Úc Care – TPHCM  ·  OA id 4009182  ·  đã xác minh") },
    { id: "hn", correct: true, label: B("Việt Úc Care – Hà Nội  ·  OA id 3771554  ·  verified",
                                        "Việt Úc Care – Hà Nội  ·  OA id 3771554  ·  đã xác minh") },
  ],

  /* care.contact.capture rows. `anchored` = has a contact/phone/email, i.e.
     Convert is allowed. */
  captures: [
    { anchored: false,
      what: B("Facebook page comment · “có nhận chăm sóc ở Long Biên không?”",
              "Bình luận trang Facebook · “có nhận chăm sóc ở Long Biên không?”"),
      got: B("Ad account 88213 · no phone, no profile id",
             "Tài khoản quảng cáo 88213 · không số điện thoại, không id hồ sơ") },
    { anchored: true, anchorA: true,
      what: B("Web form · partial submit", "Biểu mẫu web · gửi thiếu"),
      got: B("Phone +84 987 654 321 · no name", "Điện thoại +84 987 654 321 · không tên") },
    { anchored: true,
      what: B("Zalo · message to an OA still in setup", "Zalo · tin nhắn tới OA đang thiết lập"),
      got: B("Zalo user id captured", "Đã ghi nhận id người dùng Zalo") },
  ],

  /* mail.activity rows, grouped by activity type. Sums to CASE.kpis.pendingFollowups. */
  activities: [
    { type: B("To-Do", "Việc cần làm"), icon: "list-checks", n: 4 },
    { type: B("Call", "Cuộc gọi"), icon: "phone", n: 3 },
    { type: B("Meeting", "Cuộc họp"), icon: "users", n: 1 },
    { type: B("Email", "Email"), icon: "mail", n: 1 },
  ],

  /* Lead Analysis pivot: effective channel × contact status. Row totals match
     CASE.channels; column totals match CASE.month. */
  pivot: [
    { ch: B("Zalo", "Zalo"), booked: 31, lead: 52, lost: 8, spam: 5, total: 96 },
    { ch: B("Hotline", "Tổng đài"), booked: 19, lead: 31, lost: 5, spam: 3, total: 58 },
    { ch: B("Website", "Website"), booked: 8, lead: 22, lost: 3, spam: 1, total: 34 },
    { ch: B("Facebook", "Facebook"), booked: 3, lead: 14, lost: 1, spam: 3, total: 21 },
    { ch: B("Walk-in", "Đến trực tiếp"), booked: 1, lead: 7, lost: 1, spam: 0, total: 9 },
    { ch: B("Referral", "Giới thiệu"), booked: 1, lead: 3, lost: 0, spam: 2, total: 6 },
  ],

  /* Recent-contacts feed on the Dashboard. */
  recent: [
    { name: CASE.sender, meta: B("Zalo · 07:42", "Zalo · 07:42"), tone: "r" },
    { name: B("Phạm Quốc Anh", "Phạm Quốc Anh"), meta: B("Hotline · 07:20", "Tổng đài · 07:20"), tone: "a" },
    { name: B("Lê Thị Bích", "Lê Thị Bích"), meta: B("Website · 06:58", "Website · 06:58"), tone: "b" },
  ],
};


/* =============================================================================
   OPS — one day, seen four ways.

   Wednesday 12 August 2026, Hà Nội. The SAME day as the CRM worked case, on
   purpose: conversation #4172's 16:30 wound-care visit for Nguyễn Thị Hoa is
   booking B-4471 below, so a learner who did the CRM lessons meets the same
   patient from the other side of the desk.

   Everything reconciles:
     14 bookings today = 13 assigned + 1 unassigned
     13 assigned      = Ngọc 5 + Lan 4 + Hà 3 + Tuấn 1
     states           = 2 completed + 3 in progress + 8 assigned/new + 1 cancelled
   Change any figure here and change it everywhere — check_contract.py guards
   the state vocabulary, and the lessons quote these totals directly.
   ========================================================================== */
const OPS = {
  day: B("Wednesday 12 August 2026", "Thứ Tư, 12 tháng 8 năm 2026"),
  area: B("Hà Nội", "Hà Nội"),

  totals: { bookings: 14, assigned: 13, unassigned: 1, completed: 2,
            inProgress: 3, cancelled: 1, staffOnShift: 4 },

  /* Backend states are the product's own: draft · confirmed (New Booking) ·
     assigned · in_progress · completed · completed_pending_invoice ·
     cancelled · closed. */
  staff: [
    { id: "ngoc", name: B("Ngọc", "Ngọc"), role: B("Nurse", "Điều dưỡng"), load: 5, cap: 6 },
    { id: "lan",  name: B("Lan", "Lan"),   role: B("Nurse", "Điều dưỡng"), load: 4, cap: 6 },
    { id: "ha",   name: B("Hà", "Hà"),     role: B("Nurse", "Điều dưỡng"), load: 3, cap: 6 },
    { id: "tuan", name: B("Tuấn", "Tuấn"), role: B("Nurse", "Điều dưỡng"), load: 1, cap: 6 },
  ],

  bookings: [
    { ref: "B-4468", time: "08:00", staff: "ngoc", state: "completed",
      client: B("Phạm Quốc Anh", "Phạm Quốc Anh"), svc: B("Wound care", "Chăm sóc vết thương"),
      district: B("Ba Đình", "Ba Đình"), anchor: "ob-row-4468" },
    { ref: "B-4469", time: "09:00", staff: "lan", state: "completed",
      client: B("Lê Thị Bích", "Lê Thị Bích"), svc: B("Injection", "Tiêm"),
      district: B("Đống Đa", "Đống Đa") },
    { ref: "B-4470", time: "10:30", staff: "ngoc", state: "in_progress",
      client: B("Đỗ Văn Hưng", "Đỗ Văn Hưng"), svc: B("Physiotherapy", "Vật lý trị liệu"),
      district: B("Ba Đình", "Ba Đình") },
    { ref: "B-4471", time: "16:30", staff: "lan", state: "assigned",
      client: B("Nguyễn Thị Hoa", "Nguyễn Thị Hoa"), svc: B("Wound care at home", "Chăm sóc vết thương tại nhà"),
      district: B("Cầu Giấy", "Cầu Giấy"), anchor: "ob-row-4471", flag: "crm" },
    { ref: "B-4472", time: "11:00", staff: "ha", state: "in_progress",
      client: B("Vũ Thị Mai", "Vũ Thị Mai"), svc: B("Blood draw", "Lấy máu"),
      district: B("Hai Bà Trưng", "Hai Bà Trưng") },
    { ref: "B-4473", time: "14:00", staff: "tuan", state: "assigned",
      client: B("Trần Văn Sơn", "Trần Văn Sơn"), svc: B("Wound care", "Chăm sóc vết thương"),
      district: B("Long Biên", "Long Biên") },
    { ref: "B-4474", time: "15:00", staff: false, state: "confirmed",
      client: B("Hoàng Thị Yến", "Hoàng Thị Yến"), svc: B("Injection", "Tiêm"),
      district: B("Cầu Giấy", "Cầu Giấy"), anchor: "ob-unassigned" },
    { ref: "B-4475", time: "13:00", staff: "ngoc", state: "assigned",
      client: B("Bùi Văn Khoa", "Bùi Văn Khoa"), svc: B("Catheter care", "Chăm sóc ống thông"),
      district: B("Ba Đình", "Ba Đình") },
    { ref: "B-4476", time: "17:00", staff: "lan", state: "assigned",
      client: B("Ngô Thị Lý", "Ngô Thị Lý"), svc: B("Wound care", "Chăm sóc vết thương"),
      district: B("Đống Đa", "Đống Đa") },
    { ref: "B-4477", time: "12:00", staff: "ha", state: "in_progress",
      client: B("Đặng Thị Mai", "Đặng Thị Mai"), svc: B("Injection", "Tiêm"),
      district: B("Hai Bà Trưng", "Hai Bà Trưng") },
    { ref: "B-4478", time: "18:00", staff: "lan", state: "assigned",
      client: B("Lý Văn Phúc", "Lý Văn Phúc"), svc: B("Physiotherapy", "Vật lý trị liệu"),
      district: B("Đống Đa", "Đống Đa") },
    { ref: "B-4479", time: "09:30", staff: "ngoc", state: "assigned",
      client: B("Huỳnh Nhi", "Huỳnh Nhi"), svc: B("Blood draw", "Lấy máu"),
      district: B("Ba Đình", "Ba Đình") },
    { ref: "B-4480", time: "16:00", staff: "ha", state: "assigned",
      client: B("Quách Hải Yến", "Quách Hải Yến"), svc: B("Wound care", "Chăm sóc vết thương"),
      district: B("Hai Bà Trưng", "Hai Bà Trưng") },
    { ref: "B-4481", time: "10:00", staff: "ngoc", state: "cancelled",
      client: B("Trần Thanh Tâm", "Trần Thanh Tâm"), svc: B("Injection", "Tiêm"),
      district: B("Ba Đình", "Ba Đình") },
  ],

  timeoff: [
    { who: "ha",   from: "13/08", to: "13/08", kind: B("Annual leave", "Nghỉ phép"), state: B("Requested", "Chờ duyệt") },
    { who: "tuan", from: "14/08", to: "16/08", kind: B("Annual leave", "Nghỉ phép"), state: B("Approved", "Đã duyệt") },
  ],

  /* Cash the nurses are holding right now. Reconciled by OPERATIONS at end of
     shift; Finance receives a balanced figure and never chases a nurse. */
  collections: [
    { who: "ngoc", amount: 620000, visits: 2 },
    { who: "lan",  amount: 450000, visits: 1 },
    { who: "ha",   amount: 280000, visits: 1 },
  ],
  collectionsTotal: 1350000,

  family: [
    { client: B("Nguyễn Thị Hoa", "Nguyễn Thị Hoa"), from: B("Trần Mỹ Linh (daughter)", "Trần Mỹ Linh (con gái)"),
      text: B("Will the nurse still come this afternoon?", "Chiều nay điều dưỡng vẫn đến chứ ạ?"), unread: true },
    { client: B("Vũ Thị Mai", "Vũ Thị Mai"), from: B("Vũ Anh Tú (son)", "Vũ Anh Tú (con trai)"),
      text: B("Thank you for this morning.", "Cảm ơn vì buổi sáng nay."), unread: false },
  ],

  /* The seeded anomaly for the OPS mission: the obvious reassignment breaks
     travel feasibility. Tuấn finishes in Long Biên at 15:00; B-4471 is in Cầu
     Giấy at 16:30 and the leg is 50 minutes. It FITS the calendar and does not
     fit the map — and the checker warns rather than blocks, on purpose. */
  travel: { fromDistrict: B("Long Biên", "Long Biên"), toDistrict: B("Cầu Giấy", "Cầu Giấy"),
            minutes: 50, gapMinutes: 90, feasible: true,
            note: B("Fits, but only just — 40 minutes of slack in Hà Nội afternoon traffic.",
                    "Vừa đủ, nhưng rất sát — chỉ dư 40 phút trong giờ cao điểm buổi chiều ở Hà Nội.") },
};


/* =============================================================================
   FIN — one month of money, and it ties to the other two sections.

   August 2026, Hà Nội. The 63 invoices are the 63 bookings the CRM month
   converted, and the 1,350,000 ₫ in transit is the cash the OPS nurses are
   holding at the end of 12 August. Three sections, one clinic, one set of
   numbers.

   Everything reconciles:
     63 invoices  = 28 wound care + 20 injection + 10 physio + 5 blood draw
     25,850,000 ₫ = 19,700,000 paid + 6,150,000 outstanding
     overdue (4 invoices, 1,850,000 ₫) is a SUBSET of the outstanding 15

   Deliberately NOT asserted: any VAT rate. Healthcare VAT treatment in Vietnam
   is a tax question, not a UI question, and the tutorial has no business
   teaching it from a guess. The VAT Log lesson teaches what the screen IS —
   a read-only record of what was posted — which is what the code shows.
   ========================================================================== */
const FIN = {
  month: B("August 2026", "Tháng 8 năm 2026"),
  area: B("Hà Nội", "Hà Nội"),

  invoices: { count: 63, billed: 25850000, paid: 19700000, outstanding: 6150000,
              paidCount: 48, outstandingCount: 15 },
  overdue: { count: 4, amount: 1850000, oldestDays: 47 },
  inTransit: 1350000,

  lines: [
    { svc: B("Wound care at home", "Chăm sóc vết thương tại nhà"), n: 28, price: 450000 },
    { svc: B("Injection", "Tiêm"), n: 20, price: 300000 },
    { svc: B("Physiotherapy", "Vật lý trị liệu"), n: 10, price: 600000 },
    { svc: B("Blood draw", "Lấy máu"), n: 5, price: 250000 },
  ],

  /* A red invoice is a Vietnamese tax document. Issued on request, not on
     every invoice — 41 of the 63 asked for one. */
  red: { issued: 41, cancelled: 1, pending: 0,
         rule: B("Cancel and reissue only for wrong buyer details, amount or service description, and only inside the current filing period. After the period closes the route is a credit note.",
                 "Chỉ hủy và phát hành lại khi sai thông tin người mua, số tiền hoặc mô tả dịch vụ, và chỉ trong kỳ kê khai hiện tại. Sau khi kỳ khai đã đóng thì phải dùng hóa đơn điều chỉnh.") },

  /* Three refunds, three genuinely different situations. This is the whole
     point of the FINANCE mission. */
  refunds: [
    { id: "R-101", route: "prepaid", amount: 900000,
      client: B("Lê Thị Bích", "Lê Thị Bích"),
      why: B("Bought 5 visits of credit, used 3, moved away.", "Mua trước 5 lượt, dùng 3, rồi chuyển đi nơi khác."),
      anchor: "fr-prepaid" },
    { id: "R-102", route: "package", amount: 1800000,
      client: B("Đỗ Văn Hưng", "Đỗ Văn Hưng"),
      why: B("An 8-visit physiotherapy course stopped after 4 on clinical advice.",
             "Liệu trình vật lý trị liệu 8 buổi dừng sau 4 buổi theo chỉ định chuyên môn."),
      anchor: "fr-package" },
    { id: "R-103", route: "transaction", amount: 450000,
      client: B("Vũ Thị Mai", "Vũ Thị Mai"),
      why: B("Paid twice for the same visit — one payment was keyed in on the wrong record.",
             "Thanh toán hai lần cho cùng một lượt — một khoản bị nhập nhầm vào hồ sơ khác."),
      anchor: "fr-transaction" },
  ],

  /* Not live. Written honestly as a preview rather than teaching a workflow
     nobody runs. */
  bhyt: { live: false, claims: 0 },

  packages: [
    { name: B("Wound care · 8 visits", "Chăm sóc vết thương · 8 buổi"), sold: 6, price: 3200000 },
    { name: B("Physiotherapy · 8 visits", "Vật lý trị liệu · 8 buổi"), sold: 4, price: 4400000 },
  ],
};

/* =============================================================================
   3. THE REAL SIDEBAR — CRM section, as the database actually holds it.
   -----------------------------------------------------------------------------
   Contract id: `crm-sidebar-items` (xml-ids + sequences + EN labels) and
   `crm-sidebar-labels-vi` (the shipped Vietnamese strings).

   Sources (sequence · xml-id · file):
     10 · health_cms_sidebar.item_crm_dashboard        data/cms_sidebar_items_crm.xml
     11 · health_care_command.item_care_command        data/cms_sidebar_items_care_command.xml
     12 · ..._channels.item_channel_center             data/cms_sidebar_items_channel_center.xml
     13 · ..._channels.item_contact_capture            data/cms_sidebar_items_contact_capture.xml
     20 · health_cms_sidebar.item_crm_contacts         data/cms_sidebar_items_crm.xml
     21 · health_web_leads.item_web_touchpoints        data/cms_sidebar_items_web_leads.xml
     23 · health_web_leads.item_lead_analysis          data/cms_sidebar_items_web_leads.xml
     50 · health_cms_sidebar.item_crm_activities       data/cms_sidebar_items_crm.xml

   `roles` is the DB role gate (access.role rows have no xml-id — see
   health_cms_coverage/hooks.py). Contract id: `crm-role-gate`.
   ========================================================================== */
const MENU = [
  {
    key: "crm", label: B("CRM", "CRM"),
    items: [
      { id: "dashboard", icon: "grid", seq: 10, label: B("Dashboard", "Bảng điều khiển"), roles: ["owner", "crm"] },
      { id: "carecommand", icon: "zap", seq: 11, label: B("Care Command", "Care Command"), roles: ["owner", "crm"] },
      { id: "channelcenter", icon: "plug", seq: 12, label: B("Channel Center", "Trung tâm kênh"), roles: null },
      { id: "unrouted", icon: "inbox", seq: 13, label: B("Unrouted Contacts", "Danh bạ chưa được định tuyến"), roles: null },
      { id: "contacts", icon: "phone", seq: 20, label: B("Contacts", "Liên hệ"), roles: ["owner", "crm"] },
      { id: "touchpoints", icon: "crosshair", seq: 21, label: B("Web Touchpoints", "Điểm chạm web"), roles: null },
      { id: "leadanalysis", icon: "bar-chart", seq: 23, label: B("Lead Analysis", "Phân tích khách tiềm năng"), roles: null },
      { id: "activities", icon: "list-checks", seq: 50, label: B("Activities", "Hoạt động"), roles: ["owner", "crm"] },
    ],
  },
  /* The other two sections carry their REAL leaves, with ids that are station
     keys. Two reasons this is not decoration:

     1. The shell titles the screen from this list, so a stub section left the
        heading blank on every OPS practice screen.
     2. Whether a section is greyed is now decided by which section owns the
        screen on display, not by a flag frozen at authoring time — so one
        MENU serves a CRM lesson, an OPS mission and a FINANCE mission. */
  {
    key: "ops", label: B("OPERATIONS MANAGER", "QUẢN LÝ VẬN HÀNH"),
    items: [
      { id: "ops_dashboard", icon: "grid", label: B("Dashboard", "Bảng điều khiển") },
      { id: "ops_bookings", icon: "calendar", label: B("Bookings", "Lịch hẹn") },
      { id: "ops_clients", icon: "users", label: B("Clients", "Khách hàng") },
      { id: "ops_timeoff", icon: "clock", label: B("Time Off", "Nghỉ phép") },
      { id: "ops_schedule", icon: "users", label: B("Staff Schedule", "Lịch nhân sự") },
      { id: "ops_collections", icon: "receipt", label: B("Collections", "Thu tiền mặt") },
      { id: "ops_workload", icon: "bar-chart", label: B("Workload", "Khối lượng công việc") },
      { id: "ops_family", icon: "message-circle", label: B("Family Inbox", "Hộp thư người nhà") },
      { id: "ops_routes", icon: "map", label: B("Route Feasibility", "Khả năng di chuyển") },
    ],
  },
  {
    key: "fin", label: B("FINANCE", "TÀI CHÍNH"),
    items: [
      { id: "fin_dashboard", icon: "grid", label: B("Dashboard", "Bảng điều khiển") },
      { id: "fin_invoices", icon: "receipt", label: B("Invoices", "Hóa đơn") },
      { id: "fin_account_payment", icon: "check-circle", label: B("Account Payment", "Thanh toán tài khoản") },
      { id: "fin_cash_transit", icon: "receipt", label: B("Cash In Transit", "Tiền đang chuyển") },
      { id: "fin_refund", icon: "rotate-ccw", label: B("Refund / Credit", "Hoàn tiền / Điều chỉnh") },
      { id: "fin_ar_dashboard", icon: "bar-chart", label: B("AR Dashboard", "Bảng công nợ") },
      { id: "fin_ar_management", icon: "clipboard-check", label: B("AR Management", "Quản lý công nợ") },
      { id: "fin_payments", icon: "check-circle", label: B("Payments", "Thanh toán") },
      { id: "fin_overdue", icon: "alert-triangle", label: B("Overdue Clients", "Khách hàng quá hạn") },
      { id: "fin_vat_log", icon: "file-text", label: B("VAT Log", "Nhật ký hóa đơn VAT") },
      { id: "fin_ar_transactions", icon: "list-checks", label: B("AR Transactions", "Giao dịch công nợ") },
      { id: "fin_bhyt", icon: "clipboard-check", label: B("BHYT Claims", "Hồ sơ BHYT") },
      { id: "fin_packages", icon: "list-checks", label: B("Service Packages", "Gói dịch vụ") },
      { id: "fin_red_invoice", icon: "shield-check", label: B("Red Invoice Log", "Nhật ký hóa đơn đỏ") },
    ],
  },
];

/* Leaves that USED to be in CRM and no longer are — the 19.0.1.2.0 menu
   consolidation (health_cms_coverage/hooks.py RETIRE / RELOCATE_TO_ADMIN).
   Contract id: `crm-retired`. */
const RETIRED = [
  { label: B("Follow-up Calendar", "Lịch theo dõi"), now: B("a calendar view mode on Contacts", "một chế độ xem lịch trên màn hình Liên hệ") },
  { label: B("Relationships", "Quan hệ"), now: B("the Client › Healthcare Relationships tab", "thẻ Khách hàng › Quan hệ chăm sóc") },
  { label: B("Campaign Review", "Duyệt chiến dịch"), now: B("the “Unmatched campaigns” chip on Web Touchpoints", "chip “Chiến dịch chưa khớp” trên Điểm chạm web") },
  { label: B("Channels (setup)", "Kênh (thiết lập)"), now: B("moved to ADMIN", "đã chuyển sang QUẢN TRỊ") },
  { label: B("Reply Templates", "Mẫu trả lời"), now: B("moved to ADMIN", "đã chuyển sang QUẢN TRỊ") },
  { label: B("Website Connector", "Kết nối website"), now: B("moved to ADMIN", "đã chuyển sang QUẢN TRỊ") },
];

/* Status/state → chip label + tone, so a renamed selection is one edit here.
   Keys are contract-checked (`contact-status`, `connection-states`). */
const STATUS_LABELS = {
  contact: {
    active: { l: B("New", "Mới"), t: "" },
    lead: { l: B("Lead", "KHTN"), t: "b" },
    booking: { l: B("Appointment Scheduled", "Đã đặt lịch"), t: "g" },
    lost_booking: { l: B("Cancelled", "Đã hủy"), t: "r" },
    spam: { l: B("Spam Call", "Cuộc gọi rác"), t: "r" },
    thinking: { l: B("Thinking / Considering", "Đang cân nhắc"), t: "a" },
    recontact: { l: B("To Be Contacted Again", "Cần liên hệ lại"), t: "a" },
    service_used: { l: B("Service Used", "Đã dùng dịch vụ"), t: "g" },
    existing: { l: B("Existing Client", "Khách hàng hiện có"), t: "g" },
  },
  conversation: {
    needs_reply: { l: B("Needs reply", "Cần trả lời"), t: "r" },
    waiting: { l: B("Waiting", "Đang chờ"), t: "" },
    junk_suspect: { l: B("Junk?", "Thư rác?"), t: "r" },
    closed: { l: B("Closed", "Đã đóng"), t: "" },
  },
  connection: {
    not_connected: { l: B("Not connected", "Chưa kết nối"), t: "" },
    authorizing: { l: B("Signing in", "Đang đăng nhập"), t: "b" },
    select_resource: { l: B("Choosing what to connect", "Chọn nội dung để kết nối"), t: "b" },
    configuring: { l: B("Setting things up", "Đang thiết lập"), t: "b" },
    testing: { l: B("Testing", "Đang kiểm thử"), t: "b" },
    ready: { l: B("Connected", "Đã kết nối"), t: "g" },
    action_required: { l: B("Action required", "Cần xử lý"), t: "r" },
    expiring: { l: B("Expiring soon", "Sắp hết hạn"), t: "a" },
    error: { l: B("Error", "Lỗi"), t: "r" },
    disabled: { l: B("Disabled", "Đã tắt"), t: "" },
    legacy: { l: B("Legacy (not migrated)", "Cũ (chưa chuyển đổi)"), t: "" },
  },
};

export { B, PRACTICE_META, CASE, PRACTICE, MENU, RETIRED, STATUS_LABELS, OPS, FIN };
