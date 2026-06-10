# Strategic Platform Research: Odoo CE vs. Tryton vs. ERPNext/Frappe
### A decision paper for the future technology direction of a UX-first product business

**Prepared:** 2026-06-10 · **Author:** Claude (Opus 4.8) · **Status:** Approved — recommendation adopted (stay on Odoo CE)

---

## Context — why this study exists

You are deciding the foundation for a **multi-product business where UX is the supreme differentiator** and where you will heavily customize on top of a base of ERP-grade modules. You like Odoo Community Edition's development ergonomics, but three doubts pushed you to evaluate alternatives:

1. **Branding** — Odoo's name appearing in URLs/screens dilutes a custom product flavor.
2. **License** — unease about Odoo CE being "open source with restrictions" vs. "truly free" stacks like Tryton.
3. **UX ceiling** — whether layering JS libraries on Odoo CE is *enough*, or whether a headless stack (e.g. Tryton) would let you build a better UI/UX from scratch.

You also asked, candidly, whether I (Claude) actually know these stacks well enough to build on them, or whether you'd need to supply docs/source.

**Your clarifying answers reframed the question decisively:**
- License concern is **mainly branding** (not copyleft obligations) — branding you find acceptable to remove.
- Delivery model is **both SaaS and on-prem (hybrid)**.
- Fate of the existing Odoo health app: **let the findings decide**.
- Top-weighted factors (all four equally): **premium UX ceiling · licensing freedom · my ability to build on the stack · breadth of base modules**.

The single most important finding came not from the web but from your own repository (Section 5). It changes the answer.

---

## Executive summary & recommendation

> **Recommendation: Stay on Odoo Community Edition for the health platform and for your near-term product line. Do not migrate. Reinvest the energy you'd spend migrating into (a) hardening the debrand into a reusable white-label layer and (b) productizing your custom-frontend stack as a repeatable base for future products.**
>
> **Keep one strategic option open:** for a *greenfield* future product where you want a genuinely permissive (MIT) license and a clean modern Vue stack from day one, run a small, time-boxed **Frappe Framework** pilot. It is the only alternative that beats Odoo on a dimension you actually care about (pure license permissiveness) without costing you your existing investment. **Tryton's only compelling pull is GNU Health — and that doesn't outweigh its costs given you've already built your own clinical domain on Odoo.**

**Why, in one paragraph:** Your stated reason to leave (branding) is fully solvable on Odoo CE under LGPL — and *you have already solved it* (five debranding addons in production). Your UX-ceiling worry is also already answered in production: you ship a separate Vue 3 + Quasar offline PWA plus a deeply themed, debranded backend. Migrating means discarding ~1.49M lines of work and 16 health addons to *re-earn* capabilities you already have, on stacks where the base ecosystem is smaller (Tryton) or the proprietary-license advantage only helps *new* code (Frappe). On all four of your weighted factors, the net case favors staying.

---

## 1. The scoring framework

All four factors weighted equally (per your answer). Scores 1–5, higher = better for your goals. A fifth row — *switching cost / existing investment* — is not one of your four factors but is the dominant practical reality, so it's shown separately.

| Factor (equal weight) | **Odoo CE** | **Tryton (+GNU Health)** | **ERPNext / Frappe** |
|---|:--:|:--:|:--:|
| **Premium UX ceiling** | **4.5** — high ceiling; you've *proven it* (Vue PWA + themed backend). Backend shell mildly constrains, but portal/headless paths are unconstrained. | 3.5 — same ceiling *is reachable*, but you must build **100% of the frontend** on JSON-RPC; zero reusable premium UI. | 4.0 — proven by Frappe's own Vue 3 SPAs (CRM/Helpdesk/HR); requires a custom Vue/React frontend (Desk UI is dated). |
| **Licensing freedom** (your sense: *branding*) | **4.5** — LGPL **permits full debranding** (done); proprietary modules OK; SaaS = no disclosure. *Pure-copyleft purists score it 3.5* (trademark + AGPL-contamination + open-core drift). | 3.0 — GPLv3: proprietary only works for **SaaS** (no distribution); **on-prem distribution triggers copyleft** on your modules — and you ship hybrid. | 5.0 — **Frappe Framework is MIT** (truly permissive) *if* you don't import ERPNext/Frappe-Health GPL code; newer products are AGPL — avoid in SaaS. |
| **My (Claude) build capability** | **5.0** — largest training corpus of the three; I'm already productively building in this exact repo (OWL, ORM, XML views, PWA). | 3.0 — competent on architecture + a headless React/Vue frontend, but smaller corpus and thin headless docs; **I'd want you to supply docs/source** for non-standard paths. | 4.0 — solid on DocTypes, Python controllers, Frappe UI/Vue; strong but a notch below Odoo. |
| **Base-module ecosystem** | **5.0** — broadest core (full CE accounting, CRM, inventory, HR, FSM…) + OCA (~260 repos) + **your own 16 health addons**. | 3.5 — clean ~180 modules + **GNU Health** (mature EMR/HMIS/LIMS) for the *health* vertical specifically; general third-party ecosystem is small. | 4.0 — broad ERPNext + **Frappe Health** (FHIR-based, mid-maturity, GPLv3); marketplace smaller than Odoo's. |
| **— Switching cost / existing investment** *(context, not weighted)* | **None — you are already here** | Very high — discard ~1.49M LOC; rebuild frontend wholesale | High — rebuild on a new framework + new frontend |

**Read of the table:** Odoo leads or ties on three of your four factors and is far ahead on the unscored reality (switching cost). Frappe wins *only* "licensing freedom" — and only for **new** code you write fresh on the MIT framework; it cannot retroactively make your existing health app permissive, and the moment you pull in its GPL accounting/health modules the advantage evaporates. Tryton never leads a category for your specific situation.

---

## 2. The licensing reality (your #1 stated concern, resolved)

**Your concern is branding, and branding is the easy part.**

- **Odoo CE is LGPLv3** (since v9; it was AGPL through v8). LGPL is *weak/linking* copyleft: **custom modules kept in separate addons — not patching core — may be licensed proprietary** and never published. (Odoo's own license text endorses "LGPL, MIT, or proprietary" modules.) SaaS use is **not** a disclosure trigger.
- **Debranding is explicitly permitted** by Odoo (their own staff confirm it on the forum; they even host debranding apps on their store). You may remove the name, logo, "Powered by Odoo," favicon, titles, login branding, and alias the `/web`·`/odoo` routes. **The only hard limits:** (1) keep the in-*code* copyright notice (not shown on screen), and (2) the **"Odoo" trademark** — you can't put it in your product/company name or domain. None of that affects a white-labeled product.
- **You have already done this** — `web_debranding`, `portal_debranding`, `mail_debranding`, `pos_debranding`, `website_debranding` are installed (Section 5). Your concern is, in practice, already retired.

### 2.1 Do you ever have to open *your* code? (delivery-model table)

The rule for all three stacks: **copyleft is triggered by *distribution* (handing the software to someone to run themselves), not by using or developing it** — and pure SaaS hosting is *not* distribution (except under AGPL). Because you ship **hybrid (SaaS + on-prem)**, this is decisive.

| Stack | SaaS (you host, users access via browser) | On-prem (customer runs it themselves) |
|---|---|---|
| **Odoo CE** (LGPL) | **Custom modules stay closed** ✅ | **Custom modules stay closed** ✅ |
| **Tryton** (GPL) | **Custom modules stay closed** ✅ | **Must give that customer your module source** ❌ |
| **Frappe** (MIT framework *only*) | Stay closed ✅ | Stay closed ✅ |
| **Frappe** (importing ERPNext / Frappe-Health GPL code) | Stay closed* ✅ | Must open to that customer ❌ |

\*Caveat: Frappe's *newer* products (CRM/Helpdesk) are **AGPL-3.0**, which *does* trigger on SaaS. The bare framework is MIT and safe.

In every case the "common/base" modules are the vendor's own code — already public; you never proactively "open" them. You only share *modifications you make to the core itself*, and only upon distribution. The practical rule on Odoo: **never patch core, always a separate addon → your IP is 100% closed in both delivery modes.**

### 2.2 The counterintuitive headline

**For keeping your own code proprietary, Odoo CE (LGPL) is the *most* permissive of the three — more than Tryton.** Tryton *feels* freer because it's ideologically pure FOSS with no paid Enterprise edition and no vendor lock — but that purity comes *from* strong GPL copyleft, which is **less** friendly to closed custom code in an on-prem/hybrid model. Odoo's "weaker" LGPL is precisely what lets your custom modules stay proprietary even when shipped to a customer's own server. Since you deliver hybrid, **Odoo keeps your IP closed in both modes; Tryton forces it open on-prem** — another mark against migrating to Tryton, not for it.

> **Net:** On *your* definition of the problem (branding), Odoo already wins. On the stricter "pure license" definition, Frappe's MIT framework is best **for new code only**; Tryton's GPL is the most restrictive for your hybrid model.

---

## 3. The UX-ceiling question, answered

**Short answer: yes — the Odoo + custom-JS-layer approach is sufficient, and you have already demonstrated it at production scale.** Migrating to "build a better UI from scratch" on Tryton would not raise your ceiling; it would just make you *rebuild* what you have.

The architectural truth across all three stacks is identical: **a premium, best-in-class UX requires a custom frontend on a headless/API backend — on Odoo, Tryton, *and* Frappe alike.** None of the three ships a premium UI out of the box. The differences are only in *how much you must build* and *how much is reusable*:

- **Odoo:** OWL component framework for deep backend customization **+** an unconstrained website/portal layer **+** full headless access (JSON-RPC today; migrate to the new External JSON-2 API before legacy RPC is removed in Odoo 22 / 2028). You can — and do — run a fully separate SPA/PWA against it. **You already ship a Vue 3 + Quasar offline-first PWA on this exact pattern.** Your UX ceiling is whatever you design; you've proven it's high.
- **Frappe:** Proves the same point from the other side — Frappe's own modern products (CRM, Helpdesk, HR, Gameplan) are **Vue 3 + Frappe UI SPAs** on the same REST backend, because their Desk UI was *"not good"* (their words). So Frappe = build a custom Vue/React frontend = exactly what you already do on Odoo.
- **Tryton:** The most *honest* negative. Default UI (GTK + jQuery/Bootstrap "Sao") is dated and disqualified for a premium product. Headless is clean and endorsed by maintainers, **but you build the entire frontend yourself** against an *under-documented* (if stable) JSON-RPC API, and you must replicate client-behavior contracts (on-change cascades, default sequences) that the official clients honor automatically. Zero reusable premium UI. It's a credible headless backend — but it offers you **no UX advantage over what you already have**, at maximum rebuild cost.

> **Conclusion:** Your instinct that Tryton "gives an opportunity to build a wonderful UI layer on top" is true — but it's *equally* true of Odoo and Frappe, and you've already built that layer on Odoo. The opportunity isn't unique to Tryton; the rebuild cost is.

---

## 4. Can I (Claude) build on these stacks? — honest assessment

You asked for candor, so:

- **Odoo (CE): Strong — highest confidence.** It has the largest presence in my training data of the three, and I'm already building productively in *this* repo (OWL components, ORM models, XML views, QWeb, the PWA, debranding). The one area that's genuinely harder and more version-volatile is the OWL/JS frontend layer — but that's a stack reality, not a knowledge gap, and we're already navigating it.
- **Frappe / ERPNext: Good.** I know the DocType metadata model, Python controllers, client scripts, the REST API, and Frappe UI (Vue 3) well enough to be productive without hand-holding. Slightly below my Odoo fluency, but solid. For a greenfield Frappe pilot I would not need you to supply much beyond the official docs.
- **Tryton: Moderate — I'd want your help.** I understand its architecture well (arguably the cleanest of the three) and I'd be *strong* on the headless frontend (it's just React/Vue against JSON-RPC, my home turf). But Tryton has the smallest corpus in my training, and the community itself notes the headless documentation is incomplete. I could build it, but I'd be most effective if **you supplied current docs/source** (Tryton + GNU Health), and we'd hit more "reverse-engineer from the Sao source" moments than on Odoo.

> **Net:** My capability ranking — **Odoo > Frappe > Tryton** — happens to reinforce the recommendation. On the stack you're already on, I'm at my most effective.

---

## 5. What you've already built (the decisive finding)

A full scan of `health19` shows this is **not** "Odoo with a theme." It is a custom healthcare platform that *happens to run on Odoo*:

- **~16 custom health addons** (`health_base`, `health_crm`, `health_fieldservice`, `health_invoicing`, `health_pwa`, `health_landing`, `health_theme`, plus VOIP/Zalo/roster/red-invoice/flow/CMS/admin) — full clinical, CRM, FSM, billing, and Vietnamese-compliance domain logic.
- **A separate Vue 3 + Quasar offline-first PWA** (`health_pwa`) — PouchDB/IndexedDB sync, service worker, push notifications, fully decoupled from Odoo's web client via REST. Bilingual (Vietnamese-first).
- **A real design system** — `health_theme` (custom SCSS, 100+ design tokens, brand palette, typography) + a **Lucide CSS-mask SVG icon system** (your `hf-wt-ico` pattern).
- **Complete debranding** — five addons removing Odoo branding from backend, portal, email, POS, and website; custom login, titles, favicon, app name.
- **Scale:** ~1.49M total LOC of customization (Python + JS/CSS/SCSS); production version-tracked (PWA SW at 1.0.98).

**Implication:** You have *already executed* the exact strategy this study would otherwise recommend a UX-first business adopt — debranded ERP backend + bespoke modern frontend. Both alternatives would have you **rebuild this from zero** to reach parity, before adding any new value. That is the core economic argument against migrating.

---

## 6. The two alternatives — where they'd actually win (intellectual honesty)

To not just cheerlead Odoo:

- **Frappe Framework (MIT)** genuinely wins **licensing purity for greenfield code** and offers a clean, modern, Vue-first developer story with very fast low-code CRUD via DocTypes. If you start a *brand-new, non-health* product and want zero copyleft from day one on a fresh stack, Frappe is the rational choice to evaluate. It does **not** retroactively help your existing Odoo investment, and its health/ERP modules are GPL.
- **Tryton + GNU Health** genuinely wins **the health domain model as a gift**: GNU Health is a mature, UN-(UNU-IIGH)-adopted EMR/HMIS/LIMS with ~40+ clinical modules and FHIR (read-only) — a real head start *if you were starting health from scratch*. **But you're not** — you've already built your clinical domain on Odoo. Tryton's clean architecture and 5-year LTS cadence are real engineering virtues; they don't overcome the small ecosystem, small talent pool, GPL-on-prem friction, full-frontend-rebuild cost, and my lower fluency.

Neither advantage applies to *your present situation* strongly enough to justify a switch.

---

## 7. Risks of staying on Odoo (and mitigations)

| Risk | Mitigation |
|---|---|
| **Annual breaking releases (~3-yr support)** → re-port cost, concentrated in the JS/OWL layer | Keep custom logic in clean separate addons; isolate the volatile frontend; budget an annual upgrade sprint. Your decoupled Vue PWA already insulates the most UX-critical surface from OWL churn. |
| **AGPL contamination** from a single third-party module | Audit every addon manifest's `license` field; standardize on LGPL/MIT/OCA modules; CI-check licenses. |
| **Open-core drift** (features move to Enterprise) | Your moat is your own 16 addons; you already replace gated pieces (e.g. custom BI/dashboards). Track each Enterprise-gated feature you rely on. |
| **Legacy RPC removed in Odoo 22 (2028)** | Migrate the PWA's integration to the **External JSON-2 API** ahead of time. |
| **Trademark** (can't use "Odoo" in name/domain) | Already moot — you ship under "Viet Uc"/VAFHS branding. |

---

## 8. Recommended strategy & next steps

**Decision:** Stay on Odoo CE; do **not** migrate the health app. (This answers your "let findings decide" on the existing app: keep it.)

**To turn "staying" into a multi-product advantage:**

1. **Productize the debrand + frontend stack into a reusable base.** Extract `health_theme` + the debranding set + the Lucide icon system + the Vue/Quasar PWA shell into a clean, documented **white-label starter** you can fork per product. This is the "base of modules + heavy customization on top" you want — built on what already works.
2. **Lock licensing hygiene.** Add a manifest-license audit (CI) to guarantee no AGPL creeps in; document your "never patch core, always separate addon" rule so proprietary status is provably safe.
3. **Future-proof the integration layer.** Plan the JSON-RPC → External JSON-2 migration for the PWA before Odoo 22.
4. **Keep Frappe as a live option, not a migration.** For the *next greenfield, non-health* product where MIT-purity matters, run a **2–3 week time-boxed Frappe Framework spike** (DocTypes + a Frappe UI/Vue frontend) and compare velocity against your Odoo starter. Decide per-product, not all-or-nothing.
5. **Shelve Tryton** unless a future product is *health-from-scratch* and GNU Health's domain model would save more than the full-frontend rebuild costs — an unlikely combination given your existing Odoo clinical assets.

---

## Verification / how to pressure-test this conclusion

This is a strategy paper, not code, so "verification" means stress-testing the decision before you commit:

- **License safety proof:** run a manifest-license audit across `addons/` to confirm zero AGPL dependencies (validates the "stay proprietary on LGPL" claim end-to-end).
- **UX-parity check:** the live `health_pwa` (Vue 3 + Quasar) and debranded backend already serve as the empirical proof that Odoo+custom-frontend reaches premium UX — review them as Exhibit A.
- **Frappe spike (optional, for the greenfield question only):** stand up a throwaway Frappe bench, model 2–3 DocTypes, wire a Frappe UI/Vue screen, and time it against building the equivalent on your Odoo starter. Let measured velocity — not this paper — settle the greenfield choice.

---

### Appendix — source-backed stack facts (condensed)
- **Odoo CE:** LGPLv3 (proprietary modules OK off-core; SaaS = no disclosure); debranding permitted (trademark + in-code copyright are the limits); OWL/QWeb frontend; full headless RPC (External JSON-2; legacy RPC EOL Odoo 22/2028); broad CE core + OCA (~260 repos); thin/version-lagged free *healthcare* modules; Belgium-based, ~$5B+ valuation, annual releases.
- **Tryton:** GPLv3 (SaaS keeps modules private; on-prem distribution triggers copyleft); GTK + jQuery/Bootstrap "Sao" UI (dated); clean JSON-RPC headless but under-documented; ~180 modules; **GNU Health** (GPLv3 EMR/HMIS/LIMS, ~40+ modules, UNU-IIGH-adopted, v5.0 on Tryton 7.0 LTS); small non-profit-backed community; 6-mo releases, 5-yr LTS; cleanest architecture of the three.
- **ERPNext/Frappe:** **Framework MIT**, **ERPNext + Frappe Health GPLv3**, newer SaaS products AGPL; DocType metadata core; Desk UI dated but modern Vue 3 + Frappe UI SPAs proven (CRM/Helpdesk/HR); Frappe Health = FHIR-based, mid-maturity (v16.1.1, ~501★); Mumbai-based, bootstrapped-leaning (~$1.3M, Zerodha), frequent releases; high low-code velocity, opinionated learning curve.
